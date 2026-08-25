"""Render a kaggriculture episode as a standalone HTML file and open it.

Two modes:

  1. Fresh episode: pass two agent identifiers, run a game, save the HTML.
  2. From replay:   pass `--from-replay path/to/replay.json`, render that.

Output goes under `reports/replays/` by default and opens in the system
browser. Use `--no-open` to just write the file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import webbrowser
from pathlib import Path


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", Path(name).stem or name)


def render_episode(
    agent_a: str,
    agent_b: str,
    seed: int = 0,
    config: dict[str, object] | None = None,
) -> str:
    """Run a fresh episode and return the HTML replay."""
    from kaggle_environments import make

    full_config: dict[str, object] = {"episodeSteps": 720, "seed": seed}
    if config:
        full_config.update(config)
    env = make("kaggriculture", configuration=full_config)
    env.run([agent_a, agent_b])
    return str(env.render(mode="html"))


def render_replay(path: Path) -> str:
    """Reconstruct an env from a saved replay JSON and return the HTML."""
    from kaggle_environments import make

    replay = json.loads(path.read_text(encoding="utf-8"))
    config = replay.get("configuration", {}) or {}
    env = make("kaggriculture", steps=replay.get("steps") or [], configuration=config)
    return str(env.render(mode="html"))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="kagg-view",
        description="Render a kaggriculture episode as HTML and open it in a browser.",
    )
    ap.add_argument("agent_a", nargs="?", help="Built-in name or path to a .py agent")
    ap.add_argument("agent_b", nargs="?", help="Built-in name or path to a .py agent")
    ap.add_argument(
        "--from-replay", type=Path, default=None, help="Render an existing replay JSON instead"
    )
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--config", type=str, default=None, help="JSON dict of extra env configuration")
    ap.add_argument("--output", type=Path, default=None, help="Where to save the HTML")
    ap.add_argument("--no-open", action="store_true", help="Do not open the browser")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.from_replay is not None:
        html = render_replay(args.from_replay)
        default_out = Path("reports/replays") / (args.from_replay.stem + ".html")
    else:
        if not (args.agent_a and args.agent_b):
            print("error: must supply agent_a and agent_b or --from-replay", file=sys.stderr)
            return 2
        config = json.loads(args.config) if args.config else None
        html = render_episode(args.agent_a, args.agent_b, args.seed, config)
        default_out = (
            Path("reports/replays")
            / f"{_sanitize_name(args.agent_a)}-vs-{_sanitize_name(args.agent_b)}-seed{args.seed}.html"
        )

    out = args.output or default_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")

    if not args.no_open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
