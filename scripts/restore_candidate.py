"""Restore an exact experimental executable from its content-addressed snapshot."""

import argparse
import gzip
import hashlib
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("sha256")
parser.add_argument("--output", type=Path, default=Path("data/interim/restored/main.py"))
args = parser.parse_args()
if len(args.sha256) != 64 or any(c not in "0123456789abcdef" for c in args.sha256):
    parser.error("Expected a lowercase SHA-256 digest")
content = gzip.decompress((Path("reports/sources") / (args.sha256 + ".py.gz")).read_bytes())
assert hashlib.sha256(content).hexdigest() == args.sha256
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_bytes(content)
print(args.output)
