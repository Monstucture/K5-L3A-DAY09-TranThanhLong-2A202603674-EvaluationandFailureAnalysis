from lab8.shapes.single import run_claim
from lab8.db import connect


def test_single_missing_order_id(public_db):
    result = run_claim(
        "C-004",
        seed=11,
        store_path=str(public_db),
    )

    assert result.status == "needs_info"
    assert result.proposal_amount == 0
    assert result.error_reason == "missing_order_id"
    assert result.model_calls == 0



def test_single_refund_idempotency(public_db):
    first = run_claim(
        "C-001",
        seed=11,
        store_path=str(public_db),
    )

    second = run_claim(
        "C-001",
        seed=11,
        store_path=str(public_db),
    )

    assert first.status == "resolved"
    assert second.status == "resolved"

    assert first.proposal_amount == 35000
    assert second.proposal_amount == 35000

    assert len(first.refund_effects) == 1
    assert len(second.refund_effects) == 1

    assert (
        first.refund_effects[0]["idempotency_key"]
        == second.refund_effects[0]["idempotency_key"]
    )

    assert first.committed_audit_count == 1
    assert second.committed_audit_count == 1

    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert result.refund_effects == []

def test_single_refund_idempotency(public_db):
    first = run_claim(
        "C-001",
        seed=11,
        store_path=str(public_db),
    )

    second = run_claim(
        "C-001",
        seed=11,
        store_path=str(public_db),
    )

    assert first.status == "resolved"
    assert second.status == "resolved"

    assert first.proposal_amount == 35000
    assert second.proposal_amount == 35000

    assert len(first.refund_effects) == 1
    assert len(second.refund_effects) == 1

    assert (
        first.refund_effects[0]["idempotency_key"]
        == second.refund_effects[0]["idempotency_key"]
    )

    assert first.committed_audit_count == 1
    assert second.committed_audit_count == 1


def test_single_zero_refund(public_db):
    result = run_claim(
        "C-002",
        seed=11,
        store_path=str(public_db),
    )

    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert result.refund_effects == []
