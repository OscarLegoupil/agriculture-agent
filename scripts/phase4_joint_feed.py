"""Joint critical-feed assignment experiments on two immutable observation policies."""

import argparse
import contextlib
import gzip
import hashlib
import inspect
import io
import json
from collections import Counter
from pathlib import Path
from statistics import mean

BASES = {
    "banked": "401b58a64d12a3df82ae9157a8d12a0d1e99c10c273fecb96f0d399501a9c6d4",
    "depot": "ee412dabf71824ebf32c870b021bc7ae0a3cc35d231f142c8c0fc8550d09a6ba",
}


def joint_feed_routes(
    pending, positions, inventories, shed, board, farm, cfg, hour, shed_tiles, budget=0.05
):
    """Min-cost flow reserves distinct workers and shared depot wheat before slack."""
    import sys
    import time

    stop = time.perf_counter() + budget
    targets = sorted(pending)
    count = len(positions)
    sink = 2 + count + len(targets)
    graph = [[] for _ in range(sink + 1)]

    def edge(left, right, capacity, cost):
        forward = [right, len(graph[right]), capacity, cost]
        backward = [left, len(graph[left]), 0, -cost]
        graph[left].append(forward)
        graph[right].append(backward)
        return forward

    def distance(left, right):
        return abs(left[0] - right[0]) + abs(left[1] - right[1])

    edge(0, 1, max(0, shed.get("WHEAT", 0)), 0)
    safe = sum(shed.values()) + sum(sum(inv.values()) for inv in inventories) <= cfg.get(
        "shedCapacity", 100
    )
    links = []
    for worker, position in enumerate(positions):
        if time.perf_counter() >= stop:
            print("joint_feed_fallback: budget", file=sys.stderr)
            return None
        inv = inventories[worker]
        sale = sum(
            n
            for item, n in inv.items()
            if item in ("CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL")
        )
        if sale and (farm["money"] < 1000 or not safe):
            continue
        fetching = not inv.get("WHEAT", 0)
        edge(1 if fetching else 0, 2 + worker, 1, 0)
        for index, target in enumerate(targets):
            home = min(shed_tiles, key=lambda p: distance(position, p) + distance(p, target))
            cost = (
                distance(position, home) + distance(home, target) + 2
                if fetching
                else distance(position, target) + 1
            )
            slack = 24 - hour - cost
            if slack >= 0:
                link = edge(2 + worker, 2 + count + index, 1, cost)
                links.append((link, target, (cost, worker, home, fetching, slack)))
    for index, (x, y) in enumerate(targets):
        # These bounded constants implement lexicographic survival, task count,
        # then travel cost: <=24 actions and <=18 productive animal targets.
        priority = 100000 if board[y][x]["consecutive_unfed"] > 0 else 1000
        edge(2 + count + index, sink, 1, -priority)
    while True:
        distances = [float("inf")] * len(graph)
        previous = [None] * len(graph)
        distances[0] = 0
        for _ in range(len(graph) - 1):
            changed = False
            for node, outgoing in enumerate(graph):
                if time.perf_counter() >= stop:
                    print("joint_feed_fallback: budget", file=sys.stderr)
                    return None
                for index, (target, _reverse, capacity, cost) in enumerate(outgoing):
                    if capacity and distances[node] + cost < distances[target]:
                        distances[target] = distances[node] + cost
                        previous[target] = node, index
                        changed = True
            if not changed:
                break
        if distances[sink] >= 0:
            break
        node = sink
        while node:
            parent, index = previous[node]
            link = graph[parent][index]
            link[2] -= 1
            graph[node][link[1]][2] += 1
            node = parent
    return [(target, route) for link, target, route in links if link[2] == 0]


