"""Plot matched second-cycle results from the saved comparison summary."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--label", required=True, help="State validation or exploratory development"
    )
    args = parser.parse_args()
    report = json.loads(args.summary.read_text())
    names, rows = [], []
    for pool in ("anchor", "challenge"):
        for opponent, row in report[pool]["opponents"].items():
            names.append(
                Path(opponent)
                .parent.name.removeprefix("reference-")
                .replace("gzm", "GzmCR")
                .replace("cok", "COK")
                .replace("seyam", "Seyam")
            )
            rows.append(row)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1.2, 1]}
    )
    y = np.arange(len(rows))
    for offset, key, color, label in (
        (-0.17, "incumbent_score", "#355C7D", "v7 release"),
        (0.17, "challenger_score", "#168477", "Expanded challenger"),
    ):
        values = [100 * row[key] for row in rows]
        left.barh(y + offset, values, height=0.3, color=color, label=label)
        for yi, value in zip(y + offset, values, strict=True):
            left.text(value + 1, yi, f"{value:.1f}%", va="center", fontsize=9)
    left.set(yticks=y, yticklabels=names, xlim=(0, 112), xlabel="Match score (%)")
    left.invert_yaxis()
    left.legend(loc="lower right", fontsize=9, frameon=False)
    delta = np.array([row["score_delta"] for row in rows]) * 100
    intervals = np.array([row["delta_ci95"] for row in rows]) * 100
    right.errorbar(
        delta,
        y,
        xerr=np.stack((delta - intervals[:, 0], intervals[:, 1] - delta)),
        fmt="o",
        color="#168477",
        capsize=5,
    )
    right.axvline(0, color="#a0a8ad", linewidth=1)
    right.set(
        yticks=y,
        yticklabels=[],
        xlabel="Paired score change (percentage points)",
        ylim=left.get_ylim(),
    )
    for axis in (left, right):
        axis.grid(axis="x", alpha=0.15)
        axis.set_axisbelow(True)
    fig.suptitle(args.label, x=0.06, ha="left", fontweight="bold")
    seeds = report["anchor"]["seeds"]
    fig.text(
        0.06,
        0.025,
        f"{len(seeds)} seeds · both seats · 95% intervals resample complete seeds · COK and Seyam share a public route lineage",
        fontsize=9,
        color="#52616b",
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.93))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180, facecolor="white")
    plt.close(fig)
    args.output.with_suffix(".json").write_text(
        json.dumps(
            {
                "summary": str(args.summary),
                "label": args.label,
                "generator": "scripts/phase2_figures.py",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
