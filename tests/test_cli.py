"""Comprehensive tests for the cre-swarm CLI interface."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from autonomous_cre_underwriting.cli import cli
from autonomous_cre_underwriting.types.property import PropertyDeal


@pytest.fixture
def runner() -> CliRunner:
    """Click CLI test runner with fixed terminal width."""
    return CliRunner(env={"COLUMNS": "200"})


def test_cli_version_and_help(runner: CliRunner):
    """CLI prints version and top-level commands."""
    res_version = runner.invoke(cli, ["--version"])
    assert res_version.exit_code == 0
    assert "0.1.0" in res_version.output

    res_help = runner.invoke(cli, ["--help"])
    assert res_help.exit_code == 0
    assert "deals" in res_help.output
    assert "underwrite" in res_help.output
    assert "run" in res_help.output
    assert "dcf" in res_help.output
    assert "memo" in res_help.output
    assert "audit" in res_help.output
    assert "portfolio" in res_help.output
    assert "mcp" in res_help.output


def test_deals_sample_list_and_show(runner: CliRunner, tmp_path: Path):
    """deals sample creates deal, list shows it, and show displays specs."""
    storage_dir = str(tmp_path / "store")

    # Create sample
    res_sample = runner.invoke(
        cli,
        [
            "deals",
            "sample",
            "--deal-id",
            "test-deal-100",
            "--title",
            "Austin Crest Residences",
            "--storage-dir",
            storage_dir,
        ],
    )
    assert res_sample.exit_code == 0
    assert "test-deal-100" in res_sample.output

    # List deals
    res_list = runner.invoke(cli, ["deals", "list", "--storage-dir", storage_dir])
    assert res_list.exit_code == 0
    assert "test-deal-100" in res_list.output
    assert "Austin Crest Residences" in res_list.output

    # Show deal
    res_show = runner.invoke(cli, ["deals", "show", "test-deal-100", "--storage-dir", storage_dir])
    assert res_show.exit_code == 0
    assert "Austin Crest Residences" in res_show.output
    assert "Travis" in res_show.output

    # Show missing deal fails
    res_missing = runner.invoke(cli, ["deals", "show", "missing-id", "--storage-dir", storage_dir])
    assert res_missing.exit_code != 0


def test_deals_add_and_delete(runner: CliRunner, sample_deal: PropertyDeal, tmp_path: Path):
    """deals add via flags and JSON file, followed by deletion."""
    storage_dir = str(tmp_path / "store")

    # Add via explicit flags
    res_add = runner.invoke(
        cli,
        [
            "deals",
            "add",
            "--deal-id",
            "deal-manual-01",
            "--title",
            "Manual Office Tower",
            "--property-type",
            "office",
            "--price",
            "18000000",
            "--noi",
            "1100000",
            "--sponsor",
            "Beacon Capital",
            "--storage-dir",
            storage_dir,
        ],
    )
    assert res_add.exit_code == 0
    assert "deal-manual-01" in res_add.output

    # Add via JSON file
    deal_file = tmp_path / "deal_export.json"
    deal_file.write_text(sample_deal.model_dump_json(indent=2), encoding="utf-8")

    res_add_file = runner.invoke(
        cli,
        ["deals", "add", "--file", str(deal_file), "--storage-dir", storage_dir],
    )
    assert res_add_file.exit_code == 0
    assert sample_deal.id in res_add_file.output

    # Delete deal
    res_del = runner.invoke(
        cli,
        ["deals", "delete", "deal-manual-01", "--storage-dir", storage_dir],
    )
    assert res_del.exit_code == 0
    assert "Successfully deleted" in res_del.output

    # Delete missing deal fails
    res_del_missing = runner.invoke(
        cli,
        ["deals", "delete", "non-existent-deal", "--storage-dir", storage_dir],
    )
    assert res_del_missing.exit_code != 0


def test_deals_add_validation_error(runner: CliRunner, tmp_path: Path):
    """deals add without required flags exits with error."""
    res = runner.invoke(
        cli,
        ["deals", "add", "--title", "Missing Details", "--storage-dir", str(tmp_path)],
    )
    assert res.exit_code != 0


def test_underwrite_and_run_workflow(runner: CliRunner, tmp_path: Path):
    """underwrite and run commands execute full multi-agent diligence pipeline."""
    storage_dir = str(tmp_path / "store")
    memo_out = str(tmp_path / "ic_memo.md")

    # Seed deal
    runner.invoke(
        cli,
        [
            "deals",
            "sample",
            "--deal-id",
            "deal-underwrite-01",
            "--storage-dir",
            storage_dir,
        ],
    )

    # Run diligence workflow
    res_uw = runner.invoke(
        cli,
        [
            "underwrite",
            "deal-underwrite-01",
            "--output-memo",
            memo_out,
            "--storage-dir",
            storage_dir,
        ],
    )
    assert res_uw.exit_code == 0
    assert "COMPLETED" in res_uw.output
    assert "IC Recommendation" in res_uw.output
    assert Path(memo_out).exists()
    assert "INVESTMENT COMMITTEE MEMORANDUM" in Path(memo_out).read_text(encoding="utf-8")

    # Run alias 'run' on non-existent deal fails
    res_run_fail = runner.invoke(
        cli,
        ["run", "invalid-id", "--storage-dir", storage_dir],
    )
    assert res_run_fail.exit_code != 0


def test_dcf_compute_and_stress(runner: CliRunner, tmp_path: Path):
    """dcf command runs valuation, supports table/csv/json and --stress flag."""
    storage_dir = str(tmp_path / "store")

    # Seed deal
    runner.invoke(
        cli,
        ["deals", "sample", "--deal-id", "deal-dcf-01", "--storage-dir", storage_dir],
    )

    # Standard table with stress
    res_table = runner.invoke(
        cli,
        ["dcf", "deal-dcf-01", "--stress", "--storage-dir", storage_dir],
    )
    assert res_table.exit_code == 0
    assert "DCF Valuation Summary" in res_table.output
    assert "Downside Stress Testing Scenarios" in res_table.output

    # CSV format
    res_csv = runner.invoke(
        cli,
        ["dcf", "deal-dcf-01", "--format", "csv", "--storage-dir", storage_dir],
    )
    assert res_csv.exit_code == 0
    assert "Potential Gross Revenue" in res_csv.output
    assert "Net Operating Income" in res_csv.output

    # JSON format
    res_json = runner.invoke(
        cli,
        ["dcf", "deal-dcf-01", "--format", "json", "--storage-dir", storage_dir],
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert "annual_cash_flows" in data
    assert "metrics" in data


def test_memo_show_export_and_list(runner: CliRunner, tmp_path: Path):
    """memo commands inspect, export, and list memos."""
    storage_dir = str(tmp_path / "store")
    memo_file = str(tmp_path / "exported_memo.md")

    # Seed deal and run diligence
    runner.invoke(
        cli,
        ["deals", "sample", "--deal-id", "deal-memo-01", "--storage-dir", storage_dir],
    )
    runner.invoke(
        cli,
        ["underwrite", "deal-memo-01", "--storage-dir", storage_dir],
    )

    # Show memo markdown
    res_show = runner.invoke(
        cli,
        ["memo", "show", "deal-memo-01", "--storage-dir", storage_dir],
    )
    assert res_show.exit_code == 0
    assert "INVESTMENT COMMITTEE MEMORANDUM" in res_show.output

    # Show memo JSON
    res_json = runner.invoke(
        cli,
        ["memo", "show", "deal-memo-01", "--json-out", "--storage-dir", storage_dir],
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["deal_id"] == "deal-memo-01"

    # Export memo
    res_export = runner.invoke(
        cli,
        ["memo", "export", "deal-memo-01", memo_file, "--storage-dir", storage_dir],
    )
    assert res_export.exit_code == 0
    assert Path(memo_file).exists()

    # List memos
    res_list = runner.invoke(
        cli,
        ["memo", "list", "--storage-dir", storage_dir],
    )
    assert res_list.exit_code == 0
    assert "deal-memo-01" in res_list.output


def test_audit_verification(runner: CliRunner, tmp_path: Path):
    """audit command verifies cryptographic SHA256 provenance of agent tasks."""
    storage_dir = str(tmp_path / "store")

    # Seed and underwrite
    runner.invoke(
        cli,
        ["deals", "sample", "--deal-id", "deal-audit-01", "--storage-dir", storage_dir],
    )
    runner.invoke(
        cli,
        ["underwrite", "deal-audit-01", "--storage-dir", storage_dir],
    )

    # Audit
    res_audit = runner.invoke(
        cli,
        ["audit", "deal-audit-01", "--storage-dir", storage_dir],
    )
    assert res_audit.exit_code == 0
    assert "VERIFIED (PASS)" in res_audit.output
    assert "Agent Action Provenance Log" in res_audit.output

    # Audit non-existent workflow fails
    res_fail = runner.invoke(
        cli,
        ["audit", "missing-deal", "--storage-dir", storage_dir],
    )
    assert res_fail.exit_code != 0


def test_portfolio_summary_stress_and_policy(runner: CliRunner, tmp_path: Path):
    """portfolio group calculates rollups, macro stress tests, and policy compliance."""
    storage_dir = str(tmp_path / "store")

    # Seed 2 sample deals
    runner.invoke(
        cli,
        [
            "deals",
            "sample",
            "--deal-id",
            "deal-port-01",
            "--title",
            "Asset One",
            "--price",
            "20000000",
            "--noi",
            "1200000",
            "--storage-dir",
            storage_dir,
        ],
    )
    runner.invoke(
        cli,
        [
            "deals",
            "sample",
            "--deal-id",
            "deal-port-02",
            "--title",
            "Asset Two",
            "--price",
            "30000000",
            "--noi",
            "1800000",
            "--storage-dir",
            storage_dir,
        ],
    )

    # Summary
    res_summary = runner.invoke(cli, ["portfolio", "summary", "--storage-dir", storage_dir])
    assert res_summary.exit_code == 0
    assert "Property Count: 2" in res_summary.output
    assert "$50,000,000.00" in res_summary.output

    # Stress
    res_stress = runner.invoke(
        cli,
        [
            "portfolio",
            "stress",
            "--scenario-name",
            "Macro Crash",
            "--rent-shock",
            "-0.08",
            "--storage-dir",
            storage_dir,
        ],
    )
    assert res_stress.exit_code == 0
    assert "Macro Crash" in res_stress.output
    assert "Consolidated NOI" in res_stress.output

    # Policy Check
    res_policy = runner.invoke(
        cli,
        [
            "portfolio",
            "policy-check",
            "deal-port-01",
            "--storage-dir",
            storage_dir,
        ],
    )
    assert res_policy.exit_code == 0
    assert "Policy Hurdle Checks" in res_policy.output


def test_mcp_deed_and_sec_queries(runner: CliRunner):
    """mcp command group queries municipal deed records and SEC EDGAR filings."""
    # Deed query with seller verification
    res_deed = runner.invoke(
        cli,
        [
            "mcp",
            "deed",
            "01-0203-0405-0000",
            "--county",
            "Travis",
            "--state",
            "TX",
            "--seller",
            "Apex Capital Partners LLC",
        ],
    )
    assert res_deed.exit_code == 0
    assert "DOC-2022-0987654" in res_deed.output
    assert "VERIFIED" in res_deed.output

    # SEC query
    res_sec = runner.invoke(cli, ["mcp", "sec", "0001234567"])
    assert res_sec.exit_code == 0
    assert "0001234567-26-000012" in res_sec.output
    assert "Apex REIT Management Corp" in res_sec.output


def test_cli_error_branches_and_empty_states(runner: CliRunner, tmp_path: Path):
    """Test CLI error handling when dealing with empty repositories or non-existent items."""
    empty_dir = str(tmp_path / "empty_store")

    # List deals in empty store
    res_empty_deals = runner.invoke(cli, ["deals", "list", "--storage-dir", empty_dir])
    assert res_empty_deals.exit_code == 0
    assert "No deals found" in res_empty_deals.output

    # List memos in empty store
    res_empty_memos = runner.invoke(cli, ["memo", "list", "--storage-dir", empty_dir])
    assert res_empty_memos.exit_code == 0
    assert "No underwriting memos found" in res_empty_memos.output

    # Portfolio summary in empty store
    res_empty_port = runner.invoke(cli, ["portfolio", "summary", "--storage-dir", empty_dir])
    assert res_empty_port.exit_code == 0
    assert "No deals in repository" in res_empty_port.output

    # Portfolio stress in empty store
    res_empty_stress = runner.invoke(cli, ["portfolio", "stress", "--storage-dir", empty_dir])
    assert res_empty_stress.exit_code == 0
    assert "No deals in repository" in res_empty_stress.output

    # Policy check for non-existent deal aborts
    res_policy_fail = runner.invoke(cli, ["portfolio", "policy-check", "fake-deal", "--storage-dir", empty_dir])
    assert res_policy_fail.exit_code != 0

    # DCF compute for non-existent deal aborts
    res_dcf_fail = runner.invoke(cli, ["dcf", "compute", "fake-deal", "--storage-dir", empty_dir])
    assert res_dcf_fail.exit_code != 0

    # Show memo for non-existent deal aborts
    res_memo_fail = runner.invoke(cli, ["memo", "show", "fake-deal", "--storage-dir", empty_dir])
    assert res_memo_fail.exit_code != 0

    # Export memo for non-existent deal aborts
    res_memo_exp_fail = runner.invoke(cli, ["memo", "export", "fake-deal", str(tmp_path / "out.md"), "--storage-dir", empty_dir])
    assert res_memo_exp_fail.exit_code != 0

    # Audit verification for non-existent deal aborts
    res_audit_fail = runner.invoke(cli, ["audit", "verify", "fake-deal", "--storage-dir", empty_dir])
    assert res_audit_fail.exit_code != 0

    # MCP deed not found
    res_mcp_deed_empty = runner.invoke(cli, ["mcp", "deed", "00-0000-0000", "--county", "Dallas", "--state", "TX"])
    assert res_mcp_deed_empty.exit_code == 0
    assert "No deed records found" in res_mcp_deed_empty.output

    # MCP sec not found
    res_mcp_sec_empty = runner.invoke(cli, ["mcp", "sec", "NONEXISTENT_CIK"])
    assert res_mcp_sec_empty.exit_code == 0
    assert "No SEC filings found" in res_mcp_sec_empty.output


def test_cli_no_auto_advance_and_mcp_audit(runner: CliRunner, tmp_path: Path):
    """Test CLI underwrite with single step --step and mcp deed --audit."""
    store_dir = str(tmp_path / "step_store")

    # Seed deal
    runner.invoke(
        cli,
        ["deals", "sample", "--deal-id", "deal-step-01", "--storage-dir", store_dir],
    )

    # Underwrite with --step
    res_step = runner.invoke(cli, ["underwrite", "deal-step-01", "--step", "--storage-dir", store_dir])
    assert res_step.exit_code == 0
    assert "Diligence Swarm Execution State" in res_step.output

    # MCP deed with --audit flag
    res_deed_audit = runner.invoke(cli, ["mcp", "deed", "01-0203-0405-0000", "--audit"])
    assert res_deed_audit.exit_code == 0
    assert "Chain of Title Audit" in res_deed_audit.output
    assert "VALID" in res_deed_audit.output
