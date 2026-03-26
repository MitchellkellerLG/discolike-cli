"""Tests for discover and count commands -- the critical filter tests."""

from __future__ import annotations

import json

import httpx
import respx
from click.testing import CliRunner

from discolike.cli import cli
from discolike.commands.discover import collect_filters
from tests.conftest import load_fixture, make_cli_runner

BASE_URL = "https://api.discolike.com/v1"


class TestCollectFilters:
    """Unit tests for the filter collection logic."""

    def test_empty_kwargs_returns_empty(self) -> None:
        assert collect_filters() == {}

    def test_single_domain(self) -> None:
        result = collect_filters(domain=("leadgrow.ai",))
        assert result == {"domain": ["leadgrow.ai"]}

    def test_multiple_domains(self) -> None:
        result = collect_filters(domain=("a.com", "b.com"))
        assert result == {"domain": ["a.com", "b.com"]}

    def test_country_filter(self) -> None:
        result = collect_filters(country=("US", "GB"))
        assert result == {"country": ["US", "GB"]}

    def test_employee_range(self) -> None:
        result = collect_filters(employee_range="51-200")
        assert result == {"employee_range": "51-200"}

    def test_icp_text(self) -> None:
        result = collect_filters(icp_text="B2B SaaS companies with 50+ employees")
        assert result == {"icp_text": "B2B SaaS companies with 50+ employees"}

    def test_score_range(self) -> None:
        result = collect_filters(min_digital_footprint=100, max_digital_footprint=500)
        assert result == {"min_digital_footprint": 100, "max_digital_footprint": 500}

    def test_negation_filters(self) -> None:
        result = collect_filters(negate_domain=("skip.com",), negate_country=("CN",))
        assert result == {"negate_domain": ["skip.com"], "negate_country": ["CN"]}

    def test_skips_false_boolean_defaults(self) -> None:
        result = collect_filters(
            auto_icp_text=False,
            auto_phrase_match=False,
            enhanced=False,
            include_search_domains=False,
            redirect=False,
        )
        assert result == {}

    def test_includes_true_booleans(self) -> None:
        result = collect_filters(auto_icp_text=True, enhanced=True)
        assert result == {"auto_icp_text": True, "enhanced": True}

    def test_skips_default_variance(self) -> None:
        result = collect_filters(variance="UNRESTRICTED")
        assert result == {}

    def test_includes_non_default_variance(self) -> None:
        result = collect_filters(variance="LOW")
        assert result == {"variance": "LOW"}

    def test_skips_default_consensus(self) -> None:
        result = collect_filters(consensus=1)
        assert result == {}

    def test_includes_non_default_consensus(self) -> None:
        result = collect_filters(consensus=5)
        assert result == {"consensus": 5}

    def test_empty_tuples_skipped(self) -> None:
        result = collect_filters(domain=(), country=(), category=())
        assert result == {}

    def test_none_values_skipped(self) -> None:
        result = collect_filters(
            icp_text=None,
            employee_range=None,
            min_digital_footprint=None,
        )
        assert result == {}

    def test_combined_filters(self) -> None:
        result = collect_filters(
            domain=("seed.com",),
            country=("US",),
            employee_range="11-50",
            category=("SAAS",),
            min_digital_footprint=200,
            enhanced=True,
        )
        assert result == {
            "domain": ["seed.com"],
            "country": ["US"],
            "employee_range": "11-50",
            "category": ["SAAS"],
            "min_digital_footprint": 200,
            "enhanced": True,
        }


