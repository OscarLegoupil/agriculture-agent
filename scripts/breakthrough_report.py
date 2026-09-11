"""Validate frozen strategy screens and compare each policy with one champion.

No games are run. Optional worker measurements read retained official replays.
Development confidence intervals describe paired seed variation, not a correction
for choosing candidates after inspecting the development results.
"""

import argparse
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

try:
    from .evidence_io import read_result
    from .phase2_compare import compare
    from .summarize_benchmark import match_score
except ImportError:
    from evidence_io import read_result
    from phase2_compare import compare
    from summarize_benchmark import match_score


CHAMPION = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"
PROVENANCE = ("environment_version", "interpreter_sha256", "lock_sha256", "dependencies")
MILESTONES = (3, 5, 8, 11, 15, 20, 29)
MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}
LOGISTICS = MOVES | {"PICKUP", "DROP", "PLACE"}


def sha(content):
    return hashlib.sha256(content).hexdigest()


def local_path(value):
    return Path(value.replace("\\", "/"))


def verify(manifest):
    """Reject incomplete coverage, wrong identities and invalid game outcomes."""
    if manifest.get("complete") is not True:
        raise ValueError("Partial screen: finish the declared panel before reporting")
    panel = manifest["declared_panel"]
    for field in ("seeds", "seats", "opponents"):
        values = panel[field]
        if not values or len(values) != len(set(values)):
            raise ValueError(f"Empty or duplicate declared {field}")
    if set(panel["seats"]) != {0, 1}:
        raise ValueError("Both seats must be declared")
    candidates = manifest["candidates"]
    if not candidates or len({m["sha256"] for m in candidates.values()}) != len(candidates):
        raise ValueError("Missing candidates or duplicate candidate identities")
    expected = {
        (c, o, seed, seat)
        for c in candidates
        for o in panel["opponents"]
        for seed in panel["seeds"]
        for seat in panel["seats"]
    }
    rows = manifest["episodes"]
    actual = {(r["candidate"], r["opponent"], r["seed"], r["seat"]) for r in rows}
    if actual != expected or len(rows) != len(expected):
        raise ValueError("Rows do not uniquely cover the complete declared panel")
    for candidate, metadata in candidates.items():
        contents = (
            local_path(candidate).read_bytes(),
            gzip.decompress(local_path(metadata["snapshot"]).read_bytes()),
        )
        if any(sha(content) != metadata["sha256"] for content in contents):
            raise ValueError(f"Candidate source or snapshot hash differs: {candidate}")
    for opponent in panel["opponents"]:
        if sha(local_path(opponent).read_bytes()) != manifest["hashes"][opponent]:
            raise ValueError(f"Opponent executable hash differs: {opponent}")
    for bundle in manifest.get("executable_bundles", {}).values():
        for path, digest in bundle.items():
            if sha(local_path(path).read_bytes()) != digest:
                raise ValueError(f"Executable sidecar hash differs: {path}")
    configurations = set()
    for row in rows:
        if row.get("resolved_seed") != row["seed"]:
            raise ValueError("Resolved seed differs from the declared seed")
        if len(row["statuses"]) != 2:
            raise ValueError("Missing player status")
        if row["configuration"].get("seed") not in (None, row["seed"]):
            raise ValueError("Effective configuration contains a different seed")
        configurations.add(json.dumps({**row["configuration"], "seed": None}, sort_keys=True))
        for seat, key in ((row["seat"], "cash"), (1 - row["seat"], "opponent_cash")):
            cash = row.get(key)
            if row["statuses"][seat] == "DONE" and (cash is None or not math.isfinite(cash)):
                raise ValueError("DONE outcome has missing or non-finite cash")
    if len(configurations) != 1:
        raise ValueError("Effective configurations differ within the screen")
    return json.loads(configurations.pop())


