"""Evidence archival contracts found during the independent phase-3 review."""

import gzip
import hashlib
import json
import sys
from pathlib import Path

import pytest
from scripts import phase3_report


def test_failed_episode_is_not_counted_as_cash_win(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manifest, _ = manifest_fixture(tmp_path)
    manifest["episodes"][0]["statuses"][0] = "ERROR"
    manifest["episodes"][0]["cash"] = None
    path = tmp_path / "phase3-error.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "results" / "summary.json"
    monkeypatch.setattr(sys, "argv", ["report", str(path), "--output", str(output)])
    phase3_report.main()
    group = json.loads(output.read_text(encoding="utf-8"))["experiments"][0]["groups"][0]
    assert group["wins"] == 1
    assert group["match_score"] == 0.5
    assert group["non_done_games"] == 1
    assert group["missing_cash_games"] == 1


def manifest_fixture(tmp_path, schema="mapped", cash=100):
    source = b"def agent(obs, configuration=None): return {}\n"
    digest = hashlib.sha256(source).hexdigest()
    snapshot = Path("reports/sources") / (digest + ".py.gz")
    (tmp_path / snapshot).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / snapshot).write_bytes(gzip.compress(source, mtime=0))
    candidate = "candidate/main.py"
    row_candidate = candidate
    manifest = {
        "revision": "review-fixture",
        "complete": True,
        "hashes": {"opponent/main.py": "1" * 64},
    }
    if schema == "mapped":
        manifest["candidates"] = {candidate: {"sha256": digest, "name": "fixture"}}
    elif schema == "direct":
        manifest.update(candidate=candidate, sha256=digest, snapshot=str(snapshot))
    elif schema == "generic":
        row_candidate = "data\\interim\\frozen\\" + digest + "\\main.py"
        manifest.update(
            executed_candidate=row_candidate.replace("\\", "/"),
            arguments={"candidate": candidate},
            candidate_snapshot=str(snapshot),
        )
        manifest["hashes"][candidate] = digest
    else:
        raise AssertionError(schema)
    manifest["episodes"] = [
        {
            "candidate": row_candidate,
            "opponent": "opponent/main.py",
            "seed": 0,
            "seat": seat,
            "cash": cash,
            "opponent_cash": 90,
            "statuses": ["DONE", "DONE"],
            "stderr_turns": 0,
            "runtime_max_seconds": 0.001,
        }
        for seat in (0, 1)
    ]
    return manifest, digest


@pytest.mark.parametrize("schema", ["mapped", "direct", "generic"])
def test_report_accepts_all_executed_manifest_schemas(tmp_path, monkeypatch, schema):
    monkeypatch.chdir(tmp_path)
    manifest, digest = manifest_fixture(tmp_path, schema)
    path = Path("experiment.json")
    path.write_text(json.dumps(manifest))
    output = Path("results/index.json")
    monkeypatch.setattr(sys, "argv", ["phase3_report", str(path), "--output", str(output)])
    phase3_report.main()
    result = json.loads(output.read_text())
    group = result["experiments"][0]["groups"][0]
    assert group["sha256"] == digest
    assert group["games"] == group["wins"] == 2


def test_invalid_later_input_does_not_publish_earlier_archive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    good, _ = manifest_fixture(tmp_path)
    bad, _ = manifest_fixture(tmp_path)
    bad["candidates"]["candidate/main.py"]["sha256"] = "0" * 64
    Path("good.json").write_text(json.dumps(good))
    Path("bad.json").write_text(json.dumps(bad))
    output = Path("results/index.json")
    monkeypatch.setattr(
        sys, "argv", ["phase3_report", "good.json", "bad.json", "--output", str(output)]
    )
    with pytest.raises((AssertionError, ValueError, FileNotFoundError)):
        phase3_report.main()
    assert not list(output.parent.glob("*.gz"))
    assert not output.exists()


def test_distinct_same_basename_inputs_cannot_overwrite_evidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    one, _ = manifest_fixture(tmp_path, cash=100)
    two, _ = manifest_fixture(tmp_path, cash=101)
    for directory, manifest in (("one", one), ("two", two)):
        Path(directory).mkdir()
        (Path(directory) / "experiment.json").write_text(json.dumps(manifest))
    output = Path("results/index.json")
    monkeypatch.setattr(
        sys,
        "argv",
        ["phase3_report", "one/experiment.json", "two/experiment.json", "--output", str(output)],
    )
    with pytest.raises(
        (AssertionError, ValueError, FileExistsError, RuntimeError),
        match=r"(?i)collis|overwrite|different",
    ):
        phase3_report.main()
    assert not list(output.parent.glob("*.gz"))
    assert not output.exists()
