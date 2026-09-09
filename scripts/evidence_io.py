"""Read plain or compressed benchmark evidence."""

import gzip
import json
from pathlib import Path


def read_result(path):
    path = Path(path)
    if not path.exists() and path.suffix == ".json":
        path = path.with_suffix(".json.gz")
    content = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    return json.loads(content)
