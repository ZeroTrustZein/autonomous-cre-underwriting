"""Risk synthesis engine, covenant compliance checker, and Investment Committee memorandum builder."""

from typing import List, Optional, Tuple

from autonomous_cre_underwriting.types.agents import AgentRole
from autonomous_cre_underwriting.types.financial import (
    DCFValuationResult,
    FinancingAssumptions,
    ValuationMetrics,
)
from autonomous_cre_underwriting.types.property import PropertyDeal
from autonomous_cre_underwriting.types.risk import (
    ChecklistStatus,
    DiligenceChecklistItem,
    MemoRecommendation,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
    SignOff,
    StressScenario,
    UnderwritingMemo,
)


class RiskSynthesisEngine:
    """Evaluates multi-source diligence anomalies, covenant tests, and synthesizes IC memos."""

    def evaluate_covenant_compliance(
        self,
        deal: PropertyDeal,
        financing: FinancingAssumptions,
        dcf_result: DCFValuationResult,
    ) -> List[DiligenceChecklistItem]:
        """Verify debt covenants against modeled financial results."""
        checklist: List[DiligenceChecklistItem] = []

        # 1. DSCR Covenant Check
        min_dscr = dcf_result.metrics.min_dscr_observed
        covenant_dscr = financing.min_dscr_covenant
        if min_dscr >= covenant_dscr:
            dscr_status = ChecklistStatus.PASS
            dscr_comments = f"Minimum pro-forma DSCR of {min_dscr:.2f}x satisfies {covenant_dscr:.2f}x covenant."
        elif min_dscr >= 1.05:
            dscr_status = ChecklistStatus.REQUIRES_REVIEW
            dscr_comments = f"Minimum DSCR of {min_dscr:.2f}x is below covenant {covenant_dscr:.2f}x but covers debt service."
        else:
            dscr_status = ChecklistStatus.FAIL
            dscr_comments = (
                f"Minimum DSCR of {min_dscr:.2f}x violates lender covenant of {covenant_dscr:.2f}x."
            )

        checklist.append(
            DiligenceChecklistItem(
                category=RiskCategory.REFINANCING_DEBT,
                requirement=f"Minimum DSCR covenant >= {covenant_dscr:.2f}x",
                status=dscr_status,
                comments=dscr_comments,
                citation_reference="Financing Term Sheet & DCF Model",
            )
        )

        # 2. LTV Covenant Check
        purchase_price = deal.target_purchase_price
        ltv = financing.loan_amount / purchase_price if purchase_price > 0 else 1.0
        covenant_ltv = financing.max_ltv_covenant
        if ltv <= covenant_ltv:
            ltv_status = ChecklistStatus.PASS
            ltv_comments = f"Underwritten LTV of {ltv * 100:.1f}% satisfies max {covenant_ltv * 100:.1f}% constraint."
        else:
            ltv_status = ChecklistStatus.FAIL
            ltv_comments = f"Underwritten LTV of {ltv * 100:.1f}% breaches max covenant of {covenant_ltv * 100:.1f}%."

        checklist.append(
            DiligenceChecklistItem(
                category=RiskCategory.REFINANCING_DEBT,
                requirement=f"Maximum LTV covenant <= {covenant_ltv * 100:.1f}%",
                status=ltv_status,
                comments=ltv_comments,
                citation_reference="Loan Sizing Memo",
            )
        )

        # 3. Year 1 Debt Yield Check (standard institutional hurdle: >= 8.0%)
        if dcf_result.annual_cash_flows:
            y1_dy = dcf_result.annual_cash_flows[0].debt_yield
            if y1_dy >= 0.08:
                dy_status = ChecklistStatus.PASS
                dy_comments = (
                    f"Year 1 debt yield of {y1_dy * 100:.2f}% exceeds 8.0% institutional threshold."
                )
            elif y1_dy >= 0.065:
                dy_status = ChecklistStatus.REQUIRES_REVIEW
                dy_comments = (
                    f"Year 1 debt yield of {y1_dy * 100:.2f}% is moderate (target >= 8.0%)."
                )
            else:
                dy_status = ChecklistStatus.FAIL
                dy_comments = f"Year 1 debt yield of {y1_dy * 100:.2f}% is inadequate for requested debt quantum."

            checklist.append(
                DiligenceChecklistItem(
                    category=RiskCategory.REFINANCING_DEBT,
                    requirement="Year 1 Debt Yield >= 8.00%",
                    status=dy_status,
                    comments=dy_comments,
                    citation_reference="DCF Cash Flow Schedule Year 1",
                )
            )

        return checklist

    def build_standard_checklist(
        self,
        deal: PropertyDeal,
        title_continuous: bool = True,
        active_liens: float = 0.0,
    ) -> List[DiligenceChecklistItem]:
        """Construct standard multi-category diligence compliance items."""
        items: List[DiligenceChecklistItem] = []

        # Title diligence
        if title_continuous and active_liens == 0.0:
            title_status = ChecklistStatus.PASS
            title_notes = "Complete chain of title confirmed; no unreleased tax or mechanics liens."
        elif not title_continuous:
            title_status = ChecklistStatus.FAIL
            title_notes = "Gap in chain of title between recorded deeds."
        else:
            title_status = ChecklistStatus.REQUIRES_REVIEW
            title_notes = (
                f"Outstanding liens of ${active_liens:,.2f} require payoff letter at closing."
            )

        items.append(
            DiligenceChecklistItem(
                category=RiskCategory.TITLE_AND_LEGAL,
                requirement="Clean chain of title and unencumbered deed verification",
                status=title_status,
                comments=title_notes,
                citation_reference=deal.address.apn or "County Deed Records",
            )
        )

        # Environmental & Physical
        flood_status = (
            ChecklistStatus.PASS
            if deal.physical.flood_zone in ("X", "C", "D")
            else ChecklistStatus.REQUIRES_REVIEW
        )
        items.append(
            DiligenceChecklistItem(
                category=RiskCategory.PHYSICAL_ENVIRONMENTAL,
                requirement="FEMA Flood Hazard Assessment (Zone X non-special hazard)",
                status=flood_status,
                comments=f"Property located in FEMA Zone {deal.physical.flood_zone}.",
                citation_reference="FEMA Flood Map Service Center",
            )
        )

        # Occupancy & Rent roll
        occ = deal.unit_mix.physical_occupancy_rate
        occ_status = (
            ChecklistStatus.PASS
            if occ >= 0.90
            else (ChecklistStatus.REQUIRES_REVIEW if occ >= 0.75 else ChecklistStatus.FAIL)
        )
        items.append(
            DiligenceChecklistItem(
                category=RiskCategory.TENANT_CREDIT,
                requirement="Stabilized Physical Occupancy >= 90%",
                status=occ_status,
                comments=f"In-place physical occupancy is {occ * 100:.1f}%.",
                citation_reference="Certified Rent Roll",
            )
        )

        return items

    def synthesize_decision(
        self,
        deal: PropertyDeal,
        metrics: ValuationMetrics,
        risk_findings: List[RiskFinding],
        checklist: List[DiligenceChecklistItem],
        stress_scenarios: List[StressScenario],
        target_irr_hurdle: float = 0.12,
    ) -> Tuple[MemoRecommendation, List[str], str]:
        """Determine swarm recommendation, conditions precedent, and executive narrative."""
        # 1. Critical blockers
        critical_risks = [r for r in risk_findings if r.severity == RiskSeverity.CRITICAL]
        failed_checklist = [item for item in checklist if item.status == ChecklistStatus.FAIL]
        high_risks = [r for r in risk_findings if r.severity == RiskSeverity.HIGH]

        conditions_precedent: List[str] = []

        if critical_risks:
            reason = (
                f"Critical risk flag: {critical_risks[0].title}. {critical_risks[0].description}"
            )
            return (
                MemoRecommendation.REJECT,
                ["Critical diligence defects must be remedied prior to any consideration."],
                f"REJECT recommendation due to unresolved critical defect: {reason}",
            )

        if failed_checklist:
            reasons = "; ".join(f"{c.requirement} ({c.comments})" for c in failed_checklist)
            return (
                MemoRecommendation.REJECT,
                ["Resolve checklist failure items prior to closing."],
                f"REJECT recommendation: Failed underwriting compliance requirements: {reasons}",
            )

        # 2. Return hurdles and covenant breaches
        covenants_breached = any(s.covenant_breached for s in stress_scenarios)
        if metrics.levered_irr < (target_irr_hurdle - 0.04) or metrics.min_dscr_observed < 1.10:
            return (
                MemoRecommendation.REVISE_TERMS,
                [
                    "Renegotiate acquisition price to increase entry cap rate",
                    "Resize senior debt to maintain minimum 1.25x DSCR buffer",
                ],
                f"REVISE TERMS recommendation: Levered IRR ({metrics.levered_irr * 100:.1f}%) or "
                f"DSCR ({metrics.min_dscr_observed:.2f}x) fails baseline investment guidelines.",
            )

        # 3. Formulate conditions precedent from High risks and review items
        for r in high_risks:
            if r.proposed_mitigation:
                conditions_precedent.append(f"Mitigate {r.title}: {r.proposed_mitigation}")
            else:
                conditions_precedent.append(
                    f"Satisfactory resolution of {r.title} ({r.impact_summary})"
                )

        for c in checklist:
            if c.status == ChecklistStatus.REQUIRES_REVIEW:
                conditions_precedent.append(f"Complete review of: {c.requirement} ({c.comments})")

        # Standard institutional conditions precedent
        if not conditions_precedent:
            conditions_precedent.append("Execution of definitive loan and acquisition agreements.")
            conditions_precedent.append("Final title policy endorsement without survey exceptions.")

        # 4. Determine APPROVE_WITH_CONDITIONS vs STRONGLY_RECOMMEND
        if high_risks or len(conditions_precedent) > 2 or covenants_breached:
            recommendation = MemoRecommendation.APPROVE_WITH_CONDITIONS
            exec_summary = (
                f"Approve acquisition of '{deal.title}' at ${deal.target_purchase_price:,.0f} basis "
                f"with conditions precedent. Model projects {metrics.levered_irr * 100:.1f}% levered IRR, "
                f"{metrics.equity_multiple:.2f}x equity multiple, and {metrics.min_dscr_observed:.2f}x min DSCR. "
                f"Key risks require designated escrow or contractual protections before closing."
            )
        else:
            recommendation = MemoRecommendation.STRONGLY_RECOMMEND
            exec_summary = (
                f"Strongly recommend acquisition of '{deal.title}' at ${deal.target_purchase_price:,.0f} basis. "
                f"Compelling core-plus profile delivering {metrics.levered_irr * 100:.1f}% levered IRR, "
                f"{metrics.equity_multiple:.2f}x equity multiple, clean title, and compliant credit metrics."
            )

        return recommendation, conditions_precedent, exec_summary

    def generate_agent_sign_offs(
        self,
        recommendation: MemoRecommendation,
        roles: Optional[List[AgentRole]] = None,
    ) -> List[SignOff]:
        """Generate unanimous committee sign-offs."""
        if roles is None:
            roles = [
                AgentRole.MUNICIPAL_DEED_AUDITOR,
                AgentRole.SEC_DILIGENCE_ANALYST,
                AgentRole.DCF_VALUATION_ENGINEER,
                AgentRole.CREDIT_RISK_UNDERWRITER,
                AgentRole.INVESTMENT_COMMITTEE_CHAIR,
            ]

        sign_offs: List[SignOff] = []
        for role in roles:
            rationale = (
                f"Approved based on diligence checklist compliance and modeled returns "
                f"under {role.value} mandate."
                if recommendation
                in (
                    MemoRecommendation.STRONGLY_RECOMMEND,
                    MemoRecommendation.APPROVE_WITH_CONDITIONS,
                )
                else f"Diligence review under {role.value} mandate concurs with {recommendation.value}."
            )
            sign_offs.append(
                SignOff(
                    role=role,
                    recommendation=recommendation,
                    rationale=rationale,
                )
            )
        return sign_offs

    def build_memo(
        self,
        deal: PropertyDeal,
        dcf_result: DCFValuationResult,
        risk_findings: List[RiskFinding],
        diligence_checklist: List[DiligenceChecklistItem],
        stress_scenarios: List[StressScenario],
    ) -> UnderwritingMemo:
        """Synthesize complete Investment Committee Memorandum."""
        rec, conditions, summary = self.synthesize_decision(
            deal=deal,
            metrics=dcf_result.metrics,
            risk_findings=risk_findings,
            checklist=diligence_checklist,
            stress_scenarios=stress_scenarios,
        )

        sign_offs = self.generate_agent_sign_offs(recommendation=rec)

        return UnderwritingMemo(
            deal_id=deal.id,
            deal_title=deal.title,
            executive_summary=summary,
            recommendation=rec,
            valuation_summary=dcf_result.metrics,
            risk_findings=risk_findings,
            diligence_checklist=diligence_checklist,
            stress_scenarios=stress_scenarios,
            conditions_precedent=conditions,
            sign_offs=sign_offs,
        )
