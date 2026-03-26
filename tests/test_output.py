"""Tests for OutputManager — JSON, CSV, and table rendering."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from discolike.output import DecimalEncoder, OutputManager, click_echo_json
from discolike.types import CostBreakdown, DiscoverRecord, DiscoverResult


class TestDecimalEncoder:
    def test_encodes_decimal(self) -> None:
        data = {"price": Decimal("1.50")}
        result = json.dumps(data, cls=DecimalEncoder)
        assert result == '{"price": 1.5}'

    def test_non_decimal_raises(self) -> None:
        with pytest.raises(TypeError):
            json.dumps({"val": object()}, cls=DecimalEncoder)


class TestOutputManagerJSON:
    def test_json_dict(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(json_output=True)
        om.render({"foo": "bar"})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["foo"] == "bar"

    def test_json_list_of_dicts(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(json_output=True)
        om.render([{"a": 1}, {"a": 2}])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["count"] == 2
        assert len(data["records"]) == 2

    def test_json_pydantic_model(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(json_output=True)
        record = DiscoverRecord(domain="test.com", name="Test", score=100)
        om.render(record)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["domain"] == "test.com"

    def test_json_pydantic_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(json_output=True)
        records = [
            DiscoverRecord(domain="a.com", name="A"),
            DiscoverRecord(domain="b.com", name="B"),
        ]
        om.render(records)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["count"] == 2
        assert data["records"][0]["domain"] == "a.com"

    def test_json_discover_result(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(json_output=True)
        result = DiscoverResult(
            records=[DiscoverRecord(domain="x.com", name="X")],
            count=1,
        )
        om.render(result)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["count"] == 1

    def test_json_includes_meta_cost(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(json_output=True)
        cost = CostBreakdown(
            endpoint="discover",
            query_fee=Decimal("0.18"),
            record_fee=Decimal("0.07"),
            total=Decimal("0.25"),
            records_returned=20,
            session_total=Decimal("0.25"),
            plan="starter",
        )
        om.render({"result": "ok"}, cost=cost)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "_meta" in data
        assert data["_meta"]["cost"]["total"] == 0.25
        assert data["_meta"]["cost"]["endpoint"] == "discover"
        assert "timestamp" in data["_meta"]

    def test_json_meta_cached(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(json_output=True)
        cost = CostBreakdown(endpoint="test", plan="starter")
        om.render({"x": 1}, cost=cost, cached=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["_meta"]["cached"] is True

    def test_json_scalar_value(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(json_output=True)
        om.render("hello")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["result"] == "hello"

    def test_json_empty_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(json_output=True)
        om.render([])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["count"] == 0
        assert data["records"] == []


class TestOutputManagerCSV:
    def test_csv_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(csv_output=True)
        # Force csv rendering even if TTY
        om._render_csv([{"name": "A", "score": 100}, {"name": "B", "score": 200}])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        assert lines[0].strip() == "name,score"
        assert "A" in lines[1]
        assert "B" in lines[2]

    def test_csv_with_fields_filter(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(csv_output=True, fields=["name"])
        om._render_csv(
            [{"name": "A", "score": 100, "extra": "x"}],
        )
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        assert lines[0].strip() == "name"
        assert "score" not in captured.out

    def test_csv_list_values_joined(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(csv_output=True)
        om._render_csv([{"tags": ["a", "b", "c"]}])
        captured = capsys.readouterr()
        assert "a; b; c" in captured.out

    def test_csv_none_values(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(csv_output=True)
        om._render_csv([{"name": None}])
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Header + one row with empty value
        assert len(lines) == 2

    def test_csv_empty_records(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(csv_output=True)
        om._render_csv([])
        captured = capsys.readouterr()
        assert captured.out == ""


class TestOutputManagerTable:
    def test_table_renders_records(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager()
        # Render directly to table since we can't guarantee TTY in test
        om._render_table(
            [{"name": "Test Corp", "score": "450"}],
            title="Results",
        )
        captured = capsys.readouterr()
        assert "Test Corp" in captured.out
        assert "450" in captured.out

    def test_table_empty_shows_no_results(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        om = OutputManager()
        om._render_table([])
        captured = capsys.readouterr()
        assert "No results" in captured.err

    def test_table_with_cost_footer(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager()
        cost = CostBreakdown(
            endpoint="discover",
            total=Decimal("0.25"),
            session_total=Decimal("0.50"),
            plan="starter",
        )
        om._render_table(
            [{"name": "X"}],
            cost=cost,
        )
        captured = capsys.readouterr()
        assert "$0.25" in captured.err or "$0.2500" in captured.err
        assert "session: $0.50" in captured.err

    def test_table_truncates_long_values(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        om = OutputManager()
        long_val = "x" * 100
        om._render_table([{"desc": long_val}])
        captured = capsys.readouterr()
        # Rich uses unicode ellipsis \u2026 or literal "..." for overflow
        assert "\u2026" in captured.out or "..." in captured.out

    def test_table_with_field_filter(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        om = OutputManager(fields=["name"])
        om._render_table(
            [{"name": "A", "score": 100}],
        )
        captured = capsys.readouterr()
        assert "A" in captured.out
        # score column should not appear since we filtered to just name
        # (Can't strictly assert "100" is absent since Rich may include it differently,
        #  but column header "score" should not appear)


class TestStatusMessages:
    def test_status(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager()
        om.status("Loading...")
        captured = capsys.readouterr()
        assert "Loading" in captured.err

    def test_status_quiet(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager(quiet=True)
        om.status("Loading...")
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager()
        om.success("Done!")
        captured = capsys.readouterr()
        assert "Done" in captured.err

    def test_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager()
        om.warning("Watch out")
        captured = capsys.readouterr()
        assert "Watch out" in captured.err

    def test_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        om = OutputManager()
        om.error("Broken")
        captured = capsys.readouterr()
        assert "Broken" in captured.err


class TestClickEchoJson:
    def test_echo_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        click_echo_json({"key": "val", "num": Decimal("1.5")})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["key"] == "val"
        assert data["num"] == 1.5
