"""Unit tests for SparkRules connector (skipped when sparkrules not installed)."""

from __future__ import annotations

import pytest

sparkrules = pytest.importorskip("sparkrules")

from serverless_data_mesh.rules import SparkRulesConnector  # noqa: E402


_SIMPLE_DRL = r"""
rule PositiveAmount
when
    $row : Row ( $row.amount > 0 )
then
    result.eligible = true;
end
"""


def test_from_drl_and_apply_chunk() -> None:
    connector = SparkRulesConnector.from_drl(_SIMPLE_DRL)
    records = [{"id": "1", "amount": 100}, {"id": "2", "amount": -1}]
    enriched, audit = connector.apply_chunk(records)
    assert len(enriched) == 2
    assert enriched[0].get("eligible") is True
    assert len(audit) >= 1


def test_quality_gate_require_fire() -> None:
    from serverless_data_mesh.exceptions import RuleEvaluationError

    connector = SparkRulesConnector.from_drl(_SIMPLE_DRL)
    with pytest.raises(RuleEvaluationError):
        connector.quality_gate([{"id": "x", "amount": -5}], require_any_rule_fired=True)


def test_audit_json() -> None:
    connector = SparkRulesConnector.from_drl(_SIMPLE_DRL)
    _, audit = connector.apply_chunk([{"id": "1", "amount": 10}])
    payload = connector.audit_json(audit)
    assert "PositiveAmount" in payload or "[]" in payload
