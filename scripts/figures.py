"""Generate portfolio figures exclusively from saved benchmark outputs."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from summarize_benchmark import match_score, summarize

COLORS = {"v5": "#9aabb7", "v6": "#e5a43b", "v7": "#168477", "ink": "#193349"}
LABELS = {
    "data/raw/reference-lonespear/main.py": "lonespear\nMixed livestock",
    "data/raw/reference-gzm/main.py": "GzmCR\nMixed farming",
    "data/raw/reference-tina/agent.py": "TinaawhyteD\nCrop-only",
}


def read(name):
    return json.loads(Path(name).read_text())["episodes"]


def save(fig, name):
    fig.savefig(Path("reports/figures") / name, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", default="reports/results/holdout-v7.json")
    args = parser.parse_args()
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": COLORS["ink"],
            "text.color": COLORS["ink"],
            "axes.titleweight": "bold",
        }
    )
    rows = read(args.evaluation)
    report = summarize(rows)
    opponents = list(report["opponents"])
    values = [report["opponents"][o]["score"] * 100 for o in opponents]
    lower = [
        v - report["opponents"][o]["ci95"][0] * 100 for v, o in zip(values, opponents, strict=True)
    ]
    upper = [
        report["opponents"][o]["ci95"][1] * 100 - v for v, o in zip(values, opponents, strict=True)
    ]
    fig, ax = plt.subplots(figsize=(8.5, 4.3))
    ax.bar(range(len(opponents)), values, color=[COLORS["v7"], "#265777", "#8ca6b8"], width=0.56)
    ax.errorbar(
        range(len(opponents)),
        values,
        yerr=[lower, upper],
        fmt="none",
        color=COLORS["ink"],
        capsize=5,
    )
    ax.axhline(50, color="#a5a5a5", linestyle="--", linewidth=1)
    ax.set(
        xticks=range(len(opponents)),
        xticklabels=[LABELS.get(o, o) for o in opponents],
        ylabel="Match score (%)",
        ylim=(0, 112),
        title="Frozen v7 against independent implementations",
    )
    for x, value in enumerate(values):
        ax.text(x, 105, f"{value:.1f}%", ha="center", fontweight="bold")
    ax.text(
        0,
        -0.28,
        f"{report['primary']['seeds']} seeds x both seats per opponent. 95% intervals resample whole seeds.\n"
        "Crop-only reference is supplementary; primary score weights the first two equally.",
        transform=ax.transAxes,
        fontsize=9,
    )
    save(fig, "performance-v7.png")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for version, filename in (
        ("v5", "audit-v5.json"),
        ("v6", "audit-v6.json"),
        ("v7", "audit-v7.json"),
    ):
        games = [
            r for r in read("reports/results/" + filename) if "reference-lonespear" in r["opponent"]
        ]
        for column, field in enumerate(("cash", "footprint")):
            traces = np.array(
                [
                    [
                        d["cash"] if field == "cash" else d["crops"] + d["animals"]
                        for d in r["daily"]
                    ]
                    for r in games
                ]
            )
            x = np.array([d["step"] / 24 for d in games[0]["daily"]])
            axes[column].plot(
                x, traces.mean(axis=0), label=version, color=COLORS[version], linewidth=2.5
            )
        axes[0].set(
            ylabel="Mean cash", xlabel="Game day", title="Cash available through the season"
        )
        axes[1].set(
            ylabel="Productive tiles", xlabel="Game day", title="Realized production footprint"
        )
    for ax in axes:
        ax.legend(frameon=False)
        ax.grid(axis="y", alpha=0.15)
    fig.text(
        0.12,
        -0.03,
        "Development audit: seeds 0, 17, 42, 103; both seats against pinned lonespear. Mean of eight games.",
        fontsize=9,
    )
    save(fig, "trajectories-v7.png")

    control = [
        r
        for r in read("reports/results/production-screen-4.json")
        if "delivery_control" in r["candidate"]
    ]
    matching = read("reports/results/screen-matching.json")
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.8))
    metrics = []
    for games in (control, matching):
        travel = [
            sum(
                r["realized_actions"].get("success:" + d, 0)
                for d in ("NORTH", "SOUTH", "EAST", "WEST")
            )
            for r in games
        ]
        work = [
            sum(
                v
                for k, v in r["realized_actions"].items()
                if k.startswith("success:")
                and k.split(":")[1] not in ("NORTH", "SOUTH", "EAST", "WEST")
            )
            for r in games
        ]
        metrics.append(
            [np.mean([match_score(r) for r in games]) * 100, np.mean(travel), np.mean(work)]
        )
    for index, (title, label) in enumerate(
        (("Match score", "%"), ("Travel", "Moves / game"), ("Successful work", "Actions / game"))
    ):
        vals = [m[index] for m in metrics]
        axes[index].bar(["Greedy", "Joint"], vals, color=[COLORS["v5"], COLORS["v7"]], width=0.55)
        axes[index].set(title=title, ylabel=label, ylim=(0, max(vals) * 1.18))
        for x, v in enumerate(vals):
            axes[index].text(x, v * 1.03, f"{v:,.1f}", ha="center", fontsize=10)
    fig.text(
        0.12,
        -0.03,
        "Scheduler ablation: seeds 5 and 11, both seats, both primary references (8 games each). Development data.",
        fontsize=9,
    )
    fig.tight_layout()
    save(fig, "assignment-ablation.png")


if __name__ == "__main__":
    main()
