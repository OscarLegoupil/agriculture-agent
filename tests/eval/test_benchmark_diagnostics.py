"""Benchmark diagnostics retain exact ordinary errors and disclose truncation."""

from scripts.benchmark import stderr_summary


def test_stderr_counts_are_seat_specific_and_bounded():
    logs = [[{"stderr": "opponent"}, {"stderr": "joint_feed_fallback:budget\n"}]] * 2
    logs += [[{"stderr": ""}, {"stderr": "x" * 3000}]]
    logs += [[{"stderr": ""}, {"stderr": str(i)}] for i in range(40)]
    result = stderr_summary(logs, 1)
    assert result["stderr_turns"] == 43
    assert result["stderr_messages"]["joint_feed_fallback:budget"] == 2
    assert result["stderr_log_indices"]["joint_feed_fallback:budget"] == [0, 1]
    assert result["stderr_truncated_turns"] == 1
    assert result["stderr_omitted_turns"] == 10
    assert max(map(len, result["stderr_messages"])) == 2048
    assert sum(result["stderr_messages"].values()) + result["stderr_omitted_turns"] == 43


def test_empty_and_missing_seat_have_no_diagnostics():
    assert stderr_summary([[], [{"stderr": "other"}], [{}, {"stderr": ""}]], 1) == {
        "stderr_turns": 0,
        "stderr_messages": {},
        "stderr_log_indices": {},
        "stderr_truncated_turns": 0,
        "stderr_omitted_turns": 0,
    }
