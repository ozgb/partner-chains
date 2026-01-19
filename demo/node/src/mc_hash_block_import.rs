//! Two-step MC hash verification at block import time.
//!
//! This module implements the DOS-resistant MC hash verification strategy:
//! 1. Step 1: Check if the block exists AT ALL in Cardano → if not, return error (peer penalty)
//! 2. Step 2: Check if the block is STABLE → if not, return MissingState (no penalty, retry later)

use sc_consensus::block_import::{BlockCheckParams, BlockImport, BlockImportParams};
use sc_consensus::ImportResult;
use sidechain_domain::McBlockHash;
use sidechain_mc_hash::{McHashDataSource, McHashInherentDigest};
use sp_consensus::Error as ConsensusError;
use sp_consensus_slots::SlotDuration;
use sp_partner_chains_consensus_aura::inherent_digest::InherentDigest;
use sp_runtime::traits::{Block as BlockT, Header as HeaderT};
use std::marker::PhantomData;
use std::sync::Arc;

/// A block import wrapper that performs two-step MC hash verification.
///
/// This wrapper intercepts block imports and verifies that the mc_hash in the block header:
/// 1. Exists in Cardano (if not → error → peer penalty)
/// 2. Is stable (if not → MissingState → no penalty, retry later)
pub struct McHashVerifyingBlockImport<Inner, Block: BlockT> {
    inner: Inner,
    mc_hash_data_source: Arc<dyn McHashDataSource + Send + Sync>,
    slot_duration: SlotDuration,
    _phantom: PhantomData<Block>,
}

impl<Inner, Block> McHashVerifyingBlockImport<Inner, Block>
where
    Block: BlockT,
{
    /// Creates a new MC hash verifying block import wrapper.
    ///
    /// # Arguments
    /// - `inner`: The inner block import to wrap (typically GrandpaBlockImport)
    /// - `mc_hash_data_source`: Data source for querying Cardano blocks
    /// - `slot_duration`: Partner chain slot duration for timestamp calculations
    pub fn new(
        inner: Inner,
        mc_hash_data_source: Arc<dyn McHashDataSource + Send + Sync>,
        slot_duration: SlotDuration,
    ) -> Self {
        Self {
            inner,
            mc_hash_data_source,
            slot_duration,
            _phantom: PhantomData,
        }
    }
}

/// Extracts mc_hash from block header digest.
fn extract_mc_hash_from_digest<Block: BlockT>(
    header: &Block::Header,
) -> Result<McBlockHash, String> {
    McHashInherentDigest::value_from_digest(header.digest().logs())
        .map_err(|e| format!("Failed to extract mc_hash from digest: {}", e))
}

/// Extracts slot from block header using Aura pre-digest.
fn extract_slot_from_header<Block: BlockT>(
    header: &Block::Header,
) -> Result<sp_consensus_slots::Slot, String> {
    use sp_consensus_aura::sr25519::AuthorityPair as AuraPair;
    use sp_core::Pair;

    sc_consensus_aura::find_pre_digest::<Block, <AuraPair as Pair>::Signature>(header)
        .map_err(|e| format!("Failed to extract slot from header: {:?}", e))
}

/// Converts a slot to timestamp.
fn slot_to_timestamp(
    slot: sp_consensus_slots::Slot,
    slot_duration: SlotDuration,
) -> sp_timestamp::Timestamp {
    sp_timestamp::Timestamp::new(slot.as_u64() * slot_duration.as_millis())
}

