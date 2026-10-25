"""Regression: ls/bash truncation must still signal the cut when the budget cannot hold the full marker."""

from deerflow.sandbox.tools import _truncate_bash_output, _truncate_ls_output


def test_bash_tiny_budget_still_marks_truncation():
    output = "x" * 100

    result = _truncate_bash_output(output, 32)

    # A bare 32-char prefix reads as the complete output; the cut must be visible.
    assert "truncated" in result
    assert len(result) <= 32


def test_ls_tiny_budget_still_marks_truncation():
    output = "\n".join(f"/mnt/user-data/workspace/file_{i}.txt" for i in range(20))

    result = _truncate_ls_output(output, 60)

    assert "truncated" in result
    assert len(result) <= 60


def test_regular_budgets_keep_existing_markers():
    bash = _truncate_bash_output("x" * 400, 100)
    ls = _truncate_ls_output("y" * 400, 200)

    assert "[middle truncated:" in bash and len(bash) <= 100
    assert "[truncated: showing first" in ls and len(ls) <= 200
