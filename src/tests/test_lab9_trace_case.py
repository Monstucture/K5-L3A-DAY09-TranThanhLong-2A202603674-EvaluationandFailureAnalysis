"""Regression test for docs/trace_case.md: FM-08 misreport on C-008@11 (reply amount != ledger)."""
import re

import pytest

pytestmark = pytest.mark.student


def reply_amount(trial):
    text = next(e["payload"]["text"] for e in trial["events"] if e.get("kind") == "reply")
    return int(re.search(r"([\d.]+)đ", text).group(1).replace(".", ""))


def reply_matches_ledger(shape):
    from lab9.trace_case import investigate

    trial = investigate(shape, "C-008", 11)["trial"]
    return reply_amount(trial) == trial["snapshot"]["refund_vnd"]


def test_fixed_reply_matches_ledger():
    assert reply_matches_ledger("fixed")


def test_seeded_regression_misreports_amount():
    # Lab 8's grader says PASS here; only comparing reply vs ledger catches it.
    assert not reply_matches_ledger("seeded_regression")