#[async_trait::async_trait]
impl<Inner, Block> BlockImport<Block> for McHashVerifyingBlockImport<Inner, Block>
where
    Inner: BlockImport<Block, Error = ConsensusError> + Send + Sync,
    Block: BlockT,
{
    type Error = ConsensusError;

    async fn check_block(
        &self,
        block: BlockCheckParams<Block>,
    ) -> Result<ImportResult, Self::Error> {
        self.inner.check_block(block).await
    }

    async fn import_block(
        &self,
        block: BlockImportParams<Block>,
    ) -> Result<ImportResult, Self::Error> {
        // Skip MC hash verification for state-only imports (warp sync, etc.)
        if block.with_state() || block.state_action.skip_execution_checks() {
            return self.inner.import_block(block).await;
        }

        // Extract mc_hash from block header digest
        let mc_hash = match extract_mc_hash_from_digest::<Block>(&block.header) {
            Ok(hash) => hash,
            Err(e) => {
                log::warn!(
                    target: "mc-hash-import",
                    "Failed to extract mc_hash from header: {}",
                    e
                );
                return Err(ConsensusError::Other(Box::new(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    format!("Failed to extract mc_hash from header: {}", e),
                ))));
            }
        };

        // Calculate reference timestamp from slot
        let slot = match extract_slot_from_header::<Block>(&block.header) {
            Ok(s) => s,
            Err(e) => {
                log::warn!(
                    target: "mc-hash-import",
                    "Failed to extract slot from header: {}",
                    e
                );
                return Err(ConsensusError::Other(Box::new(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    format!("Failed to extract slot from header: {}", e),
                ))));
            }
        };
        let reference_timestamp = slot_to_timestamp(slot, self.slot_duration);

        // ============================================================
        // STEP 1: Check if block exists AT ALL in Cardano
        // ============================================================
        // This catches fabricated/invalid mc_hash values that will never be valid.
        // If the block doesn't exist, this is malicious behavior → return error → peer penalty.

        match self
            .mc_hash_data_source
            .get_block_by_hash(mc_hash.clone())
            .await
        {
            Ok(None) => {
                // Block does NOT exist in Cardano - this is INVALID, not "not ready yet"
                // Return error which will trigger VerificationFailed → peer penalty
                log::warn!(
                    target: "mc-hash-import",
                    "MC hash {:?} does not exist in Cardano - rejecting block",
                    mc_hash
                );
                return Err(ConsensusError::Other(Box::new(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    format!(
                        "Invalid mc_hash reference: block {:?} does not exist in Cardano",
                        mc_hash
                    ),
                ))));
            }
            Ok(Some(mc_block)) => {
                // Block exists - proceed to stability check
                log::trace!(
                    target: "mc-hash-import",
                    "MC hash {:?} exists in Cardano at block number {}",
                    mc_hash,
                    mc_block.number
                );
            }
            Err(e) => {
                // DB connection error - treat as temporary, return MissingState
                log::warn!(
                    target: "mc-hash-import",
                    "Failed to query db-sync for mc_hash existence: {}",
                    e
                );
                return Ok(ImportResult::MissingState);
            }
        }

        // ============================================================
        // STEP 2: Check if block is STABLE (has enough confirmations)
        // ============================================================
        // The block exists, but may not have enough confirmations yet.
        // This is a temporary condition → return MissingState → no penalty, retry later.

        match self
            .mc_hash_data_source
            .get_stable_block_for(mc_hash.clone(), reference_timestamp)
            .await
        {
            Ok(Some(_stable_block)) => {
                // Block is stable - proceed with import
                log::debug!(
                    target: "mc-hash-import",
                    "MC hash {:?} is stable, proceeding with block import",
                    mc_hash
                );
                self.inner.import_block(block).await
            }
            Ok(None) => {
                // Block exists but is not stable yet - return MissingState
                // NO peer penalty, NO restart(), block will be re-requested later
                log::info!(
                    target: "mc-hash-import",
                    "MC hash {:?} exists but is not yet stable, returning MissingState",
                    mc_hash
                );
                Ok(ImportResult::MissingState)
            }
            Err(e) => {
                // DB error during stability check - treat as temporary
                log::warn!(
                    target: "mc-hash-import",
                    "Failed to query db-sync for mc_hash stability: {}",
                    e
                );
                Ok(ImportResult::MissingState)
            }
        }
    }
}
