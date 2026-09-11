"""Unit tests for risk findings, stress tests, and underwriting memorandum synthesis."""

from autonomous_cre_underwriting.types.agents import AgentRole
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


def test_risk_finding_attributes(sample_risk_findings):
    """Verify diligence risk findings categorization and fields."""
    assert len(sample_risk_findings) == 2
    f1 = sample_risk_findings[0]
    assert f1.category == RiskCategory.TITLE_AND_LEGAL
    assert f1.severity == RiskSeverity.MEDIUM
    assert f1.confirmed_by_role == AgentRole.MUNICIPAL_DEED_AUDITOR

    f2 = sample_risk_findings[1]
    assert f2.category == RiskCategory.REFINANCING_DEBT
    assert f2.severity == RiskSeverity.HIGH
    assert f2.confirmed_by_role == AgentRole.SEC_DILIGENCE_ANALYST


def test_diligence_checklist_item():
    """Itemized diligence compliance items and status."""
    item = DiligenceChecklistItem(
        category=RiskCategory.PHYSICAL_ENVIRONMENTAL,
        requirement="Phase I Environmental Site Assessment review",
        status=ChecklistStatus.PASS,
        comments="No historical dry cleaners or underground storage tanks on site.",
        citation_reference="ESA-2026-TRAVIS-01",
    )
    assert item.status == ChecklistStatus.PASS
    assert item.category == RiskCategory.PHYSICAL_ENVIRONMENTAL


def test_underwriting_memo_synthesis(sample_memo):
    """Full IC memorandum structure and agent committee sign-offs."""
    assert sample_memo.deal_id == "deal-atx-001"
    assert sample_memo.recommendation == MemoRecommendation.APPROVE_WITH_CONDITIONS
    assert len(sample_memo.risk_findings) == 2
    assert len(sample_memo.conditions_precedent) == 2
    assert len(sample_memo.sign_offs) == 1
    assert sample_memo.sign_offs[0].role == AgentRole.INVESTMENT_COMMITTEE_CHAIR
