"""Memory evidence distinguishes an executable image from pre-exec RSS history."""

import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.verify_submission import memory_usage


def mock_linux(monkeypatch, status):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setitem(
        sys.modules,
        "resource",
        SimpleNamespace(RUSAGE_SELF=0, getrusage=lambda who: SimpleNamespace(ru_maxrss=250 * 1024)),
    )
    monkeypatch.setattr(Path, "read_text", lambda path: status)


def test_linux_prefers_current_image_highwater_and_retains_history(monkeypatch):
    mock_linux(monkeypatch, "Name:\tpython\nVmHWM:\t16384 kB\nVmRSS:\t14000 kB\n")
    result = memory_usage()
    assert result["peak_rss_bytes"] == 16 * 1024 * 1024
    assert result["resource_peak_rss_bytes"] == 250 * 1024 * 1024
    assert "current-image" in result["peak_rss_measure"]


def test_missing_proc_accounting_keeps_explicit_historical_fallback(monkeypatch):
    mock_linux(monkeypatch, "Name:\tpython\n")
    result = memory_usage()
    assert result["peak_rss_bytes"] == result["resource_peak_rss_bytes"]
    assert "pre-exec" in result["peak_rss_measure"]


def test_native_process_memory_measure_is_positive():
    result = memory_usage()
    assert result["peak_rss_bytes"] > 0
    assert result["peak_rss_measure"]


@pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="Linux exec/proc accounting contract"
)
def test_linux_exec_does_not_attribute_previous_image_to_current_image():
    after_exec = (
        inspect.getsource(memory_usage) + "\nimport json\nprint(json.dumps(memory_usage()))"
    )
    before_exec = """
import os, sys
allocation = bytearray(64 * 1024 * 1024)
for offset in range(0, len(allocation), 4096):
    allocation[offset] = 1
os.execv(sys.executable, [sys.executable, '-I', '-S', '-c', sys.argv[1]])
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-c", before_exec, after_exec],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    result = json.loads(completed.stdout)
    assert "current-image" in result["peak_rss_measure"]
    assert result["resource_peak_rss_bytes"] >= 64 * 1024 * 1024
    assert result["resource_peak_rss_bytes"] - result["peak_rss_bytes"] > 32 * 1024 * 1024