def replay_workers(row):
    """Measure daily maximum simultaneous hands; reset snapshots have zero hands."""
    value = row.get("replay_path")
    if not value or not local_path(value).is_file():
        return None
    path = local_path(value)
    content = path.read_bytes()
    replay = json.loads(content)
    seat = row["seat"]
    if replay["info"].get("seed") != row["seed"] or replay["rewards"][seat] != row["cash"]:
        raise ValueError(f"Replay does not match the recorded outcome: {path}")
    days = {}
    for day in MILESTONES:
        states = replay["steps"][day * 24 : (day + 1) * 24]
        if states:
            days[day] = max(len(s[seat]["observation"]["farms"][seat]["hands"]) for s in states)
    return {"path": path.as_posix(), "sha256": sha(content), "daily_peak_hands": days}


def means(rows, key):
    names = sorted({name for row in rows for name in row.get(key, {})})
    return {name: float(np.mean([r.get(key, {}).get(name, 0) for r in rows])) for name in names}


def runtime_distribution(values):
    return {
        "games": len(values),
        "median": float(np.median(values)),
        "p95": float(np.quantile(values, 0.95)),
        "p99": float(np.quantile(values, 0.99)),
        "max": float(max(values)),
    }


def diagnostics(rows, workers):
    actions = means(rows, "realized_actions")
    successful = {k[8:]: v for k, v in actions.items() if k.startswith("success:")}
    milestones = {}
    for day in MILESTONES:
        observations = [next((d for d in r["daily"] if d["step"] == day * 24), None) for r in rows]
        observed = [d for d in observations if d is not None]
        hands = [workers[id(r)]["daily_peak_hands"].get(day) for r in rows if workers.get(id(r))]
        hands = [value for value in hands if value is not None]
        milestones[str(day)] = {
            "observed_games": len(observed),
            "composition_mean": means(observed, "composition") if observed else {},
            **{
                key + "_mean": float(np.mean([d[key] for d in observed])) if observed else None
                for key in ("cash", "land", "crops", "animals", "shed", "carried")
            },
            "replay_worker_games": len(hands),
            "peak_hands_mean": float(np.mean(hands)) if hands else None,
        }
    losses = sum((Counter(r.get("losses", {})) for r in rows), Counter())
    return {
        "ledger_mean": means(rows, "ledger"),
        "realized_actions_mean": actions,
        "moves_mean": sum(successful.get(k, 0) for k in MOVES),
        "productive_actions_mean": sum(v for k, v in successful.items() if k not in LOGISTICS),
        "losses_total": dict(losses),
        "stderr_turns": sum(r.get("stderr_turns", 0) for r in rows),
        "stderr_messages": dict(
            sum((Counter(r.get("stderr_messages", {})) for r in rows), Counter())
        ),
        "stderr_truncated_turns": sum(r.get("stderr_truncated_turns", 0) for r in rows),
        "stderr_omitted_turns": sum(r.get("stderr_omitted_turns", 0) for r in rows),
        "runtime_episode_max_seconds": runtime_distribution(
            [r["runtime_max_seconds"] for r in rows]
        ),
        "runtime_max_seconds": max(r["runtime_max_seconds"] for r in rows),
        "runtime_episode_p99_seconds": runtime_distribution(
            [r["runtime_p99_seconds"] for r in rows]
        ),
        "milestones": milestones,
    }


