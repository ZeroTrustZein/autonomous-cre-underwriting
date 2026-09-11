"""DCF cash flow schedule and valuation metric exporters (CSV, Markdown, JSON)."""

import csv
import io
from typing import Any, Dict

from autonomous_cre_underwriting.types.financial import DCFValuationResult


class DCFScheduleExporter:
    """Exporters for audit-ready DCF pro-forma schedules and returns."""

    @staticmethod
    def to_csv(result: DCFValuationResult) -> str:
        """Export annual pro-forma cash flows to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")

        headers = [
            "Year",
            "Potential Gross Revenue",
            "Vacancy & Credit Loss",
            "Effective Gross Income",
            "Operating Expenses",
            "Net Operating Income",
            "CapEx Reserves",
            "Debt Service",
            "Unlevered Cash Flow",
            "Levered Cash Flow",
            "Ending Loan Balance",
            "DSCR",
            "Debt Yield",
        ]
        writer.writerow(headers)

        for cf in result.annual_cash_flows:
            writer.writerow(
                [
                    cf.year,
                    f"{cf.potential_gross_revenue:.2f}",
                    f"{cf.vacancy_and_credit_loss:.2f}",
                    f"{cf.effective_gross_income:.2f}",
                    f"{cf.operating_expenses:.2f}",
                    f"{cf.net_operating_income:.2f}",
                    f"{cf.capex_reserves:.2f}",
                    f"{cf.debt_service:.2f}",
                    f"{cf.unlevered_cash_flow:.2f}",
                    f"{cf.levered_cash_flow:.2f}",
                    f"{cf.ending_loan_balance:.2f}",
                    f"{cf.dscr:.2f}",
                    f"{cf.debt_yield:.4f}",
                ]
            )

        return output.getvalue()

    @staticmethod
    def to_markdown_table(result: DCFValuationResult) -> str:
        """Render annual pro-forma cash flows as an ASCII/Markdown table."""
        lines = [
            "| Year | PGR | EGI | OpEx | NOI | Debt Service | Levered CF | Ending Debt | DSCR |",
            "| ---: | --: | --: | ---: | --: | -----------: | ---------: | ----------: | ---: |",
        ]
        for cf in result.annual_cash_flows:
            lines.append(
                f"| {cf.year} | ${cf.potential_gross_revenue:,.0f} | ${cf.effective_gross_income:,.0f} | "
                f"${cf.operating_expenses:,.0f} | ${cf.net_operating_income:,.0f} | "
                f"${cf.debt_service:,.0f} | ${cf.levered_cash_flow:,.0f} | "
                f"${cf.ending_loan_balance:,.0f} | {cf.dscr:.2f}x |"
            )
        return "\n".join(lines)

    @staticmethod
    def to_dict(result: DCFValuationResult) -> Dict[str, Any]:
        """Convert valuation result to serializable dictionary."""
        return result.model_dump(mode="json")
