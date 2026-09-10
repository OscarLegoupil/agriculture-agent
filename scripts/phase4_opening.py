"""Summarize recorded opening cash flows and initial animal service, without games."""

import argparse
import gzip
import hashlib
import inspect
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path


def care_priority(tile, day, animal_data):
    """Spread useful pending care over the remaining effective action days.

    Existing harvest tasks are assumed to clear held output before the target
    event; this is a scheduling priority, not a complete route feasibility model.
    """
    _, first_age, interval, cap, _, _ = animal_data
    first = tile["placed_day"] + first_age
    event = first
    while event <= day + 1:
        event += interval
    if event > 29:
        return 0.0
    next_event = first
    while next_event <= day:
        next_event += interval
    pending = 0 if next_event == day + 1 else tile.get("pending_care_bonus", 0)
    attainable_bonus = first_age - 1 if event == first else interval
    needed = max(0, min(cap - 1, attainable_bonus) - pending)
    effective_days = event - day - 1
    return 60.0 * needed / effective_days


def build(name):
    digest = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"
    raw = gzip.decompress((Path("reports/sources") / (digest + ".py.gz")).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == digest
    source = raw.decode()

    def replace(content, old, new):
        assert content.count(old) == 1
        return content.replace(old, new)

    if name == "care_slack":
        source = replace(
            source, "def agent(obs:", inspect.getsource(care_priority) + "\n\ndef agent(obs:"
        )
        source = replace(
            source,
            '            task(x, y, "CARE", 60)',
            '            priority = care_priority(tile, day, ANIMALS[tile["animal"]])\n'
            "            if priority > 0:\n"
            '                task(x, y, "CARE", priority)',
        )
    elif name == "early_herd":
        source = replace(source, "    if day < 8:", "    if day < 4:")
    else:
        raise ValueError(name)
    compile(source, name, "exec")
    return source


def diagnose():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    ledger_path = Path("data/interim/phase4-loss-ledgers.json")
    ledgers = json.loads(ledger_path.read_bytes())
    result = []
    for recorded in ledgers["replays"]:
        if "3029-" not in recorded["path"]:
            continue
        path = Path(recorded["path"])
        replay = json.loads(path.read_bytes())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == recorded["sha256"]
        services = [Counter(), Counter()]
        for before, after in zip(replay["steps"][:264], replay["steps"][1:265], strict=True):
            for seat in (0, 1):
                obs = before[seat]["observation"]
                farm, private = deepcopy(obs["farms"][seat]), deepcopy(obs["private"])
                action = after[seat]["action"] or {}
                actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
                for unit, work in enumerate(actions):
                    pos = game._farmer_position(farm, unit)
                    tile = deepcopy(farm["tiles"][pos[1]][pos[0]]) if pos else None
                    game._apply_unit_action(
                        farm, private, unit, work, len(farm["tiles"]), obs["day"], 24
                    )
                    if (
                        not isinstance(tile, dict)
                        or "animal" not in tile
                        or tile["placed_day"] != 0
                    ):
                        continue
                    if work[0] not in ("FEED", "CARE"):
                        continue
                    field = "fed_today" if work[0] == "FEED" else "cared_today"
                    if not tile[field] and farm["tiles"][pos[1]][pos[0]][field]:
                        services[seat][f"day{obs['day']}:{tile['animal']}:{work[0]}"] += 1
        players = []
        for seat, player in enumerate(recorded["players"]):
            cumulative = Counter()
            for row in player["daily"][:10]:
                cumulative.update(row["ledger"])
            players.append(
                {
                    "first_ten_days_ledger": cumulative,
                    "daily_through_day10": player["daily"][:11],
                    "initial_cohort_service": services[seat],
                }
            )
        result.append(
            {"replay": recorded["path"], "sha256": recorded["sha256"], "players": players}
        )
    output = {
        "scope": "Offline actual opening cash flows, zero new games",
        "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        "replays": result,
    }
    target = Path("reports/results/phase4-opening-audit.json.gz")
    target.write_bytes(gzip.compress((json.dumps(output, indent=2) + "\n").encode(), mtime=0))
    for row in result:
        print(row["replay"])
        for seat, player in enumerate(row["players"]):
            print(seat, player["initial_cohort_service"])


def screen(args):
    from benchmark import episode, provenance, snapshot

    joint = json.loads(Path("data/raw/phase4-joint-field.json").read_bytes())
    assert joint.get("complete") is True, "Wait for joint-field workers to finish"
    assert 1 <= args.workers <= 4
    assert not args.output.exists(), "Do not overwrite an existing experiment"
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    identities = {
        "care_slack": "adce3c00296b534851a9892ad821904e073e9b6b4d17ab23010815d3c25876e2",
        "early_herd": "b343911959b3204ee44f131ee0aa39192ff68698c45ddf8f577dff2b6cda127e",
    }
    manifest = {
        **provenance([*opponents, __file__]),
        "base_sha256": "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325",
        "scope": "32 authorized known-development games; no automatic extension",
        "budget_games": 32,
        "seeds": [3000, 3017, 3042, 3063],
        "candidates": {},
        "episodes": [],
        "complete": False,
    }
    tasks = []
    for name, expected in identities.items():
        raw = build(name).encode()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == expected, "Candidate differs from declared screen identity"
        path = Path("data/interim/phase4-opening") / name / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        manifest["candidates"][str(path)] = {
            "name": name,
            "sha256": digest,
            "snapshot": snapshot(path),
        }
        tasks.extend(
            (str(path), opponent, seed, seat, None)
            for opponent in opponents
            for seed in manifest["seeds"]
            for seat in (0, 1)
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(
                manifest["candidates"][row["candidate"]]["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )
    assert len(manifest["episodes"]) == len(tasks) == 32
    assert (
        len({(r["candidate"], r["opponent"], r["seed"], r["seat"]) for r in manifest["episodes"]})
        == 32
    )
    for path, metadata in manifest["candidates"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == metadata["sha256"]
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-opening.json"))
    args = parser.parse_args()
    if args.screen:
        screen(args)
    else:
        diagnose()


if __name__ == "__main__":
    main()
