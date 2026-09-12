"""Command line interface (CLI) for Autonomous CRE Underwriting Swarm.

Provides commands to run agent diligence workflows, inspect deals, execute DCF valuation models,
generate Investment Committee underwriting memos, verify audit trails, and manage portfolios.
"""

import json
import os
from datetime import date
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autonomous_cre_underwriting.agents.swarm import create_agent_swarm
from autonomous_cre_underwriting.engine.dcf import DCFEngine
from autonomous_cre_underwriting.engine.orchestrator import SwarmOrchestrator
from autonomous_cre_underwriting.portfolio.engine import PortfolioUnderwriter
from autonomous_cre_underwriting.portfolio.rules import (
    UnderwritingCriteria,
    UnderwritingRulesEngine,
)
from autonomous_cre_underwriting.reporting.audit import AuditTrailVerifier
from autonomous_cre_underwriting.reporting.exporter import DCFScheduleExporter
from autonomous_cre_underwriting.reporting.memo import MemoExporter
from autonomous_cre_underwriting.storage.repository import DealRepository
from autonomous_cre_underwriting.types.financial import DCFParameters, FinancingAssumptions
from autonomous_cre_underwriting.types.property import (
    DealStatus,
    HistoricalFinancials,
    OperatingExpenses,
    PropertyAddress,
    PropertyDeal,
    PropertyPhysical,
    PropertyType,
    UnitMix,
    UnitSpec,
)

console = Console(width=int(os.environ.get("COLUMNS", "160")))


def get_default_repo(storage_dir: Optional[str] = None) -> DealRepository:
    """Instantiate repository with target persistence directory or default."""
    path = storage_dir or ".data/cre_store"
    repo = DealRepository(persistence_dir=path)
    if Path(path).exists():
        repo.import_from_directory(path)
    return repo


