"""Municipal deed recorder ingestion client and MCP server integration."""

import re
from typing import Any, Dict, List, Optional

from autonomous_cre_underwriting.mcp.protocol import MCPServerBase, MCPTool
from autonomous_cre_underwriting.types.ingestion import DeedRecord, DeedType


def _normalize_name(name: str) -> str:
    """Normalize legal entity name by lowercasing and removing punctuation and corporate suffixes."""
    cleaned = re.sub(r"[,\.\-\']", "", name.lower())
    suffixes = ["llc", "l.l.c.", "lp", "l.p.", "inc", "corp", "corporation", "ltd", "partners", "holdings"]
    tokens = cleaned.split()
    tokens = [t for t in tokens if t not in suffixes]
    return " ".join(tokens).strip()


class DeedIngestor:
    """Municipal deed recorder client implementing DeedIngestorProtocol."""

    def __init__(self, seed_records: Optional[List[DeedRecord]] = None) -> None:
        self._records: List[DeedRecord] = []
        if seed_records:
            for record in seed_records:
                self.add_record(record)

    def add_record(self, record: DeedRecord) -> None:
        """Add a recorded deed instrument to the local municipal cache."""
        self._records.append(record)

    def fetch_deed_records(self, apn: str, county: str, state: str) -> List[DeedRecord]:
        """Query county recorder for conveyance history matching parcel identifiers."""
        norm_apn = apn.replace("-", "").replace(" ", "")
        norm_county = county.lower().strip()

        matched = []
        for r in self._records:
            r_apn = r.parcel_number.replace("-", "").replace(" ", "")
            if r_apn == norm_apn and (not county or r.county_name.lower() == norm_county):
                matched.append(r)

        # Sort chronologically by recording date
        return sorted(matched, key=lambda d: d.recording_date)

    def verify_chain_of_title(self, apn: str, reported_seller: str) -> bool:
        """Verify whether reported seller matches the recorded grantee in the latest recorded deed."""
        records = [r for r in self._records if r.parcel_number.replace("-", "").replace(" ", "") == apn.replace("-", "").replace(" ", "")]
        if not records:
            return False

        latest_deed = max(records, key=lambda d: d.recording_date)
        norm_reported = _normalize_name(reported_seller)
        norm_grantee = _normalize_name(latest_deed.grantee)

        return norm_reported in norm_grantee or norm_grantee in norm_reported

    def audit_chain_of_title(self, apn: str) -> Dict[str, Any]:
        """Audit full title chain continuity, identifying gaps, deed types, and total transfer volume."""
        records = [r for r in self._records if r.parcel_number.replace("-", "").replace(" ", "") == apn.replace("-", "").replace(" ", "")]
        if not records:
            return {
                "apn": apn,
                "chain_valid": False,
                "records_count": 0,
                "issues": ["No recorded deeds found for parcel"],
            }

        sorted_records = sorted(records, key=lambda d: d.recording_date)
        issues: List[str] = []
        chain_continuous = True

        for i in range(len(sorted_records) - 1):
            prior = sorted_records[i]
            curr = sorted_records[i + 1]
            prior_grantee = _normalize_name(prior.grantee)
            curr_grantor = _normalize_name(curr.grantor)

            if prior_grantee != curr_grantor and prior_grantee not in curr_grantor and curr_grantor not in prior_grantee:
                chain_continuous = False
                issues.append(
                    f"Chain gap between {prior.document_number} (Grantee: {prior.grantee}) and "
                    f"{curr.document_number} (Grantor: {curr.grantor})"
                )

        # Check for quitclaim deeds which may suggest defective title
        quitclaims = [r.document_number for r in sorted_records if r.deed_type == DeedType.QUITCLAIM_DEED]
        if quitclaims:
            issues.append(f"Quitclaim deeds detected without warranty: {quitclaims}")

        latest_grantee = sorted_records[-1].grantee
        total_consideration = sum(r.consideration_amount for r in sorted_records)

        return {
            "apn": apn,
            "chain_valid": chain_continuous and len(issues) == 0,
            "records_count": len(sorted_records),
            "latest_owner": latest_grantee,
            "latest_deed_date": str(sorted_records[-1].recording_date),
            "total_consideration": total_consideration,
            "issues": issues,
        }


class MunicipalDeedMCPServer(MCPServerBase):
    """MCP Server exposing municipal deed recorder tools."""

    def __init__(self, ingestor: Optional[DeedIngestor] = None) -> None:
        super().__init__(server_name="municipal-deed-recorder", server_version="1.0.0")
        self.ingestor = ingestor if ingestor is not None else DeedIngestor()
        self._register_mcp_tools()

    def _register_mcp_tools(self) -> None:
        fetch_tool = MCPTool(
            name="municipal_deed_fetch",
            description="Fetch all recorded deeds for a given parcel APN and county",
            parameters={
                "type": "object",
                "properties": {
                    "apn": {"type": "string", "description": "Assessor Parcel Number"},
                    "county": {"type": "string", "description": "County jurisdiction"},
                    "state": {"type": "string", "description": "Two-letter US state code"},
                },
                "required": ["apn", "county", "state"],
            },
        )
        self.register_tool(fetch_tool, self._handle_fetch)

        verify_tool = MCPTool(
            name="municipal_deed_verify_chain",
            description="Verify if the claimed seller is the legitimate recorded owner on title",
            parameters={
                "type": "object",
                "properties": {
                    "apn": {"type": "string", "description": "Assessor Parcel Number"},
                    "reported_seller": {"type": "string", "description": "Reported seller name"},
                },
                "required": ["apn", "reported_seller"],
            },
        )
        self.register_tool(verify_tool, self._handle_verify)

        audit_tool = MCPTool(
            name="municipal_deed_audit_chain",
            description="Audit chain of title continuity, gaps, and title warranties for a parcel",
            parameters={
                "type": "object",
                "properties": {
                    "apn": {"type": "string", "description": "Assessor Parcel Number"},
                },
                "required": ["apn"],
            },
        )
        self.register_tool(audit_tool, self._handle_audit)

    def _handle_fetch(self, args: Dict[str, Any]) -> Dict[str, Any]:
        apn = args.get("apn", "")
        county = args.get("county", "")
        state = args.get("state", "")
        records = self.ingestor.fetch_deed_records(apn=apn, county=county, state=state)
        return {"apn": apn, "records": [r.model_dump(mode="json") for r in records]}

    def _handle_verify(self, args: Dict[str, Any]) -> Dict[str, Any]:
        apn = args.get("apn", "")
        seller = args.get("reported_seller", "")
        verified = self.ingestor.verify_chain_of_title(apn=apn, reported_seller=seller)
        return {"apn": apn, "reported_seller": seller, "verified": verified}

    def _handle_audit(self, args: Dict[str, Any]) -> Dict[str, Any]:
        apn = args.get("apn", "")
        return self.ingestor.audit_chain_of_title(apn=apn)
