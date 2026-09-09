"""Render measured matchup, execution, and development-ablation figures."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

try:
    from .evidence_io import read_result
    from .phase2_compare import match_score
except ImportError:
    from evidence_io import read_result
    from phase2_compare import match_score


BLUE, TEAL, GOLD = "#355C7D", "#168477", "#DCA44A"
GRAY = "#52616B"
OPPONENTS = ("lonespear", "gzm", "seyam", "cok")
DISPLAY = {"lonespear": "lonespear", "gzm": "GzmCR", "seyam": "Seyam", "cok": "COK"}
HARD_SEEDS = (2000, 2003, 2009, 2013)
ABLATIONS = (
    ("Startup10", "febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b"),
    (
        "Flexible herd + capacity",
        "521467d45a0e2739d634ec628009753fe8e3844633bdc6e6f733f45521489a59",
    ),
    (
        "+ Feed deadline reservations",
        "59b46457c6511d5df959a95a8c4eb8297e649e0a95b2ae7886f2042e7a60bab3",
    ),
)


def style():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": GRAY,
            "xtick.color": GRAY,
            "ytick.color": GRAY,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def file_identity(path):
    path = Path(path)
    return {"path": path.as_posix(), "sha256_file": hashlib.sha256(path.read_bytes()).hexdigest()}


def write_figure(fig, output, metadata):
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    metadata = {"generator": "scripts/phase3_figures.py", **metadata}
    output.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def opponent_key(path):
    return Path(path.replace("\\", "/")).parent.name.removeprefix("reference-")


def row_identity(manifest, row):
    candidate = row["candidate"]
    direct = manifest["hashes"].get(candidate)
    if direct:
        return direct
    declared = manifest.get("candidates", {}).get(candidate, {}).get("sha256")
    if declared:
        return declared
    if candidate.replace("\\", "/") == manifest.get("executed_candidate", "").replace("\\", "/"):
        return manifest["hashes"][manifest["arguments"]["candidate"]]
    raise ValueError("Episode candidate is absent from source provenance")


def ordered_opponents(report):
    rows = report["pools"]["equal_four"]["opponents"]
    return sorted(rows, key=lambda path: OPPONENTS.index(opponent_key(path)))


def matchup(report, output, stage, labels, metadata):
    pool = report["pools"]["equal_four"]
    paths = ordered_opponents(report)
    rows = [pool["opponents"][path] for path in paths]
    y = np.arange(len(rows))
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6), width_ratios=(1.2, 1))
    for offset, key, color, label in (
        (-0.17, "incumbent_score", BLUE, labels[0]),
        (0.17, "challenger_score", TEAL, labels[1]),
    ):
        values = [100 * row[key] for row in rows]
        left.barh(y + offset, values, height=0.29, color=color, label=label)
        for location, value in zip(y + offset, values, strict=True):
            left.text(value + 1, location, f"{value:.1f}%", va="center", fontsize=9)
    left.set(
        yticks=y,
        yticklabels=[DISPLAY[opponent_key(path)] for path in paths],
        xlim=(0, 113),
        xlabel="Match score (%)",
    )
    left.invert_yaxis()
    left.legend(loc="lower right", frameon=False, fontsize=9)
    for location, row in zip(y, rows, strict=True):
        low, high = np.array(row["delta_ci95"]) * 100
        delta = row["score_delta"] * 100
        right.hlines(location, low, high, color=TEAL, linewidth=2)
        right.plot([low, high], [location, location], "|", color=TEAL, markersize=9)
        right.plot(delta, location, "o", color=TEAL)
    right.axvline(0, color="#A5ADB3", linewidth=1)
    right.set(
        yticks=y,
        yticklabels=[],
        ylim=left.get_ylim(),
        xlabel="Paired score change (percentage points)",
    )
    for axis in (left, right):
        axis.grid(axis="x", alpha=0.15)
        axis.set_axisbelow(True)
    fig.suptitle(
        f"{stage.capitalize()}: matched opponent comparison", x=0.055, ha="left", fontweight="bold"
    )
    fig.text(
        0.055,
        0.025,
        f"{len(pool['seeds'])} seeds, both seats; 95% intervals resample whole paired seeds. "
        "COK and Seyam share public route ancestry.",
        fontsize=8.5,
        color=GRAY,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 0.93))
    write_figure(fig, output, {**metadata, "stage": stage, "plotted_opponents": pool["opponents"]})


def matched_rows(report, manifest, role):
    if manifest.get("complete") is not True:
        raise ValueError("Cannot plot a partial benchmark")
    pool = report["pools"]["equal_four"]
    expected = {
        (opponent, seed, seat)
        for opponent in pool["opponents"]
        for seed in pool["seeds"]
        for seat in (0, 1)
    }
    selected = [
        row
        for row in manifest["episodes"]
        if (row["opponent"], row["seed"], row["seat"]) in expected
    ]
    keys = [(row["opponent"], row["seed"], row["seat"]) for row in selected]
    if set(keys) != expected or len(keys) != len(expected):
        raise ValueError("Trajectory manifest does not cover the exact comparison panel")
    digest = pool["identities"][role]["sha256"]
    for row in selected:
        if row_identity(manifest, row) != digest:
            raise ValueError("Trajectory candidate identity differs from the comparison summary")
    return selected


def action_shares(rows):
    categories = ("Field work", "Handling", "Travel", "Idle", "Failed")
    fractions = []
    for row in rows:
        counts = dict.fromkeys(categories, 0)
        for key, amount in row["realized_actions"].items():
            status, operation = key.split(":", 1)
            category = (
                "Failed"
                if status == "failed"
                else "Idle"
                if status == "idle"
                else "Travel"
                if operation in {"NORTH", "SOUTH", "EAST", "WEST"}
                else "Handling"
                if operation in {"PICKUP", "DROP", "PLACE"}
                else "Field work"
            )
            counts[category] += amount
        total = sum(counts.values())
        if not total:
            raise ValueError("Missing realized worker actions")
        fractions.append([counts[category] / total for category in categories])
    return categories, np.mean(fractions, axis=0)


def behavior(report, manifests, output, stage, labels, metadata):
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.1), width_ratios=(1, 1, 1.15))
    plotted = {}
    for role, label, color in (("incumbent", labels[0], BLUE), ("challenger", labels[1], TEAL)):
        rows = matched_rows(report, manifests[role], role)
        steps = [point["step"] for point in rows[0]["daily"]]
        if any([point["step"] for point in row["daily"]] != steps for row in rows):
            raise ValueError("Daily trajectories have inconsistent observation coverage")
        cash = np.mean([[point["cash"] for point in row["daily"]] for row in rows], axis=0)
        footprint = np.mean(
            [[point["crops"] + point["animals"] for point in row["daily"]] for row in rows], axis=0
        )
        x = np.array(steps) / 24
        axes[0].plot(x, cash, color=color, linewidth=2.2, label=label)
        axes[1].plot(x, footprint, color=color, linewidth=2.2)
        categories, fractions = action_shares(rows)
        plotted[role] = {
            "daily_steps": steps,
            "mean_cash": cash.tolist(),
            "mean_living_tiles": footprint.tolist(),
            "whole_game_mean_action_shares": dict(zip(categories, fractions.tolist(), strict=True)),
        }
    colors = (TEAL, GOLD, BLUE, "#BEC7CE", "#B75151")
    left = np.zeros(2)
    for category, color in zip(categories, colors, strict=True):
        values = [
            100 * plotted[role]["whole_game_mean_action_shares"][category]
            for role in ("incumbent", "challenger")
        ]
        axes[2].barh([0, 1], values, left=left, color=color, height=0.45, label=category)
        left += values
    axes[0].set(xlabel="Day", ylabel="Mean cash (coins)")
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1000:g}k"))
    axes[1].set(xlabel="Day", ylabel="Mean living crop + animal tiles")
    axes[2].set(
        yticks=[0, 1], yticklabels=labels, xlim=(0, 100), xlabel="Whole-game worker actions (%)"
    )
    axes[2].invert_yaxis()
    axes[2].legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.23), ncol=3, fontsize=8, frameon=False
    )
    axes[0].legend(frameon=False, fontsize=9)
    for axis in axes:
        axis.grid(axis="x", alpha=0.15)
        axis.set_axisbelow(True)
    fig.suptitle(
        f"{stage.capitalize()}: realized production and execution",
        x=0.04,
        ha="left",
        fontweight="bold",
    )
    fig.text(
        0.04,
        -0.01,
        "Matched games, equal opponent weights. Worker shares average game-level fractions; "
        "PLACE includes animal placement and product delivery.",
        fontsize=8.5,
        color=GRAY,
    )
    fig.tight_layout(rect=(0, 0.09, 1, 0.93))
    write_figure(
        fig,
        output,
        {
            **metadata,
            "stage": stage,
            "measurements": plotted,
            "scope": "Daily cash/footprint means; whole-game action shares, not daily utilization",
        },
    )


def ablation(paths, output):
    manifests = [read_result(path) for path in paths]
    if any(manifest.get("complete") is not True for manifest in manifests):
        raise ValueError("Cannot plot incomplete development screens")
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    for manifest in manifests[1:]:
        for key in ("environment_version", "interpreter_sha256", "lock_sha256", "dependencies"):
            if manifest[key] != manifests[0][key]:
                raise ValueError(f"Development screens differ in {key}")
        if any(
            manifest["hashes"][opponent] != manifests[0]["hashes"][opponent]
            for opponent in opponents
        ):
            raise ValueError("Development screens use different opponent executables")
    expected = {
        (opponent, seed, seat) for opponent in opponents for seed in HARD_SEEDS for seat in (0, 1)
    }
    selected = {}
    for label, digest in ABLATIONS:
        matches = []
        for manifest in manifests:
            for row in manifest["episodes"]:
                identity = row_identity(manifest, row)
                key = (row["opponent"], row["seed"], row["seat"])
                if identity == digest and key in expected:
                    matches.append(row)
        keys = [(row["opponent"], row["seed"], row["seat"]) for row in matches]
        if len(keys) != len(expected) or set(keys) != expected:
            raise ValueError(f"Missing or duplicate exact hard-panel rows for {label}")
        selected[label] = matches
    fig, (left, right) = plt.subplots(1, 2, figsize=(11.8, 4.4), width_ratios=(1, 1.2))
    colors = (BLUE, GOLD, TEAL)
    measurements = {}
    for index, ((label, digest), color) in enumerate(zip(ABLATIONS, colors, strict=True)):
        scores, gaps = [], []
        for opponent in opponents:
            rows = [row for row in selected[label] if row["opponent"] == opponent]
            if any(row["statuses"] != ["DONE", "DONE"] for row in rows):
                raise ValueError("Ablation cash figure requires completed outcomes")
            scores.append(float(np.mean([match_score(row) for row in rows])))
            gaps.append(float(np.mean([row["cash"] - row["opponent_cash"] for row in rows])))
        y = np.arange(2) + (index - 1) * 0.24
        left.barh(y, np.array(scores) * 100, height=0.21, color=color, label=label)
        right.barh(y, gaps, height=0.21, color=color)
        for location, score in zip(y, scores, strict=True):
            left.text(score * 100 + 1, location, f"{score * 8:g}/8", va="center", fontsize=9)
        measurements[label] = {"sha256": digest, "score": scores, "mean_cash_gap": gaps}
    left.set(yticks=[0, 1], yticklabels=["Seyam", "COK"], xlim=(0, 113), xlabel="Match score (%)")
    right.set(yticks=[0, 1], yticklabels=[], xlabel="Mean cash gap (coins)")
    right.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1000:g}k"))
    right.axvline(0, color="#A5ADB3", linewidth=1)
    for axis in (left, right):
        axis.invert_yaxis()
        axis.grid(axis="x", alpha=0.15)
        axis.set_axisbelow(True)
    fig.legend(loc="lower center", ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 0.07))
    fig.suptitle(
        "Development: production capacity needs reliable feeding",
        x=0.055,
        ha="left",
        fontweight="bold",
    )
    fig.text(
        0.055,
        0.02,
        "Selected hard seeds 2000, 2003, 2009, 2013; both seats. "
        "Cumulative variants, not isolated additive effects or fresh validation.",
        fontsize=8.5,
        color=GRAY,
    )
    fig.tight_layout(rect=(0, 0.16, 1, 0.93))
    write_figure(
        fig,
        output,
        {
            "stage": "development",
            "inputs": [file_identity(path) for path in paths],
            "seeds": list(HARD_SEEDS),
            "opponents": opponents,
            "measurements": measurements,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    comparison = subparsers.add_parser("comparison")
    comparison.add_argument("--summary", required=True, type=Path)
    comparison.add_argument("--incumbent", type=Path)
    comparison.add_argument("--challenger", type=Path)
    comparison.add_argument(
        "--stage", required=True, choices=("development", "validation", "holdout")
    )
    comparison.add_argument("--incumbent-label", default="Incumbent")
    comparison.add_argument("--challenger-label", default="Candidate")
    comparison.add_argument("--output-dir", required=True, type=Path)
    experiment = subparsers.add_parser("ablation")
    experiment.add_argument(
        "--manifests",
        nargs="+",
        type=Path,
        default=[
            Path("reports/results/phase3-opening-field.json.gz"),
            Path("reports/results/phase3-interactions.json.gz"),
            Path("reports/results/phase3-funding.json.gz"),
        ],
    )
    experiment.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    style()
    if args.command == "ablation":
        ablation(args.manifests, args.output)
        return
    report = read_result(args.summary)
    if args.stage != "development" and report.get("split") != args.stage:
        raise ValueError("Figure label does not match the confirmed evaluation split")
    paths = {
        role: getattr(args, role) or Path(report["inputs"][role]["path"])
        for role in ("incumbent", "challenger")
    }
    manifests = {role: read_result(path) for role, path in paths.items()}
    for role, manifest in manifests.items():
        matched_rows(report, manifest, role)
        if (
            role in report.get("inputs", {})
            and file_identity(paths[role])["sha256_file"] != report["inputs"][role]["sha256_file"]
        ):
            raise ValueError("Input manifest differs from the confirmed summary")
    metadata = {
        "summary": file_identity(args.summary),
        "inputs": {role: file_identity(path) for role, path in paths.items()},
        "identities": report["pools"]["equal_four"]["identities"],
    }
    labels = (args.incumbent_label, args.challenger_label)
    matchup(
        report, args.output_dir / f"phase3-{args.stage}-matchups.png", args.stage, labels, metadata
    )
    behavior(
        report,
        manifests,
        args.output_dir / f"phase3-{args.stage}-behavior.png",
        args.stage,
        labels,
        metadata,
    )


if __name__ == "__main__":
    main()