def build(base, budget=0.05):
    digest = BASES[base]
    raw = gzip.decompress((Path("reports/sources") / f"{digest}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == digest
    source = raw.decode("utf-8")

    def replace(before, after):
        nonlocal source
        assert source.count(before) == 1, before
        source = source.replace(before, after)

    location = source.index("def agent(")
    helper = inspect.getsource(joint_feed_routes).replace("budget=0.05", f"budget={budget!r}")
    source = source[:location] + helper + "\n\n" + source[location:]
    replace(
        "        while pending:\n",
        "        joint_routes = joint_feed_routes(pending, positions, inventories, shed, board, farm, cfg, hour, shed_tiles)\n        while pending:\n",
    )
    replace(
        "            for target in pending:\n",
        "            for target in pending if joint_routes is None else ():\n",
    )
    replace(
        "            if not candidates:\n",
        """            if joint_routes is not None:
                for target, route in joint_routes:
                    if target in pending and route[1] not in deadline_actions and route[-1] <= 3:
                        candidates.append((0 if board[target[1]][target[0]]["consecutive_unfed"] > 0 else 1, route[-1], target, route))
            if not candidates:
""",
    )
    compile(source, "joint_feed_candidate", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--budget", type=float, default=0.05)
    parser.add_argument(
        "--verify-budget",
        action="store_true",
        help="Check saved-observation action parity without games",
    )
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-joint-feed.json"))
    parser.add_argument(
        "--summarize", action="store_true", help="Summarize the completed screen without games"
    )
    args = parser.parse_args()
    if args.verify_budget:
        verify_budget()
        return
    if args.summarize:
        summarize(args.output, args.budget)
        return
    from strategy_screen import screen

    screen(
        {"joint_" + base: build(base, args.budget) for base in BASES},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
    )
    summarize(args.output, args.budget)


def summarize(path, budget=0.006):
    raw = path.read_bytes()
    manifest = json.loads(raw)
    assert manifest["complete"] and len(manifest["episodes"]) == 32
    bases = {}
    for label, filename in [("banked", "phase4-care-corrected"), ("depot", "phase4-depot")]:
        source = json.loads((Path("data/raw") / f"{filename}.json").read_text(encoding="utf-8"))
        assert source["complete"]
        candidate = next(k for k, v in source["candidates"].items() if v["sha256"] == BASES[label])
        bases[label] = {
            (row["opponent"], row["seed"], row["seat"]): row
            for row in source["episodes"]
            if row["candidate"] == candidate
        }
        for opponent in manifest["declared_panel"]["opponents"]:
            assert manifest["hashes"][opponent] == source["hashes"][opponent]
    results = []
    for candidate, metadata in manifest["candidates"].items():
        label = metadata["name"].removeprefix("joint_")
        assert hashlib.sha256(build(label, budget).encode()).hexdigest() == metadata["sha256"]
        for opponent in manifest["declared_panel"]["opponents"]:
            rows = [
                r
                for r in manifest["episodes"]
                if r["candidate"] == candidate and r["opponent"] == opponent
            ]
            assert len(rows) == 8
            previous = [bases[label][(r["opponent"], r["seed"], r["seat"])] for r in rows]
            for old, new in zip(previous, rows, strict=True):
                assert old["configuration"] == new["configuration"]
            results.append(
                {
                    "candidate": metadata,
                    "base_sha256": BASES[label],
                    "opponent": opponent,
                    "games": len(rows),
                    "base_wins": sum(r["cash"] > r["opponent_cash"] for r in previous),
                    "wins": sum(r["cash"] > r["opponent_cash"] for r in rows),
                    "draws": sum(r["cash"] == r["opponent_cash"] for r in rows),
                    "base_mean_gap": mean(r["cash"] - r["opponent_cash"] for r in previous),
                    "mean_gap": mean(r["cash"] - r["opponent_cash"] for r in rows),
                    "paired_gap_change": mean(
                        n["cash"] - n["opponent_cash"] - o["cash"] + o["opponent_cash"]
                        for o, n in zip(previous, rows, strict=True)
                    ),
                    "stderr_turns": sum(r["stderr_turns"] for r in rows),
                    "max_action_seconds": max(r["runtime_max_seconds"] for r in rows),
                    "statuses": dict(Counter(str(r["statuses"]) for r in rows)),
                    "losses": dict(sum((Counter(r["losses"]) for r in rows), Counter())),
                }
            )
    destination = Path("reports/results")
    (destination / "phase4-joint-feed.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (destination / "phase4-joint-feed-summary.json").write_text(
        json.dumps(
            {"complete": True, "scope": "known four-seed development panel", "results": results},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(results, indent=2))


def verify_budget():
    result = {
        "complete": False,
        "kind": "budget-only saved-observation action parity",
        "cases": [],
        "artifacts": {},
    }
    for base in BASES:
        policies = []
        for budget in (0.006, 0.05):
            content = build(base, budget).encode()
            namespace = {}
            exec(content, namespace)
            policies.append(namespace["agent"])
            result["artifacts"][base + str(budget)] = {
                "sha256": hashlib.sha256(content).hexdigest()
            }
        for seed, day in [(3029, 8), (3063, 11)]:
            source = next(Path("reports/replays/phase4-losses").glob(f"*-{seed}-0.json"))
            raw = source.read_bytes()
            replay = json.loads(raw)
            for hour in (16, 18, 20):
                obs = next(
                    s[0]["observation"]
                    for s in replay["steps"]
                    if s[0]["observation"]["day"] == day and s[0]["observation"]["hour"] == hour
                )
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    actions = [policy(obs, replay["configuration"]) for policy in policies]
                assert actions[0] == actions[1] and not stderr.getvalue()
                result["cases"].append(
                    {
                        "base": base,
                        "seed": seed,
                        "day": day,
                        "hour": hour,
                        "replay_sha256": hashlib.sha256(raw).hexdigest(),
                        "actions_equal": True,
                        "stderr": "",
                    }
                )
    result["complete"] = True
    Path("reports/results/phase4-joint-budget-parity.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
