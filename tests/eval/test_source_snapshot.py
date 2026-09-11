"""Immutable source archives survive repeated Windows/Linux evaluation."""

import gzip
import hashlib
from pathlib import Path

import pytest
from scripts.benchmark import snapshot


def test_existing_archive_is_preserved_byte_for_byte(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = b"def agent(obs):\n    return {'farmer': ['PASS']}\n"
    Path("main.py").write_bytes(source)
    archive = Path("reports/sources") / (hashlib.sha256(source).hexdigest() + ".py.gz")
    archive.parent.mkdir(parents=True)
    historical = bytearray(gzip.compress(source, mtime=0))
    historical[9] = 3  # Historical Linux header, valid on either host.
    archive.write_bytes(historical)
    assert Path(snapshot("main.py")) == archive
    assert archive.read_bytes() == historical


def test_new_archive_has_portable_header_and_exact_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = b"# preserved CRLF\r\nanswer = 42\r\n"
    Path("main.py").write_bytes(source)
    archive = Path(snapshot("main.py"))
    assert archive.read_bytes()[9] == 255
    assert gzip.decompress(archive.read_bytes()) == source


def test_corrupt_existing_archive_is_not_silently_replaced(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("main.py").write_bytes(b"correct")
    archive = Path(snapshot("main.py"))
    wrong = gzip.compress(b"wrong", mtime=0)
    archive.write_bytes(wrong)
    with pytest.raises(ValueError, match="corrupt"):
        snapshot("main.py")
    assert archive.read_bytes() == wrong
