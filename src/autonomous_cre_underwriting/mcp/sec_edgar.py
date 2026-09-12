"""SEC EDGAR corporate filings ingestion client and MCP server integration."""

import re
from typing import Any, Dict, List, Optional

from autonomous_cre_underwriting.mcp.protocol import MCPServerBase, MCPTool
from autonomous_cre_underwriting.types.ingestion import (
    SECFiling,
    SECRiskMention,
    SECRiskTopic,
)


class SECIngestor:
    """SEC EDGAR corporate filing search and risk analysis client implementing SECIngestorProtocol."""

    def __init__(self, seed_filings: Optional[List[SECFiling]] = None) -> None:
        self._filings: List[SECFiling] = []
        # Index by normalized CIK
        self._cik_index: Dict[str, List[SECFiling]] = {}
        # Index by accession number
        self._accession_index: Dict[str, SECFiling] = {}
        if seed_filings:
            for f in seed_filings:
                self.add_filing(f)

    @staticmethod
    def normalize_cik(cik_or_ticker: str) -> str:
        """Pad numeric CIK to 10 digits or return uppercase ticker."""
        cleaned = cik_or_ticker.strip().upper()
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) > 0 and len(digits) <= 10 and digits == cleaned.lstrip("0"):
            return digits.zfill(10)
        return cleaned

    def add_filing(self, filing: SECFiling) -> None:
        """Register an SEC filing in the local catalog."""
        self._filings.append(filing)
        norm_cik = self.normalize_cik(filing.cik)
        if norm_cik not in self._cik_index:
            self._cik_index[norm_cik] = []
        self._cik_index[norm_cik].append(filing)
        self._accession_index[filing.accession_number] = filing

    def search_filings(
        self, cik_or_ticker: str, form_types: Optional[List[str]] = None
    ) -> List[SECFiling]:
        """Fetch SEC filings for sponsor or anchor tenant by CIK, ticker, or company name."""
        norm_query = self.normalize_cik(cik_or_ticker)
        query_text = cik_or_ticker.strip().lower()

        matched: List[SECFiling] = []
        if norm_query in self._cik_index:
            matched.extend(self._cik_index[norm_query])
        else:
            for f in self._filings:
                if (
                    query_text in f.company_name.lower()
                    or query_text == f.cik.lower()
                    or query_text in f.accession_number.lower()
                ):
                    matched.append(f)

        if form_types:
            norm_forms = {ft.upper().replace("-", "").replace(" ", "") for ft in form_types}
            matched = [
                f
                for f in matched
                if f.form_type.value.upper().replace("-", "").replace(" ", "") in norm_forms
            ]

        return sorted(matched, key=lambda f: f.filing_date, reverse=True)

    def extract_risk_factors(self, accession_number: str) -> List[Dict[str, Any]]:
        """Parse Item 1A Risk Factors and relevant lease disclosures for an accession number."""
        filing = self._accession_index.get(accession_number)
        if filing is None:
            # Try partial search
            for acc, f in self._accession_index.items():
                if accession_number in acc:
                    filing = f
                    break

        if filing is None:
            return []

        results = []
        for mention in filing.risk_mentions:
            results.append(
                {
                    "topic": mention.topic.value,
                    "excerpt": mention.excerpt,
                    "item_section": mention.item_section,
                    "severity_score": mention.severity_score,
                    "relevance_score": mention.relevance_score,
                }
            )
        return results

    def assess_sponsor_credit(self, cik_or_ticker: str) -> Dict[str, Any]:
        """Synthesize credit risk profile, debt maturities, and tenant risks from all filings."""
        filings = self.search_filings(cik_or_ticker)
        if not filings:
            return {
                "identifier": cik_or_ticker,
                "found_filings": 0,
                "credit_risk_level": "UNKNOWN",
                "summary": f"No SEC filings available for {cik_or_ticker}",
                "refinancing_risk_flag": False,
                "high_severity_mentions": [],
            }

        all_mentions: List[SECRiskMention] = []
        for f in filings:
            all_mentions.extend(f.risk_mentions)

        refinancing_flag = any(
            m.topic == SECRiskTopic.REFINANCING_RISK
            or "floating" in m.excerpt.lower()
            or "sofr" in m.excerpt.lower()
            for m in all_mentions
        )

        high_severity = [
            m.model_dump(mode="json") for m in all_mentions if m.severity_score >= 0.70
        ]

        # Determine overall credit risk rating
        if any(m.severity_score >= 0.85 for m in all_mentions):
            level = "CRITICAL"
        elif any(m.severity_score >= 0.65 for m in all_mentions) or refinancing_flag:
            level = "ELEVATED"
        elif all_mentions:
            level = "MODERATE"
        else:
            level = "LOW"

        return {
            "identifier": cik_or_ticker,
            "company_name": filings[0].company_name if filings else "",
            "found_filings": len(filings),
            "latest_filing_date": str(filings[0].filing_date) if filings else None,
            "credit_risk_level": level,
            "refinancing_risk_flag": refinancing_flag,
            "total_risk_mentions": len(all_mentions),
            "high_severity_mentions": high_severity,
        }


