"""Tests for workflow commands: discover pipeline and enrich-list."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx
from click.testing import CliRunner

from discolike.cli import cli
from tests.conftest import load_fixture

BASE_URL = "https://api.discolike.com/v1"


def _mock_discover_workflow(
    account_fixture: dict | None = None,
    extract_fixture: dict | None = None,
    count_response: dict | None = None,
    discover_fixture: dict | None = None,
    profile_fixture: dict | None = None,
    exclusion_fixture: dict | None = None,
) -> None:
    """Set up all mocks for the 8-step workflow."""
    account = account_fixture or load_fixture("account_status.json")
    extract = extract_fixture or load_fixture("extract_result.json")
    count_resp = count_response or {"count": 1500}
    discover = discover_fixture or load_fixture("discover_results.json")
    profile = profile_fixture or load_fixture("business_profile.json")
    exclusion = exclusion_fixture or load_fixture("save_exclusion.json")

    # Step 1: account status
    respx.get(f"{BASE_URL}/usage").mock(
        return_value=httpx.Response(200, json=account)
    )
    # Step 2: extract
    respx.get(f"{BASE_URL}/extract").mock(
        return_value=httpx.Response(200, json=extract)
    )
    # Step 3: count
    respx.get(f"{BASE_URL}/count").mock(
        return_value=httpx.Response(200, json=count_resp)
    )
    # Steps 4+5: discover (called twice -- validation + full)
    respx.get(f"{BASE_URL}/discover").mock(
        return_value=httpx.Response(200, json=discover)
    )
    # Step 6: business profiles
    respx.get(f"{BASE_URL}/bizdata").mock(
        return_value=httpx.Response(200, json=profile)
    )
    # Step 8: save exclusion
    respx.post(f"{BASE_URL}/queries/exclusion-list").mock(
        return_value=httpx.Response(200, json=exclusion)
    )


class TestWorkflowDiscover:
    """Tests for the workflow discover command."""

    @respx.mock
    def test_full_workflow_creates_output(self, tmp_path: Path) -> None:
        _mock_discover_workflow()
        output_file = tmp_path / "results.csv"
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "discover",
                "--seed", "leadgrow.ai",
                "--no-confirm",
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0, f"Failed with: {result.stderr}\n{result.output}"
        assert output_file.exists()
        content = output_file.read_text()
        assert "example-agency.com" in content

    @respx.mock
    def test_workflow_json_output(self, tmp_path: Path) -> None:
        _mock_discover_workflow()
        output_file = tmp_path / "results.json"
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "discover",
                "--seed", "leadgrow.ai",
                "--no-confirm",
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0, f"Failed with: {result.stderr}\n{result.output}"
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["count"] == 2
        assert len(data["records"]) == 2

    @respx.mock
    def test_workflow_with_country_filter(self, tmp_path: Path) -> None:
        _mock_discover_workflow()
        output_file = tmp_path / "results.csv"
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "discover",
                "--seed", "leadgrow.ai",
                "--country", "US",
                "--no-confirm",
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0, f"Failed with: {result.stderr}\n{result.output}"
        assert output_file.exists()

    @respx.mock
    def test_workflow_with_save_exclusion(self, tmp_path: Path) -> None:
        _mock_discover_workflow()
        output_file = tmp_path / "results.csv"
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "discover",
                "--seed", "leadgrow.ai",
                "--no-confirm",
                "--save-exclusion",
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0, f"Failed with: {result.stderr}\n{result.output}"
        # Verify exclusion save was called
        exclusion_calls = [
            c for c in respx.calls
            if "/queries/exclusion-list" in str(c.request.url)
        ]
        assert len(exclusion_calls) == 1

    @respx.mock
    def test_workflow_zero_count_exits_early(self, tmp_path: Path) -> None:
        _mock_discover_workflow(count_response={"count": 0})
        output_file = tmp_path / "results.csv"
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "discover",
                "--seed", "niche.com",
                "--no-confirm",
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0
        # Output file should NOT be created (workflow exits early)
        assert not output_file.exists()

    @respx.mock
    def test_workflow_correct_api_call_sequence(self, tmp_path: Path) -> None:
        """Verify the correct sequence and count of API calls."""
        _mock_discover_workflow()
        output_file = tmp_path / "results.csv"
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "discover",
                "--seed", "leadgrow.ai",
                "--no-confirm",
                "--enrich-top", "2",
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0, f"Failed with: {result.stderr}\n{result.output}"

        # Count calls by endpoint
        urls = [str(c.request.url) for c in respx.calls]
        assert sum(1 for u in urls if "/usage" in u) == 1
        assert sum(1 for u in urls if "/extract" in u) == 1
        assert sum(1 for u in urls if "/count" in u) == 1
        assert sum(1 for u in urls if "/discover" in u) == 2
        assert sum(1 for u in urls if "/bizdata" in u) == 2

    @respx.mock
    def test_workflow_enrich_top_zero_skips_profiles(self, tmp_path: Path) -> None:
        _mock_discover_workflow()
        output_file = tmp_path / "results.csv"
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "discover",
                "--seed", "leadgrow.ai",
                "--no-confirm",
                "--enrich-top", "0",
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0, f"Failed with: {result.stderr}\n{result.output}"

        # No bizdata calls
        urls = [str(c.request.url) for c in respx.calls]
        assert sum(1 for u in urls if "/bizdata" in u) == 0

    @respx.mock
    def test_workflow_stderr_shows_progress(self, tmp_path: Path) -> None:
        _mock_discover_workflow()
        output_file = tmp_path / "results.csv"
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "discover",
                "--seed", "leadgrow.ai",
                "--no-confirm",
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0
        # Check that progress steps appear in stderr
        assert "Step 1/8" in result.stderr
        assert "Step 2/8" in result.stderr
        assert "Step 3/8" in result.stderr
        assert "Step 4/8" in result.stderr
        assert "Step 5/8" in result.stderr
        assert "Step 7/8" in result.stderr
        assert "Running cost" in result.stderr


class TestWorkflowEnrichList:
    """Tests for the workflow enrich-list command."""

    @respx.mock
    def test_enrich_list_json_output(self, tmp_path: Path) -> None:
        profile_fixture = load_fixture("business_profile.json")
        score_fixture = load_fixture("score_result.json")
        growth_fixture = load_fixture("growth_result.json")

        respx.get(f"{BASE_URL}/bizdata").mock(
            return_value=httpx.Response(200, json=profile_fixture)
        )
        respx.get(f"{BASE_URL}/score").mock(
            return_value=httpx.Response(200, json=score_fixture)
        )
        respx.get(f"{BASE_URL}/growth").mock(
            return_value=httpx.Response(200, json=growth_fixture)
        )

        # Create input file
        input_file = tmp_path / "domains.txt"
        input_file.write_text("example-agency.com\noutbound-pros.com\n")
        output_file = tmp_path / "enriched.json"

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "enrich-list",
                "--input", str(input_file),
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0, f"Failed with: {result.stderr}\n{result.output}"
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["count"] == 2
        assert len(data["records"]) == 2
        # Check enrichment fields present
        rec = data["records"][0]
        assert "domain" in rec
        assert "digital_footprint_score" in rec
        assert "score_growth_3m" in rec

    @respx.mock
    def test_enrich_list_csv_output(self, tmp_path: Path) -> None:
        profile_fixture = load_fixture("business_profile.json")
        score_fixture = load_fixture("score_result.json")
        growth_fixture = load_fixture("growth_result.json")

        respx.get(f"{BASE_URL}/bizdata").mock(
            return_value=httpx.Response(200, json=profile_fixture)
        )
        respx.get(f"{BASE_URL}/score").mock(
            return_value=httpx.Response(200, json=score_fixture)
        )
        respx.get(f"{BASE_URL}/growth").mock(
            return_value=httpx.Response(200, json=growth_fixture)
        )

        input_file = tmp_path / "domains.txt"
        input_file.write_text("example-agency.com\n")
        output_file = tmp_path / "enriched.csv"

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "enrich-list",
                "--input", str(input_file),
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0, f"Failed with: {result.stderr}\n{result.output}"
        assert output_file.exists()
        content = output_file.read_text()
        assert "example-agency.com" in content

    @respx.mock
    def test_enrich_list_profile_only(self, tmp_path: Path) -> None:
        profile_fixture = load_fixture("business_profile.json")
        respx.get(f"{BASE_URL}/bizdata").mock(
            return_value=httpx.Response(200, json=profile_fixture)
        )

        input_file = tmp_path / "domains.txt"
        input_file.write_text("example-agency.com\n")
        output_file = tmp_path / "enriched.json"

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "enrich-list",
                "--input", str(input_file),
                "-o", str(output_file),
                "--fields", "profile",
            ],
        )
        assert result.exit_code == 0, f"Failed with: {result.stderr}\n{result.output}"

        # Only profile endpoint should be called
        urls = [str(c.request.url) for c in respx.calls]
        assert sum(1 for u in urls if "/bizdata" in u) == 1
        assert sum(1 for u in urls if "/score" in u) == 0
        assert sum(1 for u in urls if "/growth" in u) == 0

    def test_enrich_list_invalid_field_type(self, tmp_path: Path) -> None:
        input_file = tmp_path / "domains.txt"
        input_file.write_text("example.com\n")
        output_file = tmp_path / "enriched.json"

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "enrich-list",
                "--input", str(input_file),
                "-o", str(output_file),
                "--fields", "profile,bogus",
            ],
        )
        assert result.exit_code == 6  # ValidationError
        assert "bogus" in result.stderr

    def test_enrich_list_empty_file(self, tmp_path: Path) -> None:
        input_file = tmp_path / "domains.txt"
        input_file.write_text("# only comments\n")
        output_file = tmp_path / "enriched.json"

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "enrich-list",
                "--input", str(input_file),
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 6  # ValidationError
        assert "No domains" in result.stderr

    @respx.mock
    def test_enrich_list_skips_comments_and_blank_lines(self, tmp_path: Path) -> None:
        profile_fixture = load_fixture("business_profile.json")
        score_fixture = load_fixture("score_result.json")
        growth_fixture = load_fixture("growth_result.json")

        respx.get(f"{BASE_URL}/bizdata").mock(
            return_value=httpx.Response(200, json=profile_fixture)
        )
        respx.get(f"{BASE_URL}/score").mock(
            return_value=httpx.Response(200, json=score_fixture)
        )
        respx.get(f"{BASE_URL}/growth").mock(
            return_value=httpx.Response(200, json=growth_fixture)
        )

        input_file = tmp_path / "domains.txt"
        input_file.write_text(
            "# Header comment\n"
            "\n"
            "example-agency.com\n"
            "# Skip this\n"
            "\n"
            "outbound-pros.com\n"
        )
        output_file = tmp_path / "enriched.json"

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "enrich-list",
                "--input", str(input_file),
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0, f"Failed with: {result.stderr}\n{result.output}"
        data = json.loads(output_file.read_text())
        assert data["count"] == 2

    @respx.mock
    def test_enrich_list_shows_cost(self, tmp_path: Path) -> None:
        profile_fixture = load_fixture("business_profile.json")
        respx.get(f"{BASE_URL}/bizdata").mock(
            return_value=httpx.Response(200, json=profile_fixture)
        )

        input_file = tmp_path / "domains.txt"
        input_file.write_text("example-agency.com\n")
        output_file = tmp_path / "enriched.json"

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli,
            [
                "workflow", "enrich-list",
                "--input", str(input_file),
                "-o", str(output_file),
                "--fields", "profile",
            ],
        )
        assert result.exit_code == 0
        assert "Total cost" in result.stderr
