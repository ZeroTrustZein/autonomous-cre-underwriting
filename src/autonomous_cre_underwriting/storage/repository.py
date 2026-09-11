"""Persistence repository for deals, underwriting memos, DCF valuations, and swarm workflows."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from autonomous_cre_underwriting.types.agents import SwarmWorkflowState
from autonomous_cre_underwriting.types.financial import DCFValuationResult
from autonomous_cre_underwriting.types.property import DealStatus, PropertyDeal, PropertyType
from autonomous_cre_underwriting.types.risk import UnderwritingMemo


class DealRepository:
    """Multi-entity repository providing in-memory caching and JSON file persistence."""

    def __init__(self, persistence_dir: Optional[str] = None) -> None:
        self.persistence_dir = Path(persistence_dir) if persistence_dir else None
        self._deals: Dict[str, PropertyDeal] = {}
        self._memos: Dict[str, UnderwritingMemo] = {}
        self._valuations: Dict[str, DCFValuationResult] = {}
        self._workflows: Dict[str, SwarmWorkflowState] = {}

    # Deal operations
    def save_deal(self, deal: PropertyDeal) -> None:
        """Store or update a PropertyDeal."""
        self._deals[deal.id] = deal

    def get_deal(self, deal_id: str) -> Optional[PropertyDeal]:
        """Fetch a deal by identifier."""
        return self._deals.get(deal_id)

    def list_deals(self) -> List[PropertyDeal]:
        """List all registered deals."""
        return list(self._deals.values())

    def delete_deal(self, deal_id: str) -> bool:
        """Remove a deal and its associated records."""
        removed = False
        if deal_id in self._deals:
            del self._deals[deal_id]
            removed = True
        self._memos.pop(deal_id, None)
        self._valuations.pop(deal_id, None)

        if self.persistence_dir and self.persistence_dir.exists():
            deal_file = self.persistence_dir / "deals" / f"{deal_id}.json"
            if deal_file.exists():
                deal_file.unlink()
            memo_file = self.persistence_dir / "memos" / f"{deal_id}_memo.json"
            if memo_file.exists():
                memo_file.unlink()
            val_file = self.persistence_dir / "valuations" / f"{deal_id}.json"
            if val_file.exists():
                val_file.unlink()

        return removed

    def query_deals(
        self,
        status: Optional[DealStatus] = None,
        property_type: Optional[PropertyType] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sponsor: Optional[str] = None,
    ) -> List[PropertyDeal]:
        """Filter deals by criteria."""
        results = list(self._deals.values())

        if status is not None:
            results = [d for d in results if d.status == status]
        if property_type is not None:
            results = [d for d in results if d.property_type == property_type]
        if min_price is not None:
            results = [d for d in results if d.target_purchase_price >= min_price]
        if max_price is not None:
            results = [d for d in results if d.target_purchase_price <= max_price]
        if sponsor is not None:
            norm_s = sponsor.lower()
            results = [d for d in results if norm_s in d.sponsor_name.lower()]

        return results

    # Memo operations
    def save_memo(self, memo: UnderwritingMemo) -> None:
        """Save an Investment Committee UnderwritingMemo indexed by deal_id."""
        self._memos[memo.deal_id] = memo

    def get_memo(self, deal_id: str) -> Optional[UnderwritingMemo]:
        """Retrieve memo for a deal."""
        return self._memos.get(deal_id)

    def list_memos(self) -> List[UnderwritingMemo]:
        """List all generated underwriting memos."""
        return list(self._memos.values())

    # Valuation operations
    def save_valuation(self, valuation: DCFValuationResult) -> None:
        """Save a DCF valuation result indexed by deal_id."""
        self._valuations[valuation.deal_id] = valuation

    def get_valuation(self, deal_id: str) -> Optional[DCFValuationResult]:
        """Fetch DCF valuation result for a deal."""
        return self._valuations.get(deal_id)

    # Workflow state operations
    def save_workflow(self, workflow: SwarmWorkflowState) -> None:
        """Store or update workflow state."""
        self._workflows[workflow.id] = workflow

    def get_workflow(self, workflow_id: str) -> Optional[SwarmWorkflowState]:
        """Retrieve workflow state by its ID."""
        return self._workflows.get(workflow_id)

    def get_workflow_for_deal(self, deal_id: str) -> Optional[SwarmWorkflowState]:
        """Retrieve the latest workflow state associated with a deal ID."""
        matches = [w for w in self._workflows.values() if w.deal_id == deal_id]
        if not matches:
            return None
        return max(matches, key=lambda w: w.updated_at)

    # File persistence operations
    def export_to_directory(self, target_dir: Optional[str] = None) -> int:
        """Export all deals and memos to a directory as JSON files."""
        dir_path = Path(target_dir) if target_dir else self.persistence_dir
        if dir_path is None:
            raise ValueError("Target directory must be provided or persistence_dir set on repository")

        dir_path.mkdir(parents=True, exist_ok=True)
        deals_dir = dir_path / "deals"
        memos_dir = dir_path / "memos"
        workflows_dir = dir_path / "workflows"
        valuations_dir = dir_path / "valuations"
        deals_dir.mkdir(exist_ok=True)
        memos_dir.mkdir(exist_ok=True)
        workflows_dir.mkdir(exist_ok=True)
        valuations_dir.mkdir(exist_ok=True)

        count = 0
        for deal_id, deal in self._deals.items():
            file_path = deals_dir / f"{deal_id}.json"
            file_path.write_text(deal.model_dump_json(indent=2), encoding="utf-8")
            count += 1

        for deal_id, memo in self._memos.items():
            file_path = memos_dir / f"{deal_id}_memo.json"
            file_path.write_text(memo.model_dump_json(indent=2), encoding="utf-8")
            count += 1

        for wf_id, wf in self._workflows.items():
            file_path = workflows_dir / f"{wf.deal_id}_{wf.id}.json"
            file_path.write_text(wf.model_dump_json(indent=2), encoding="utf-8")

        for val_deal_id, val in self._valuations.items():
            file_path = valuations_dir / f"{val_deal_id}.json"
            file_path.write_text(val.model_dump_json(indent=2), encoding="utf-8")

        return count

    def import_from_directory(self, source_dir: Optional[str] = None) -> int:
        """Import deals and memos from JSON files in target directory."""
        dir_path = Path(source_dir) if source_dir else self.persistence_dir
        if dir_path is None or not dir_path.exists():
            return 0

        deals_dir = dir_path / "deals"
        memos_dir = dir_path / "memos"
        workflows_dir = dir_path / "workflows"
        valuations_dir = dir_path / "valuations"
        count = 0

        if deals_dir.exists():
            for f in deals_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    deal = PropertyDeal.model_validate(data)
                    self.save_deal(deal)
                    count += 1
                except Exception:
                    pass

        if memos_dir.exists():
            for f in memos_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    memo = UnderwritingMemo.model_validate(data)
                    self.save_memo(memo)
                    count += 1
                except Exception:
                    pass

        if workflows_dir.exists():
            for f in workflows_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    workflow = SwarmWorkflowState.model_validate(data)
                    self.save_workflow(workflow)
                except Exception:
                    pass

        if valuations_dir.exists():
            for f in valuations_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    valuation = DCFValuationResult.model_validate(data)
                    self.save_valuation(valuation)
                except Exception:
                    pass

        return count