class SECEdgarMCPServer(MCPServerBase):
    """MCP Server exposing SEC EDGAR corporate diligence tools."""

    def __init__(self, ingestor: Optional[SECIngestor] = None) -> None:
        super().__init__(server_name="sec-edgar-diligent", server_version="1.0.0")
        self.ingestor = ingestor if ingestor is not None else SECIngestor()
        self._register_mcp_tools()

    def _register_mcp_tools(self) -> None:
        search_tool = MCPTool(
            name="sec_edgar_search",
            description="Search SEC filings for sponsor or anchor tenant by CIK or ticker",
            parameters={
                "type": "object",
                "properties": {
                    "cik_or_ticker": {
                        "type": "string",
                        "description": "CIK number, ticker, or company name",
                    },
                    "form_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of form types e.g. ['10-K', '10-Q']",
                    },
                },
                "required": ["cik_or_ticker"],
            },
        )
        self.register_tool(search_tool, self._handle_search)

        risk_tool = MCPTool(
            name="sec_edgar_risk_factors",
            description="Extract Item 1A Risk Factors from a specific SEC filing accession number",
            parameters={
                "type": "object",
                "properties": {
                    "accession_number": {
                        "type": "string",
                        "description": "SEC filing accession number",
                    },
                },
                "required": ["accession_number"],
            },
        )
        self.register_tool(risk_tool, self._handle_risk_factors)

        assess_tool = MCPTool(
            name="sec_edgar_assess_sponsor",
            description="Evaluate corporate debt reset exposure and creditworthiness across all filings",
            parameters={
                "type": "object",
                "properties": {
                    "cik_or_ticker": {
                        "type": "string",
                        "description": "CIK number, ticker, or entity name",
                    },
                },
                "required": ["cik_or_ticker"],
            },
        )
        self.register_tool(assess_tool, self._handle_assess)

    def _handle_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        cik = args.get("cik_or_ticker", "")
        forms = args.get("form_types")
        filings = self.ingestor.search_filings(cik_or_ticker=cik, form_types=forms)
        return {"cik_or_ticker": cik, "filings": [f.model_dump(mode="json") for f in filings]}

    def _handle_risk_factors(self, args: Dict[str, Any]) -> Dict[str, Any]:
        acc = args.get("accession_number", "")
        factors = self.ingestor.extract_risk_factors(accession_number=acc)
        return {"accession_number": acc, "risk_factors": factors}

    def _handle_assess(self, args: Dict[str, Any]) -> Dict[str, Any]:
        cik = args.get("cik_or_ticker", "")
        return self.ingestor.assess_sponsor_credit(cik_or_ticker=cik)
