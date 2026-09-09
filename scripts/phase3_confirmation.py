"""Confirm one preregistered paired panel without inferring its intended scope."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

try:
    from .evidence_io import read_result
    from .phase2_compare import compare_manifests
except ImportError:
    from evidence_io import read_result
    from phase2_compare import compare_manifests


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_protocol(protocol):
    require(protocol["schema_version"] == 1, "Unsupported protocol schema")
    for key in ("incumbent_sha256", "challenger_sha256"):
        digest = protocol[key]
        require(
            isinstance(digest, str)
            and len(digest) == 64
            and all(c in "0123456789abcdef" for c in digest),
            f"Invalid {key}",
        )
    require(
        protocol["incumbent_sha256"] != protocol["challenger_sha256"],
        "Policies must have distinct frozen identities",
    )
    opponents = set(protocol["opponent_hashes"])
    pools = protocol["pools"]
    require(set(pools) == {"anchor", "challenge", "equal_four"}, "Declare all three pools")
    require(
        len(opponents) == 4 and len(pools["anchor"]) == len(pools["challenge"]) == 2,
        "Declare exactly four primary opponents",
    )
    require(
        set(pools["anchor"]).isdisjoint(pools["challenge"])
        and set(pools["anchor"]) | set(pools["challenge"]) == opponents,
        "Anchor and challenge must partition opponents",
    )
    require(set(pools["equal_four"]) == opponents, "Equal-four pool differs")
    for name, weights in pools.items():
        expected = 0.25 if name == "equal_four" else 0.5
        require(
            all(weight == expected for weight in weights.values()), "Primary pool weights changed"
        )
    require(set(protocol["splits"]) == {"validation", "holdout"}, "Declare validation and holdout")
    for name, seeds in protocol["splits"].items():
        require(bool(seeds) and all(type(seed) is int for seed in seeds), f"Invalid {name} seeds")
        require(seeds == sorted(set(seeds)), f"Duplicate or unordered {name} seeds")
    require(
        set(protocol["splits"]["validation"]).isdisjoint(protocol["splits"]["holdout"]),
        "Validation overlaps holdout",
    )
    gates = protocol["gates"]
    require(
        gates["cok_opponent"] in pools["challenge"], "COK floor names an absent challenge opponent"
    )
    for name, floor in (
        ("anchor_min_delta", 0.05),
        ("anchor_min_family_score", 0.4),
        ("challenge_min_score", 0.5),
        ("cok_min_score", 0.4),
        ("equal_four_lower_min", 0.5),
    ):
        require(
            isinstance(gates[name], (int, float))
            and math.isfinite(gates[name])
            and floor <= gates[name] <= 1,
            f"Invalid or weakened gate: {name}",
        )
    require(0 < gates["max_action_seconds"] <= 0.5, "Runtime headroom gate weakened")


def validate_manifest(manifest, protocol, split, role):
    require(manifest.get("complete") is True, f"Incomplete {role} benchmark")
    expected = {
        (opponent, seed, seat)
        for opponent in protocol["opponent_hashes"]
        for seed in protocol["splits"][split]
        for seat in (0, 1)
    }
    rows = manifest["episodes"]
    actual = [(row["opponent"], row["seed"], row["seat"]) for row in rows]
    require(
        len(actual) == len(expected) and set(actual) == expected,
        f"{role} does not match the declared Cartesian panel",
    )
    source = manifest["arguments"]["candidate"]
    require(
        manifest["hashes"][source] == protocol[role + "_sha256"], f"Wrong frozen {role} identity"
    )
    for opponent, digest in protocol["opponent_hashes"].items():
        require(manifest["hashes"][opponent] == digest, f"Wrong opponent identity: {opponent}")
    environment = protocol["environment"]
    for key in ("environment_version", "interpreter_sha256", "lock_sha256", "dependencies"):
        require(manifest[key] == environment[key], f"Wrong {role} {key}")
    for row in rows:
        require(
            type(row["seed"]) is int and type(row["seat"]) is int, "Scenario keys must be integers"
        )
        require(
            row["resolved_seed"] == row["seed"],
            f"Resolved seed differs from requested seed: {role}",
        )
        require(
            row["configuration"] == environment["configuration"],
            f"Wrong effective configuration: {role}",
        )
        require(len(row["statuses"]) == 2, "Malformed game statuses")
        for seat, key in ((row["seat"], "cash"), (1 - row["seat"], "opponent_cash")):
            value = row.get(key)
            if row["statuses"][seat] == "DONE":
                require(
                    isinstance(value, (int, float)) and math.isfinite(value),
                    "DONE outcome has missing or non-finite cash",
                )
        for key in ("runtime_p99_seconds", "runtime_max_seconds", "seconds"):
            require(
                isinstance(row[key], (int, float)) and math.isfinite(row[key]) and row[key] >= 0,
                f"Invalid {key}",
            )


def runtime_summary(rows):
    def describe(key):
        values = np.array([row[key] for row in rows])
        return {
            "mean": float(values.mean()),
            "median": float(np.median(values)),
            "p95": float(np.quantile(values, 0.95)),
            "max": float(values.max()),
        }

    return {
        "games": len(rows),
        "game_wall_seconds": describe("seconds"),
        "per_game_action_p99_seconds": describe("runtime_p99_seconds"),
        "per_game_action_max_seconds": describe("runtime_max_seconds"),
        "quantile_scope": "Distribution across games of each game's measured action statistic; not pooled action quantiles",
        "candidate_errors": sum(row["statuses"][row["seat"]] != "DONE" for row in rows),
        "opponent_errors": sum(row["statuses"][1 - row["seat"]] != "DONE" for row in rows),
        "stderr_turns": sum(row["stderr_turns"] for row in rows),
        "fallback_scope": "Stderr turns are diagnostics, not an exact fallback count; zero establishes no observed fallback that logs to stderr",
    }


def confirm(protocol, split, incumbent, challenger):
    validate_protocol(protocol)
    require(split in protocol["splits"], "Unknown split")
    for role, manifest in (("incumbent", incumbent), ("challenger", challenger)):
        validate_manifest(manifest, protocol, split, role)
    pools = {
        name: compare_manifests(incumbent, challenger, weights)
        for name, weights in protocol["pools"].items()
    }
    telemetry = {
        "incumbent": runtime_summary(incumbent["episodes"]),
        "challenger": runtime_summary(challenger["episodes"]),
    }
    anchor, challenge, combined = (pools[name] for name in ("anchor", "challenge", "equal_four"))
    declared = protocol["gates"]
    gates = {
        "anchor_delta_at_least_declared_minimum": anchor["aggregate"]["score_delta"]
        >= declared["anchor_min_delta"],
        "anchor_delta_lower_95_bound_positive": anchor["aggregate"]["delta_ci95"][0] > 0,
        "independent_anchor_family_floor": all(
            row["challenger_score"] >= declared["anchor_min_family_score"]
            for row in anchor["opponents"].values()
        ),
        "challenge_delta_positive": challenge["aggregate"]["score_delta"] > 0,
        "challenge_score_floor": challenge["aggregate"]["challenger_score"]
        >= declared["challenge_min_score"],
        "cok_score_floor": challenge["opponents"][declared["cok_opponent"]]["challenger_score"]
        >= declared["cok_min_score"],
        "equal_four_lower_95_above_declared_floor": combined["aggregate"]["challenger_ci95"][0]
        > declared["equal_four_lower_min"],
        "candidate_errors_zero": telemetry["challenger"]["candidate_errors"] == 0,
        "local_runtime_headroom": telemetry["challenger"]["per_game_action_max_seconds"]["max"]
        < declared["max_action_seconds"],
    }
    return {
        "purpose": "One frozen preregistered panel; no selection from partial results",
        "split": split,
        "pools": pools,
        "telemetry": telemetry,
        "gates": gates,
        "statistical_runtime_gates_pass": all(gates.values()),
        "scope": "These gates do not substitute for artifact packaging/parity or hosted checks. Validation is not final holdout.",
        "uncertainty": "10000 percentile bootstrap resamples of whole seeds, RNG20260910; both seats, all opponents and both policies stay paired. Coverage and adaptive development selection are separate limitations.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--split", choices=("validation", "holdout"), required=True)
    parser.add_argument("--incumbent", required=True, type=Path)
    parser.add_argument("--challenger", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(
        args.output.resolve()
        not in {p.resolve() for p in (args.protocol, args.incumbent, args.challenger)},
        "Output would overwrite input evidence",
    )
    protocol = json.loads(args.protocol.read_bytes())
    report = confirm(
        protocol, args.split, read_result(args.incumbent), read_result(args.challenger)
    )
    report["inputs"] = {
        name: {"path": str(path), "sha256_file": hashlib.sha256(path.read_bytes()).hexdigest()}
        for name, path in (
            ("protocol", args.protocol),
            ("incumbent", args.incumbent),
            ("challenger", args.challenger),
        )
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report["gates"], indent=2))


if __name__ == "__main__":
    main()
