"""Investment Committee Underwriting Memorandum formatters and report generators."""

import json

from autonomous_cre_underwriting.types.risk import UnderwritingMemo


class MemoExporter:
    """Formatter and publisher for final Investment Committee Memorandums."""

    @staticmethod
    def to_markdown(memo: UnderwritingMemo) -> str:
        """Render complete audit-ready Investment Committee memo in Markdown."""
        lines = [
            f"# INVESTMENT COMMITTEE MEMORANDUM: {memo.deal_title.upper()}",
            f"**Deal ID:** `{memo.deal_id}` | **Date:** {memo.created_at.strftime('%Y-%m-%d')} | **Recommendation:** `{memo.recommendation.value.upper()}`",
            "",
            "## 1. Executive Summary",
            memo.executive_summary,
            "",
            "## 2. Key Valuation & Return Metrics",
            f"- **Target Purchase Price:** ${memo.valuation_summary.purchase_price:,.2f}",
            f"- **Equity Required:** ${memo.valuation_summary.equity_invested:,.2f}",
            f"- **In-Place Cap Rate:** {memo.valuation_summary.in_place_cap_rate:.2%}",
            f"- **Exit Cap Rate:** {memo.valuation_summary.exit_cap_rate:.2%}",
            f"- **Unlevered IRR:** {memo.valuation_summary.unlevered_irr:.2%}",
            f"- **Levered IRR:** {memo.valuation_summary.levered_irr:.2%}",
            f"- **Equity Multiple:** {memo.valuation_summary.equity_multiple:.2f}x",
            f"- **Net Present Value (NPV):** ${memo.valuation_summary.net_present_value:,.2f}",
            f"- **Average DSCR:** {memo.valuation_summary.average_dscr:.2f}x (Min: {memo.valuation_summary.min_dscr_observed:.2f}x)",
            "",
            "## 3. Diligence Risk Findings",
        ]

        if memo.risk_findings:
            for rf in memo.risk_findings:
                lines.append(
                    f"### [{rf.severity.value.upper()}] {rf.title} ({rf.category.value})"
                )
                lines.append(f"*{rf.description}*")
                lines.append(f"- **Evidence:** {rf.evidence_citation}")
                lines.append(f"- **Impact:** {rf.impact_summary}")
                lines.append(f"- **Proposed Mitigation:** {rf.proposed_mitigation}")
                lines.append(f"- **Sign-off Role:** `{rf.confirmed_by_role.value}`")
                lines.append("")
        else:
            lines.append("No material risk findings reported.")
            lines.append("")

        lines.append("## 4. Covenant & Diligence Checklist")
        lines.append("| Category | Requirement | Status | Comments |")
        lines.append("| :--- | :--- | :---: | :--- |")
        for item in memo.diligence_checklist:
            lines.append(
                f"| {item.category.value} | {item.requirement} | `{item.status.value.upper()}` | {item.comments} |"
            )
        lines.append("")

        lines.append("## 5. Downside Stress Scenarios")
        lines.append("| Scenario | Rent Shock | Vacancy Shock | OpEx Shock | Exit Cap (+bps) | Resultant IRR | Min DSCR | Breached |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for sc in memo.stress_scenarios:
            breached_str = "YES" if sc.covenant_breached else "NO"
            lines.append(
                f"| {sc.name} | {sc.rent_shock_pct:+.1%} | {sc.vacancy_shock_pct:+.1%} | "
                f"{sc.opex_shock_pct:+.1%} | +{sc.exit_cap_expansion_bps} bps | "
                f"{sc.resultant_irr:.2%} | {sc.min_dscr_observed:.2f}x | {breached_str} |"
            )
        lines.append("")

        lines.append("## 6. Conditions Precedent to Closing")
        if memo.conditions_precedent:
            for idx, cp in enumerate(memo.conditions_precedent, start=1):
                lines.append(f"{idx}. {cp}")
        else:
            lines.append("No outstanding conditions precedent.")
        lines.append("")

        lines.append("## 7. Swarm Agent Committee Sign-Offs")
        for so in memo.sign_offs:
            lines.append(
                f"- **{so.role.value}:** `{so.recommendation.value.upper()}` — {so.rationale} ({so.timestamp.strftime('%Y-%m-%d %H:%M UTC')})"
            )

        return "\n".join(lines)

    @staticmethod
    def to_summary_text(memo: UnderwritingMemo) -> str:
        """Render concise plain-text memo summary."""
        return (
            f"[{memo.recommendation.value.upper()}] {memo.deal_title} ({memo.deal_id})\n"
            f"Price: ${memo.valuation_summary.purchase_price:,.0f} | "
            f"Levered IRR: {memo.valuation_summary.levered_irr:.1%} | "
            f"EM: {memo.valuation_summary.equity_multiple:.2f}x | "
            f"DSCR: {memo.valuation_summary.average_dscr:.2f}x\n"
            f"Risks: {len(memo.risk_findings)} flagged | "
            f"Checklist: {len(memo.diligence_checklist)} items | "
            f"Conditions: {len(memo.conditions_precedent)}"
        )

    @staticmethod
    def to_json(memo: UnderwritingMemo, indent: int = 2) -> str:
        """Serialize complete memo to structured JSON string."""
        return json.dumps(memo.model_dump(mode="json"), indent=indent)