@click.group()
@click.version_option(version="0.1.0", prog_name="cre-swarm")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Autonomous CRE Underwriting Swarm CLI.

    Execute multi-agent diligence, DCF valuations, risk memos, and portfolio rollups.
    """
    ctx.ensure_object(dict)


# =========================================================================
# 1. Deals commands
# =========================================================================


@cli.group(name="deals")
def deals_group() -> None:
    """Manage property deals and pipeline inventory."""
    pass


@deals_group.command(name="list")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
@click.option("--property-type", default=None, help="Filter by property type (multifamily, office, etc.).")
@click.option("--sponsor", default=None, help="Filter by sponsor name.")
def list_deals(storage_dir: Optional[str], property_type: Optional[str], sponsor: Optional[str]) -> None:
    """List registered deals with summary metrics."""
    repo = get_default_repo(storage_dir)
    p_type = PropertyType(property_type.lower()) if property_type else None
    deals = repo.query_deals(property_type=p_type, sponsor=sponsor)

    if not deals:
        console.print("[yellow]No deals found matching the criteria.[/yellow]")
        return

    table = Table(title="Autonomous CRE Deals Pipeline")
    table.add_column("Deal ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold white")
    table.add_column("Type", style="magenta")
    table.add_column("Location", style="blue")
    table.add_column("Target Price", justify="right", style="green")
    table.add_column("In-Place NOI", justify="right", style="green")
    table.add_column("Cap Rate", justify="right", style="yellow")
    table.add_column("Status", style="bold")

    for d in deals:
        loc = f"{d.address.city}, {d.address.state.upper()}"
        table.add_row(
            d.id,
            d.title,
            d.property_type.value,
            loc,
            f"${d.target_purchase_price:,.0f}",
            f"${d.in_place_noi:,.0f}",
            f"{d.target_cap_rate:.2%}",
            d.status.value.upper(),
        )

    console.print(table)


@deals_group.command(name="show")
@click.argument("deal_id")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
def show_deal(deal_id: str, storage_dir: Optional[str]) -> None:
    """Show detailed metadata and physical specifications for a specific deal."""
    repo = get_default_repo(storage_dir)
    deal = repo.get_deal(deal_id)

    if deal is None:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    lines = [
        f"[bold cyan]ID:[/bold cyan] {deal.id}",
        f"[bold]Title:[/bold] {deal.title}",
        f"[bold]Type:[/bold] {deal.property_type.value.upper()} | [bold]Status:[/bold] {deal.status.value.upper()}",
        f"[bold]Address:[/bold] {deal.address.street}, {deal.address.city}, {deal.address.state.upper()} {deal.address.postal_code}, {deal.address.county} County (APN: {deal.address.apn})",
        f"[bold]Sponsor:[/bold] {deal.sponsor_name} | [bold]Broker:[/bold] {deal.broker_name or 'N/A'}",
        f"[bold]Asking Price:[/bold] ${deal.asking_price:,.2f} | [bold]Target Purchase Price:[/bold] ${deal.target_purchase_price:,.2f}",
        f"[bold]In-Place NOI:[/bold] ${deal.in_place_noi:,.2f} (In-Place Yield: {deal.in_place_cap_rate:.2%})",
        f"[bold]Physical:[/bold] {deal.physical.rentable_square_feet:,.0f} RSF, Built {deal.physical.year_built} (Renovated: {deal.physical.year_renovated or 'N/A'}), {deal.physical.stories} stories",
        f"[bold]Units:[/bold] {deal.unit_mix.total_units} total, {deal.unit_mix.total_vacant_units} vacant ({deal.unit_mix.physical_occupancy_rate:.1%} occupancy)",
        f"[bold]Basis PSF / Unit:[/bold] ${deal.price_per_sqft:,.2f}/RSF | ${deal.price_per_unit:,.2f}/Unit",
    ]
    panel = Panel("\n".join(lines), title=f"Property Deal: {deal.title}", border_style="cyan")
    console.print(panel)


@deals_group.command(name="sample")
@click.option("--deal-id", default="deal-sample-001", help="Sample deal identifier.")
@click.option("--title", default="The Austin Ridge Residences", help="Sample property title.")
@click.option("--price", default=25000000.0, type=float, help="Target purchase basis.")
@click.option("--noi", default=1350000.0, type=float, help="In-place Net Operating Income.")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
def create_sample_deal(
    deal_id: str, title: str, price: float, noi: float, storage_dir: Optional[str]
) -> None:
    """Create and persist a realistic sample multifamily property deal."""
    repo = get_default_repo(storage_dir)

    deal = PropertyDeal(
        id=deal_id,
        title=title,
        property_type=PropertyType.MULTIFAMILY,
        status=DealStatus.UNDERWRITING,
        address=PropertyAddress(
            street="500 Congress Avenue",
            city="Austin",
            state="TX",
            postal_code="78701",
            county="Travis",
            apn="01-4450-0100-0000",
        ),
        physical=PropertyPhysical(
            gross_square_feet=110000.0,
            rentable_square_feet=102000.0,
            year_built=2019,
            year_renovated=2023,
            site_area_acres=2.8,
            stories=5,
            parking_spaces=140,
            zoning_code="CBD-MF",
            flood_zone="X",
        ),
        unit_mix=UnitMix(
            items=[
                UnitSpec(
                    unit_type="1B/1B",
                    count=65,
                    square_feet=760.0,
                    in_place_rent=1650.0,
                    market_rent=1850.0,
                    vacant_units=3,
                ),
                UnitSpec(
                    unit_type="2B/2B",
                    count=45,
                    square_feet=1120.0,
                    in_place_rent=2250.0,
                    market_rent=2500.0,
                    vacant_units=2,
                ),
            ]
        ),
        asking_price=price * 1.05,
        target_purchase_price=price,
        in_place_noi=noi,
        sponsor_name="Apex Capital Partners",
        broker_name="Eastdil Secured",
        target_closing_date=date(2026, 11, 30),
        historical_financials=[
            HistoricalFinancials(
                period_label="T12",
                gross_potential_rent=2350000.0,
                vacancy_credit_loss=115000.0,
                concessions=25000.0,
                other_income=90000.0,
                expenses=OperatingExpenses(
                    property_taxes=290000.0,
                    insurance=98000.0,
                    utilities=115000.0,
                    repairs_maintenance=88000.0,
                    management_fees=78000.0,
                    payroll=135000.0,
                    marketing_leasing=26000.0,
                    general_admin=36000.0,
                    capex_reserve=36000.0,
                ),
            )
        ],
    )

    repo.save_deal(deal)
    if repo.persistence_dir:
        repo.export_to_directory()

    console.print(f"[green]Successfully generated and stored sample deal:[/green] [bold]{deal.id}[/bold] ({deal.title})")


@deals_group.command(name="add")
@click.option("--file", "file_path", type=click.Path(exists=True), help="Load PropertyDeal directly from a JSON file.")
@click.option("--deal-id", default=None, help="Deal ID (default auto-generated).")
@click.option("--title", default=None, help="Property title.")
@click.option("--property-type", "p_type", default="multifamily", help="Property asset class.")
@click.option("--price", type=float, default=None, help="Target purchase price basis.")
@click.option("--noi", type=float, default=None, help="In-place annual Net Operating Income.")
@click.option("--sponsor", default=None, help="Sponsor or borrower entity name.")
@click.option("--city", default="Austin", help="City location.")
@click.option("--state", default="TX", help="State code.")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
def add_deal(
    file_path: Optional[str],
    deal_id: Optional[str],
    title: Optional[str],
    p_type: str,
    price: Optional[float],
    noi: Optional[float],
    sponsor: Optional[str],
    city: str,
    state: str,
    storage_dir: Optional[str],
) -> None:
    """Add a property deal from JSON file or command line options."""
    repo = get_default_repo(storage_dir)

    if file_path:
        p = Path(file_path)
        data = json.loads(p.read_text(encoding="utf-8"))
        deal = PropertyDeal.model_validate(data)
    else:
        if not title or price is None or noi is None or not sponsor:
            console.print("[red]Error: When not using --file, --title, --price, --noi, and --sponsor are required.[/red]")
            raise click.Abort()

        d_id = deal_id or f"deal-{title.lower().replace(' ', '-')[:16]}"
        deal = PropertyDeal(
            id=d_id,
            title=title,
            property_type=PropertyType(p_type.lower()),
            status=DealStatus.UNDERWRITING,
            address=PropertyAddress(
                street="100 Main Street",
                city=city,
                state=state,
                postal_code="78701",
                county="Travis",
                apn="01-0001-0000",
            ),
            physical=PropertyPhysical(
                gross_square_feet=50000.0,
                rentable_square_feet=46000.0,
                year_built=2020,
                site_area_acres=2.0,
                stories=4,
                parking_spaces=80,
                zoning_code="COMMERCIAL",
                flood_zone="X",
            ),
            unit_mix=UnitMix(
                items=[
                    UnitSpec(
                        unit_type="Standard",
                        count=50,
                        square_feet=920.0,
                        in_place_rent=noi / 600.0,
                        market_rent=(noi / 600.0) * 1.1,
                        vacant_units=2,
                    )
                ]
            ),
            asking_price=price * 1.05,
            target_purchase_price=price,
            in_place_noi=noi,
            sponsor_name=sponsor,
        )

    repo.save_deal(deal)
    if repo.persistence_dir:
        repo.export_to_directory()

    console.print(f"[green]Successfully added deal:[/green] [bold]{deal.id}[/bold] ({deal.title})")


@deals_group.command(name="delete")
@click.argument("deal_id")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
def delete_deal(deal_id: str, storage_dir: Optional[str]) -> None:
    """Delete a property deal from repository by ID."""
    repo = get_default_repo(storage_dir)
    deleted = repo.delete_deal(deal_id)

    if not deleted:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    if repo.persistence_dir:
        repo.export_to_directory()

    console.print(f"[green]Successfully deleted deal:[/green] [bold]{deal_id}[/bold]")


# =========================================================================
# 2. Diligence Swarm Orchestration
# =========================================================================


@cli.command(name="underwrite")
@click.argument("deal_id")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
@click.option("--output-memo", default=None, help="Path to write generated markdown memo.")
@click.option("--auto-advance/--step", default=True, help="Execute all workflow tasks or single step.")
def underwrite_deal(deal_id: str, storage_dir: Optional[str], output_memo: Optional[str], auto_advance: bool) -> None:
    """Run autonomous 6-agent diligence swarm workflow for a deal."""
    repo = get_default_repo(storage_dir)
    deal = repo.get_deal(deal_id)

    if deal is None:
        console.print(f"[red]Error: Deal '{deal_id}' not found. Create one with `cre-swarm deals sample` first.[/red]")
        raise click.Abort()

    console.print(f"[bold cyan]Initializing Swarm Diligence Workflow for:[/bold cyan] {deal.title} ({deal.id})")

    orchestrator = SwarmOrchestrator()
    create_agent_swarm(orchestrator=orchestrator)

    workflow_state = orchestrator.initialize_workflow(deal)
    console.print(f"[dim]Workflow ID:[/dim] [cyan]{workflow_state.id}[/cyan] with [bold]{len(workflow_state.tasks)}[/bold] DAG tasks.")

    with console.status("[bold green]Executing agent swarm diligence pipeline..."):
        if auto_advance:
            while not workflow_state.is_terminal:
                workflow_state = orchestrator.advance_workflow(workflow_state.id)
        else:
            workflow_state = orchestrator.advance_workflow(workflow_state.id)

    # Display task results table
    table = Table(title=f"Diligence Swarm Execution State: {deal.title}")
    table.add_column("Task ID", style="dim", no_wrap=True)
    table.add_column("Agent Role", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Duration (ms)", justify="right")
    table.add_column("Description", style="white")

    for t in workflow_state.tasks:
        status_color = "green" if t.status.value == "completed" else "red" if t.status.value == "failed" else "yellow"
        table.add_row(
            t.id[:8],
            t.role.value,
            f"[{status_color}]{t.status.value.upper()}[/{status_color}]",
            f"{t.execution_time_ms:.1f}",
            t.description,
        )

    console.print(table)

    # Save outputs if completed
    if workflow_state.is_terminal:
        memo = orchestrator.generate_underwriting_memo(deal.id)
        repo.save_memo(memo)
        repo.save_workflow(workflow_state)
        dcf_result = orchestrator.dcf_results.get(deal.id)
        if dcf_result:
            repo.save_valuation(dcf_result)

        if repo.persistence_dir:
            repo.export_to_directory()

        rec_style = "green" if "approve" in memo.recommendation.value.lower() else "red"
        console.print(
            f"\n[bold]IC Recommendation:[/bold] [{rec_style}]{memo.recommendation.value.upper()}[/{rec_style}] | "
            f"[bold]Levered IRR:[/bold] {memo.valuation_summary.levered_irr:.2%} | "
            f"[bold]Equity Multiple:[/bold] {memo.valuation_summary.equity_multiple:.2f}x | "
            f"[bold]NPV:[/bold] ${memo.valuation_summary.net_present_value:,.0f}"
        )

        if output_memo:
            out_p = Path(output_memo)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(MemoExporter.to_markdown(memo), encoding="utf-8")
            console.print(f"[green]Full Investment Committee Memorandum exported to:[/green] [bold]{output_memo}[/bold]")


# =========================================================================
# 3. DCF Financial Modeling
# =========================================================================


@cli.command(name="dcf")
@click.argument("deal_id")
@click.option("--holding-period", default=5, type=int, help="Holding period in years.")
@click.option("--exit-cap", default=0.0575, type=float, help="Exit capitalization rate.")
@click.option("--discount-rate", default=0.09, type=float, help="Discount rate for NPV.")
@click.option("--ltv", default=0.65, type=float, help="Loan to value ratio.")
@click.option("--interest-rate", default=0.0625, type=float, help="Senior loan annual interest rate.")
@click.option("--stress", is_flag=True, help="Also run downside stress testing scenarios.")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
@click.option("--format", "export_fmt", type=click.Choice(["table", "csv", "json"], case_sensitive=False), default="table")
def run_dcf(
    deal_id: str,
    holding_period: int,
    exit_cap: float,
    discount_rate: float,
    ltv: float,
    interest_rate: float,
    stress: bool,
    storage_dir: Optional[str],
    export_fmt: str,
) -> None:
    """Execute audit-ready DCF pro-forma financial model for a deal."""
    repo = get_default_repo(storage_dir)
    deal = repo.get_deal(deal_id)

    if deal is None:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    loan_amount = deal.target_purchase_price * ltv
    financing = FinancingAssumptions(
        loan_amount=loan_amount,
        interest_rate=interest_rate,
        term_years=holding_period + 2,
        amortization_years=30,
        interest_only_years=2,
    )
    params = DCFParameters(
        holding_period_years=holding_period,
        exit_cap_rate=exit_cap,
        discount_rate=discount_rate,
        annual_rent_growth=0.03,
        annual_opex_growth=0.025,
    )

    engine = DCFEngine()
    t12 = deal.historical_financials[-1] if deal.historical_financials else None
    result = engine.compute_valuation(deal=deal, parameters=params, financing=financing, t12=t12)
    repo.save_valuation(result)

    if export_fmt.lower() == "csv":
        click.echo(DCFScheduleExporter.to_csv(result))
    elif export_fmt.lower() == "json":
        click.echo(json.dumps(DCFScheduleExporter.to_dict(result), indent=2))
    else:
        # Markdown & summary tables
        console.print(Panel(
            f"[bold]Purchase Price:[/bold] ${result.metrics.purchase_price:,.2f} | [bold]Equity:[/bold] ${result.metrics.equity_invested:,.2f} | [bold]Loan:[/bold] ${financing.loan_amount:,.2f}\n"
            f"[bold]Levered IRR:[/bold] {result.metrics.levered_irr:.2%} | [bold]Unlevered IRR:[/bold] {result.metrics.unlevered_irr:.2%} | [bold]EM:[/bold] {result.metrics.equity_multiple:.2f}x\n"
            f"[bold]Net Present Value (NPV):[/bold] ${result.metrics.net_present_value:,.2f} | [bold]Average DSCR:[/bold] {result.metrics.average_dscr:.2f}x (Min: {result.metrics.min_dscr_observed:.2f}x)\n"
            f"[bold]Gross Exit Price:[/bold] ${result.metrics.gross_exit_sales_price:,.2f} | [bold]Model Checksum:[/bold] [dim]{result.model_checksum}[/dim]",
            title=f"DCF Valuation Summary: {deal.title}",
            border_style="green",
        ))

        table = Table(title="Annual Pro-Forma Cash Flow Schedule")
        table.add_column("Year", justify="right", style="cyan")
        table.add_column("PGR", justify="right")
        table.add_column("EGI", justify="right")
        table.add_column("OpEx", justify="right")
        table.add_column("NOI", justify="right", style="green")
        table.add_column("Debt Service", justify="right", style="red")
        table.add_column("Levered CF", justify="right", style="bold green")
        table.add_column("Ending Loan", justify="right")
        table.add_column("DSCR", justify="right", style="yellow")

        for cf in result.annual_cash_flows:
            table.add_row(
                str(cf.year),
                f"${cf.potential_gross_revenue:,.0f}",
                f"${cf.effective_gross_income:,.0f}",
                f"${cf.operating_expenses:,.0f}",
                f"${cf.net_operating_income:,.0f}",
                f"${cf.debt_service:,.0f}",
                f"${cf.levered_cash_flow:,.0f}",
                f"${cf.ending_loan_balance:,.0f}",
                f"{cf.dscr:.2f}x",
            )
        console.print(table)

        if stress:
            stresses = [
                engine.stress_test(
                    deal=deal,
                    parameters=params,
                    financing=financing,
                    name="Mild Stagflation Shock",
                    rent_shock_pct=-0.03,
                    vacancy_shock_pct=0.03,
                    opex_shock_pct=0.04,
                    exit_cap_expansion_bps=25,
                ),
                engine.stress_test(
                    deal=deal,
                    parameters=params,
                    financing=financing,
                    name="Severe Liquidity Crunch",
                    rent_shock_pct=-0.06,
                    vacancy_shock_pct=0.07,
                    opex_shock_pct=0.08,
                    exit_cap_expansion_bps=50,
                ),
            ]
            stress_table = Table(title="Downside Stress Testing Scenarios")
            stress_table.add_column("Scenario", style="cyan")
            stress_table.add_column("Rent Shock", justify="right")
            stress_table.add_column("Vacancy Shock", justify="right")
            stress_table.add_column("OpEx Shock", justify="right")
            stress_table.add_column("Exit Cap (+bps)", justify="right")
            stress_table.add_column("Resultant IRR", justify="right", style="green")
            stress_table.add_column("Min DSCR", justify="right", style="yellow")
            stress_table.add_column("Breached", justify="center")

            for sc in stresses:
                breached_str = "[red]YES[/red]" if sc.covenant_breached else "[green]NO[/green]"
                stress_table.add_row(
                    sc.name,
                    f"{sc.rent_shock_pct:+.1%}",
                    f"{sc.vacancy_shock_pct:+.1%}",
                    f"{sc.opex_shock_pct:+.1%}",
                    f"+{sc.exit_cap_expansion_bps} bps",
                    f"{sc.resultant_irr:.2%}",
                    f"{sc.min_dscr_observed:.2f}x",
                    breached_str,
                )
            console.print(stress_table)


# =========================================================================
# 4. Underwriting Memos & Reporting
# =========================================================================


@cli.group(name="memo")
def memo_group() -> None:
    """Inspect and export Investment Committee Underwriting Memos."""
    pass


@memo_group.command(name="show")
@click.argument("deal_id")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
@click.option("--json-out", is_flag=True, help="Display as raw JSON.")
def show_memo(deal_id: str, storage_dir: Optional[str], json_out: bool) -> None:
    """View generated Investment Committee Underwriting Memo for a deal."""
    repo = get_default_repo(storage_dir)
    memo = repo.get_memo(deal_id)

    if memo is None:
        # If memo not found directly, check if deal exists and synthesize
        deal = repo.get_deal(deal_id)
        if deal is None:
            console.print(f"[red]Error: Neither deal nor memo found for ID '{deal_id}'.[/red]")
            raise click.Abort()

        console.print(f"[yellow]No pre-existing memo for '{deal_id}'. Generating synthesized memo...[/yellow]")
        orch = SwarmOrchestrator()
        orch.deals[deal.id] = deal
        memo = orch.generate_underwriting_memo(deal_id)
        repo.save_memo(memo)

    if json_out:
        click.echo(MemoExporter.to_json(memo))
    else:
        console.print(MemoExporter.to_markdown(memo))


@memo_group.command(name="export")
@click.argument("deal_id")
@click.argument("output_path", type=click.Path(writable=True))
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
def export_memo(deal_id: str, output_path: str, storage_dir: Optional[str]) -> None:
    """Export Investment Committee memo to markdown file."""
    repo = get_default_repo(storage_dir)
    memo = repo.get_memo(deal_id)

    if memo is None:
        deal = repo.get_deal(deal_id)
        if deal is None:
            console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
            raise click.Abort()
        orch = SwarmOrchestrator()
        orch.deals[deal.id] = deal
        memo = orch.generate_underwriting_memo(deal_id)
        repo.save_memo(memo)

    md_content = MemoExporter.to_markdown(memo)
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(md_content, encoding="utf-8")
    console.print(f"[green]Exported Underwriting Memo to:[/green] [bold]{output_path}[/bold]")


@memo_group.command(name="list")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
def list_memos(storage_dir: Optional[str]) -> None:
    """List all generated Investment Committee underwriting memos."""
    repo = get_default_repo(storage_dir)
    memos = repo.list_memos()

    if not memos:
        console.print("[yellow]No underwriting memos found in repository.[/yellow]")
        return

    table = Table(title="Investment Committee Underwriting Memos")
    table.add_column("Deal ID", style="cyan")
    table.add_column("Title", style="bold white")
    table.add_column("Recommendation", style="bold")
    table.add_column("Levered IRR", justify="right", style="green")
    table.add_column("Equity Multiple", justify="right")
    table.add_column("Min DSCR", justify="right", style="yellow")
    table.add_column("Risks Flagged", justify="right")

    for m in memos:
        rec_color = "green" if "approve" in m.recommendation.value.lower() else "red"
        table.add_row(
            m.deal_id,
            m.deal_title,
            f"[{rec_color}]{m.recommendation.value.upper()}[/{rec_color}]",
            f"{m.valuation_summary.levered_irr:.2%}",
            f"{m.valuation_summary.equity_multiple:.2f}x",
            f"{m.valuation_summary.min_dscr_observed:.2f}x",
            str(len(m.risk_findings)),
        )

    console.print(table)


# =========================================================================
# 5. Audit Trail Verification
# =========================================================================


@cli.command(name="audit")
@click.argument("deal_id")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
def audit_deal(deal_id: str, storage_dir: Optional[str]) -> None:
    """Verify cryptographic provenance and SHA256 hashes of agent audit trail."""
    repo = get_default_repo(storage_dir)
    workflow = repo.get_workflow_for_deal(deal_id)

    if workflow is None:
        console.print(f"[red]Error: No workflow state found for deal '{deal_id}'. Run `cre-swarm underwrite {deal_id}` first.[/red]")
        raise click.Abort()

    verifier = AuditTrailVerifier()
    verification = verifier.verify_workflow(workflow)

    is_valid = verification["audit_valid"]
    status_str = "[bold green]VERIFIED (PASS)[/bold green]" if is_valid else "[bold red]TAMPERED / INCOMPLETE (FAIL)[/bold red]"

    panel_text = (
        f"[bold]Workflow ID:[/bold] {verification['workflow_id']}\n"
        f"[bold]Deal ID:[/bold] {verification['deal_id']}\n"
        f"[bold]Total Audit Entries:[/bold] {verification['total_entries']}\n"
        f"[bold]Valid Entries:[/bold] {verification['valid_entries']}\n"
        f"[bold]Chronological Integrity:[/bold] {verification['chronological']}\n"
        f"[bold]Integrity Status:[/bold] {status_str}"
    )
    console.print(Panel(panel_text, title=f"Cryptographic Audit Verification: {deal_id}", border_style="green" if is_valid else "red"))

    table = Table(title="Agent Action Provenance Log")
    table.add_column("Entry ID", style="dim", no_wrap=True)
    table.add_column("Role", style="magenta")
    table.add_column("Action Taken", style="cyan")
    table.add_column("Input Digest", style="dim")
    table.add_column("Justification", style="white")

    for entry in workflow.audit_trail:
        table.add_row(
            entry.entry_id[:8],
            entry.role.value,
            entry.action_taken,
            entry.input_hash[:20] + "...",
            entry.justification,
        )

    console.print(table)


# =========================================================================
# 6. Portfolio & Policy Compliance
# =========================================================================


@cli.group(name="portfolio")
def portfolio_group() -> None:
    """Aggregate multi-asset underwriting books and stress test portfolios."""
    pass


@portfolio_group.command(name="summary")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
def portfolio_summary(storage_dir: Optional[str]) -> None:
    """Calculate consolidated portfolio book metrics, debt yield, and concentration."""
    repo = get_default_repo(storage_dir)
    deals = repo.list_deals()

    if not deals:
        console.print("[yellow]No deals in repository. Create deals first.[/yellow]")
        return

    portfolio = PortfolioUnderwriter()
    for d in deals:
        val = repo.get_valuation(d.id)
        portfolio.add_deal(d, dcf_result=val)

    summary = portfolio.compute_portfolio_summary()
    concentration = portfolio.compute_concentration()

    panel_text = (
        f"[bold]Property Count:[/bold] {summary.property_count}\n"
        f"[bold]Total Purchase Price:[/bold] ${summary.total_purchase_price:,.2f}\n"
        f"[bold]Total Equity Invested:[/bold] ${summary.total_equity:,.2f}\n"
        f"[bold]Total Debt Balance:[/bold] ${summary.total_debt:,.2f} (Portfolio LTV: {summary.portfolio_ltv:.1%})\n"
        f"[bold]Consolidated NOI:[/bold] ${summary.total_noi:,.2f}\n"
        f"[bold]Weighted Cap Rate:[/bold] {summary.weighted_avg_cap_rate:.2%}\n"
        f"[bold]Weighted DSCR:[/bold] {summary.weighted_avg_dscr:.2f}x | [bold]Debt Yield:[/bold] {summary.portfolio_debt_yield:.2%}\n"
        f"[bold]Top Asset Concentration:[/bold] {concentration.top_asset_concentration_pct:.1%}"
    )
    console.print(Panel(panel_text, title="Consolidated Portfolio Book Summary", border_style="cyan"))

    # Asset Type Breakdown Table
    table = Table(title="Concentration by Property Type")
    table.add_column("Asset Class", style="magenta")
    table.add_column("Share of Basis", justify="right", style="green")
    for pt, pct in concentration.by_property_type.items():
        table.add_row(pt.capitalize(), f"{pct:.1%}")
    console.print(table)


@portfolio_group.command(name="stress")
@click.option("--scenario-name", default="Severe Stagflation", help="Scenario identifier.")
@click.option("--rent-shock", default=-0.05, type=float, help="Percentage rent contraction (e.g. -0.05).")
@click.option("--opex-shock", default=0.06, type=float, help="Percentage opex inflation (e.g. 0.06).")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
def portfolio_stress(scenario_name: str, rent_shock: float, opex_shock: float, storage_dir: Optional[str]) -> None:
    """Simulate macro downturn and count covenant breaches across portfolio."""
    repo = get_default_repo(storage_dir)
    deals = repo.list_deals()

    if not deals:
        console.print("[yellow]No deals in repository to stress test.[/yellow]")
        return

    portfolio = PortfolioUnderwriter()
    for d in deals:
        val = repo.get_valuation(d.id)
        portfolio.add_deal(d, dcf_result=val)

    stress_result = portfolio.stress_portfolio(
        name=scenario_name,
        rent_shock_pct=rent_shock,
        opex_shock_pct=opex_shock,
    )

    breach_style = "bold red" if stress_result.covenant_breaches_count > 0 else "bold green"
    text = (
        f"[bold]Scenario:[/bold] {stress_result.scenario_name}\n"
        f"[bold]Base Consolidated NOI:[/bold] ${stress_result.base_noi:,.2f}\n"
        f"[bold]Stressed Consolidated NOI:[/bold] ${stress_result.stressed_noi:,.2f} ([red]{stress_result.noi_drop_pct:+.1%}[/red])\n"
        f"[bold]Stressed DSCR:[/bold] {stress_result.stressed_dscr:.2f}x\n"
        f"[bold]Covenant Breaches:[/bold] [{breach_style}]{stress_result.covenant_breaches_count} asset(s)[/{breach_style}]"
    )
    console.print(Panel(text, title=f"Portfolio Macro Stress Test: {scenario_name}", border_style="red" if stress_result.covenant_breaches_count > 0 else "green"))


@portfolio_group.command(name="policy-check")
@click.argument("deal_id")
@click.option("--min-irr", default=0.12, type=float, help="Policy hurdle for levered IRR.")
@click.option("--min-dscr", default=1.25, type=float, help="Policy hurdle for minimum DSCR.")
@click.option("--max-ltv", default=0.70, type=float, help="Policy limit for leverage.")
@click.option("--storage-dir", default=None, help="Custom persistence directory.")
def policy_check(deal_id: str, min_irr: float, min_dscr: float, max_ltv: float, storage_dir: Optional[str]) -> None:
    """Evaluate deal against investment criteria and covenant policy limits."""
    repo = get_default_repo(storage_dir)
    deal = repo.get_deal(deal_id)

    if deal is None:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    val = repo.get_valuation(deal_id)
    if val is None:
        orch = SwarmOrchestrator()
        val = orch.dcf_engine.compute_valuation(
            deal=deal,
            parameters=DCFParameters(exit_cap_rate=max(0.045, deal.target_cap_rate + 0.005)),
            financing=FinancingAssumptions(
                loan_amount=deal.target_purchase_price * 0.65,
                interest_rate=0.0625,
            ),
        )

    criteria = UnderwritingCriteria(
        min_levered_irr=min_irr,
        min_dscr=min_dscr,
        max_ltv=max_ltv,
    )
    rules_engine = UnderwritingRulesEngine(criteria=criteria)
    results = rules_engine.evaluate_deal(deal, val)

    all_passed = all(r.passed for r in results)
    status_label = "[bold green]POLICY COMPLIANT (PASS)[/bold green]" if all_passed else "[bold red]COVENANT VIOLATIONS (FAIL)[/bold red]"

    console.print(f"\n[bold]Underwriting Policy Evaluation for:[/bold] {deal.title} — {status_label}\n")

    table = Table(title="Policy Hurdle Checks")
    table.add_column("Rule", style="cyan")
    table.add_column("Hurdle", justify="right")
    table.add_column("Actual", justify="right")
    table.add_column("Result", style="bold")
    table.add_column("Detail", style="dim")

    for r in results:
        res_str = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        table.add_row(
            r.rule_name,
            f"{r.threshold:.2f}",
            f"{r.actual_value:.2f}",
            res_str,
            r.detail,
        )

    console.print(table)


# =========================================================================
# 7. Model Context Protocol (MCP) Ingestion
# =========================================================================


@cli.group(name="mcp")
def mcp_group() -> None:
    """Query external municipal records and SEC filings via MCP protocols."""
    pass


@mcp_group.command(name="deed")
@click.argument("apn")
@click.option("--county", default="Travis", help="County jurisdiction name.")
@click.option("--state", default="TX", help="State jurisdiction code.")
@click.option("--seller", default=None, help="Verify recorded grantee matches seller.")
@click.option("--audit", is_flag=True, default=False, help="Perform full chain-of-title continuity audit.")
def mcp_deed(apn: str, county: str, state: str, seller: Optional[str], audit: bool = False) -> None:
    """Fetch municipal deed records and verify chain of title for an APN."""
    from autonomous_cre_underwriting.mcp.municipal_deed import DeedIngestor
    from autonomous_cre_underwriting.types.ingestion import DeedRecord, DeedType

    demo_deed = DeedRecord(
        parcel_number="01-0203-0405-0000",
        document_number="DOC-2022-0987654",
        recording_date=date(2022, 6, 15),
        deed_type=DeedType.SPECIAL_WARRANTY_DEED,
        grantor="Hill Country Holdings LP",
        grantee="Apex Capital Partners LLC",
        consideration_amount=21500000.0,
        transfer_tax=21500.0,
        legal_description="Lot 4, Block B, Austin Downtown Subdivision No. 2",
        county_name="Travis",
        source_url="https://recorder.traviscountytx.gov/deed/DOC-2022-0987654",
        verified=True,
    )
    ingestor = DeedIngestor(seed_records=[demo_deed])
    records = ingestor.fetch_deed_records(apn, county, state)

    if not records:
        console.print(f"[yellow]No deed records found for APN '{apn}' in {county}, {state}.[/yellow]")
        return

    table = Table(title=f"Municipal Conveyance History: APN {apn}")
    table.add_column("Document #", style="cyan")
    table.add_column("Date", style="blue")
    table.add_column("Deed Type", style="magenta")
    table.add_column("Grantor", style="white")
    table.add_column("Grantee", style="bold white")
    table.add_column("Consideration", justify="right", style="green")
    table.add_column("Verified", justify="center")

    for r in records:
        table.add_row(
            r.document_number,
            str(r.recording_date),
            r.deed_type.value,
            r.grantor,
            r.grantee,
            f"${r.consideration_amount:,.0f}",
            "[green]YES[/green]" if r.verified else "[red]NO[/red]",
        )
    console.print(table)

    if seller:
        is_verified = ingestor.verify_chain_of_title(apn, seller)
        status_str = "[bold green]VERIFIED[/bold green]" if is_verified else "[bold red]CHAIN OF TITLE GAP / MISMATCH[/bold red]"
        console.print(f"\nChain of Title Verification for Seller '[bold]{seller}[/bold]': {status_str}")

    if audit:
        audit_res = ingestor.audit_chain_of_title(apn)
        status_str = "[bold green]VALID[/bold green]" if audit_res["chain_valid"] else "[bold red]CHAIN OF TITLE ISSUES DETECTED[/bold red]"
        console.print(f"\nChain of Title Audit: {status_str}")
        for issue in audit_res.get("issues", []):
            console.print(f"  [yellow]•[/yellow] {issue}")
        if audit_res.get("latest_owner"):
            console.print(f"  [bold]Latest Recorded Grantee:[/bold] {audit_res['latest_owner']}")


@mcp_group.command(name="sec")
@click.argument("cik_or_ticker")
def mcp_sec(cik_or_ticker: str) -> None:
    """Query SEC EDGAR corporate filings and risk disclosures for a sponsor or tenant."""
    from autonomous_cre_underwriting.mcp.sec_edgar import SECIngestor
    from autonomous_cre_underwriting.types.ingestion import (
        SECFiling,
        SECFilingType,
        SECRiskMention,
        SECRiskTopic,
    )

    demo_filing = SECFiling(
        accession_number="0001234567-26-000012",
        cik="0001234567",
        company_name="Apex REIT Management Corp",
        form_type=SECFilingType.FORM_10K,
        filing_date=date(2026, 3, 1),
        period_end_date=date(2025, 12, 31),
        report_url="https://www.sec.gov/edgar/data/1234567/000123456726000012.txt",
        risk_mentions=[
            SECRiskMention(
                topic=SECRiskTopic.REFINANCING_RISK,
                excerpt="The company holds $45M of floating debt subject to SOFR reset in Q4 2026.",
                item_section="Item 1A. Risk Factors",
                severity_score=0.75,
                relevance_score=0.88,
            )
        ],
    )
    ingestor = SECIngestor(seed_filings=[demo_filing])
    filings = ingestor.search_filings(cik_or_ticker)

    if not filings:
        console.print(f"[yellow]No SEC filings found for '{cik_or_ticker}'.[/yellow]")
        return

    table = Table(title=f"SEC EDGAR Filings: {cik_or_ticker.upper()}")
    table.add_column("Accession #", style="cyan")
    table.add_column("Company", style="bold white")
    table.add_column("Form", style="magenta")
    table.add_column("Filing Date", style="blue")
    table.add_column("Risks Mentions", justify="right", style="yellow")

    for f in filings:
        table.add_row(
            f.accession_number,
            f.company_name,
            f.form_type.value,
            str(f.filing_date),
            str(len(f.risk_mentions)),
        )
    console.print(table)


# Register convenience shortcut aliases
cli.add_command(underwrite_deal, name="run")


if __name__ == "__main__":
    cli()