class TestCountCommand:
    @respx.mock
    def test_count_basic(self) -> None:
        respx.get(f"{BASE_URL}/count").mock(
            return_value=httpx.Response(200, json={"count": 1500})
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "count", "-d", "leadgrow.ai"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1500

    @respx.mock
    def test_count_low_threshold_warning(self) -> None:
        respx.get(f"{BASE_URL}/count").mock(
            return_value=httpx.Response(200, json={"count": 10})
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["count", "-d", "tiny-niche.com"])
        assert result.exit_code == 0
        # Warning should be printed to stderr (CliRunner separates stderr by default)

    @respx.mock
    def test_count_high_threshold_warning(self) -> None:
        respx.get(f"{BASE_URL}/count").mock(
            return_value=httpx.Response(200, json={"count": 50000})
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["count", "-d", "broad.com"])
        assert result.exit_code == 0

    @respx.mock
    def test_count_with_country_filter(self) -> None:
        route = respx.get(f"{BASE_URL}/count").mock(
            return_value=httpx.Response(200, json={"count": 800})
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json", "count", "-d", "test.com", "--country", "US", "--country", "GB"]
        )
        assert result.exit_code == 0
        # Verify filters were sent as query params
        url = str(route.calls[0].request.url)
        assert "country=US" in url or "country=US%2CGB" in url or "country=US,GB" in url

    @respx.mock
    def test_count_with_employee_range(self) -> None:
        route = respx.get(f"{BASE_URL}/count").mock(
            return_value=httpx.Response(200, json={"count": 250})
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json", "count", "-d", "test.com", "--employees", "51-200"]
        )
        assert result.exit_code == 0
        url = str(route.calls[0].request.url)
        assert "employee_range=51-200" in url

    def test_count_dry_run(self) -> None:
        """Dry run should NOT make HTTP calls."""
        runner = make_cli_runner()
        result = runner.invoke(cli, ["--dry-run", "--json", "count", "-d", "test.com"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0  # dry run returns 0


class TestDiscoverCommand:
    @respx.mock
    def test_discover_basic(self) -> None:
        fixture = load_fixture("discover_results.json")
        respx.get(f"{BASE_URL}/discover").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "discover", "-d", "leadgrow.ai"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 2
        assert len(data["records"]) == 2
        assert data["records"][0]["domain"] == "example-agency.com"

    @respx.mock
    def test_discover_with_max_records(self) -> None:
        fixture = load_fixture("discover_results.json")
        route = respx.get(f"{BASE_URL}/discover").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json", "discover", "-d", "test.com", "--max-records", "50"]
        )
        assert result.exit_code == 0
        url = str(route.calls[0].request.url)
        assert "max_records=50" in url

    @respx.mock
    def test_discover_save_csv(self, tmp_path) -> None:
        fixture = load_fixture("discover_results.json")
        respx.get(f"{BASE_URL}/discover").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        output_file = tmp_path / "results.csv"
        runner = CliRunner()
        result = runner.invoke(
            cli, ["discover", "-d", "test.com", "-o", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "example-agency.com" in content

    @respx.mock
    def test_discover_save_json(self, tmp_path) -> None:
        fixture = load_fixture("discover_results.json")
        respx.get(f"{BASE_URL}/discover").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        output_file = tmp_path / "results.json"
        runner = CliRunner()
        result = runner.invoke(
            cli, ["discover", "-d", "test.com", "-o", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["count"] == 2

    @respx.mock
    def test_discover_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--dry-run", "--json", "discover", "-d", "test.com"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0
        assert data["records"] == []

    @respx.mock
    def test_discover_with_icp_text(self) -> None:
        fixture = load_fixture("discover_results.json")
        route = respx.get(f"{BASE_URL}/discover").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "discover", "--icp-text", "B2B SaaS companies selling to developers"],
        )
        assert result.exit_code == 0
        url = str(route.calls[0].request.url)
        assert "icp_text=" in url

    @respx.mock
    def test_discover_with_enhanced_flag(self) -> None:
        fixture = load_fixture("discover_results.json")
        route = respx.get(f"{BASE_URL}/discover").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json", "discover", "-d", "test.com", "--enhanced"]
        )
        assert result.exit_code == 0
        url = str(route.calls[0].request.url)
        assert "enhanced=true" in url

    @respx.mock
    def test_discover_with_exclude(self) -> None:
        fixture = load_fixture("discover_results.json")
        route = respx.get(f"{BASE_URL}/discover").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json", "discover", "-d", "test.com", "--exclude", "q_abc123"]
        )
        assert result.exit_code == 0
        url = str(route.calls[0].request.url)
        assert "exclusion_query_id=q_abc123" in url

    @respx.mock
    def test_discover_with_multiple_filters(self) -> None:
        fixture = load_fixture("discover_results.json")
        route = respx.get(f"{BASE_URL}/discover").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json",
                "discover",
                "-d", "seed.com",
                "--country", "US",
                "--employees", "11-50",
                "--min-score", "200",
                "--variance", "LOW",
            ],
        )
        assert result.exit_code == 0
        url = str(route.calls[0].request.url)
        assert "domain=seed.com" in url
        assert "country=US" in url
        assert "employee_range=11-50" in url
        assert "min_digital_footprint=200" in url
        assert "variance=LOW" in url