def build_report(paths, champion=CHAMPION, use_replays=False):
    manifests = [(path, read_result(path)) for path in paths]
    configurations = [verify(m) for _, m in manifests]
    first = manifests[0][1]
    opponents = sorted(first["declared_panel"]["opponents"])
    identities, policies, inputs = {}, {}, []
    for (path, manifest), configuration in zip(manifests, configurations, strict=True):
        if configuration != configurations[0]:
            raise ValueError("Effective configuration changed between inputs")
        if any(manifest[key] != first[key] for key in PROVENANCE):
            raise ValueError("Environment/dependency provenance changed between inputs")
        if sorted(manifest["declared_panel"]["opponents"]) != opponents:
            raise ValueError("Opponent pools differ between inputs")
        if any(manifest["hashes"][o] != first["hashes"][o] for o in opponents):
            raise ValueError("Opponent identity changed between inputs")
        inputs.append(
            {
                "path": path.as_posix(),
                "sha256_file": sha(path.read_bytes()),
                "revision": manifest["revision"],
            }
        )
        for candidate, meta in manifest["candidates"].items():
            digest = meta["sha256"]
            identities.setdefault(
                digest,
                {
                    "name": meta.get("name", digest[:12]),
                    "sha256": digest,
                    "snapshot": meta["snapshot"],
                },
            )
            indexed = policies.setdefault(digest, {})
            for row in (r for r in manifest["episodes"] if r["candidate"] == candidate):
                key = row["opponent"], row["seed"], row["seat"]
                if key in indexed and indexed[key] != row:
                    raise ValueError(
                        "Overlapping policy scenarios differ; choose one declared attempt"
                    )
                indexed[key] = row
    if champion not in policies:
        raise ValueError("No records for the requested champion hash")
    workers = {}
    if use_replays:
        for rows in policies.values():
            for row in rows.values():
                workers[id(row)] = replay_workers(row)
    report = {
        "complete": True,
        "scope": "Development comparison; intervals do not adjust for candidate selection or opponent coverage",
        "inputs": inputs,
        "champion": identities[champion],
        "configuration": configurations[0],
        "provenance": {key: first[key] for key in PROVENANCE},
        "opponent_hashes": {o: first["hashes"][o] for o in opponents},
        "weights": dict.fromkeys(opponents, 1 / len(opponents)),
        "uncertainty": "10000 whole-seed bootstrap draws, RNG20260910; seats, opponents and policies retained together",
        "measurement_notes": [
            "Runtime distributions summarize per-episode action maxima/p99 values, not raw action timings.",
            "Daily worker peaks require retained replays; unavailable worker observations are null, never inferred from wages.",
            "Production excludes movement, pickup, DROP and selective PLACE delivery; exact operation means are retained.",
            "Terminal escape classification does not establish optimal abandonment.",
            "Input source hashes are recorded in original manifests; unfrozen changing harness files are not re-certified here.",
        ],
        "policies": [],
        "worker_replays": [value for value in workers.values() if value],
    }
    for digest, indexed in policies.items():
        if not indexed.keys() <= policies[champion].keys():
            raise ValueError("Champion is missing candidate scenarios")
        old = [policies[champion][key] for key in sorted(indexed)]
        new = [indexed[key] for key in sorted(indexed)]
        comparison = compare(old, new, report["weights"])
        rng = np.random.default_rng(20260910)
        samples = rng.integers(len(comparison["seeds"]), size=(10000, len(comparison["seeds"])))
        for opponent in opponents:
            rows = [r for r in new if r["opponent"] == opponent]
            scores = np.array([match_score(r) for r in rows])
            blocks = scores.reshape(-1, 2).mean(axis=1)
            old_rows = [r for r in old if r["opponent"] == opponent]
            cash_changes = [
                after["cash"] - after["opponent_cash"] - before["cash"] + before["opponent_cash"]
                for before, after in zip(old_rows, rows, strict=True)
                if all(
                    value is not None and math.isfinite(value)
                    for row in (before, after)
                    for value in (row["cash"], row["opponent_cash"])
                )
            ]
            # Missing outcomes stay in the score denominator. Do not impute a
            # cash change or bootstrap an incomplete collection of seed pairs.
            cash_blocks = (
                np.array(cash_changes).reshape(-1, 2).mean(axis=1)
                if len(cash_changes) == len(rows)
                else None
            )
            comparison["opponents"][opponent].update(
                wins=int(sum(score == 1 for score in scores)),
                draws=int(sum(score == 0.5 for score in scores)),
                score_ci95=np.quantile(blocks[samples].mean(axis=1), [0.025, 0.975]).tolist(),
                mean_paired_gap_change_ci95=(
                    np.quantile(cash_blocks[samples].mean(axis=1), [0.025, 0.975]).tolist()
                    if cash_blocks is not None
                    else None
                ),
                behavior=diagnostics(rows, workers),
            )
        report["policies"].append({"identity": identities[digest], "comparison": comparison})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", nargs="+", type=Path, required=True)
    parser.add_argument("--champion", default=CHAMPION, help="Exact SHA-256 present in the inputs")
    parser.add_argument("--replay-workers", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(
        [p for group in args.input for p in group], args.champion, args.replay_workers
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for policy in report["policies"]:
        print(policy["identity"]["name"], json.dumps(policy["comparison"]["aggregate"]))


if __name__ == "__main__":
    main()
