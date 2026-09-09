"""Export an official HTML replay and a single-frame official renderer page."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", default="submissions/20260909-v7/main.py")
    parser.add_argument("--opponent", default="data/raw/reference-lonespear/main.py")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--frame", type=int, default=480)
    parser.add_argument("--screenshot", action="store_true")
    parser.add_argument("--chrome")
    args = parser.parse_args()
    from kaggle_environments import make

    environment = make("kaggriculture", configuration={"seed": args.seed})
    environment.run([args.artifact, args.opponent])
    destination = Path("reports/replays")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "season.json").write_text(json.dumps(environment.toJSON()), encoding="utf-8")
    (destination / "season.html").write_text(
        environment.render(mode="html", width=1280, height=900), encoding="utf-8"
    )
    environment.steps = [environment.steps[args.frame]]
    (destination / "frame.html").write_text(
        environment.render(mode="html", width=1280, height=900), encoding="utf-8"
    )
    print(destination / "frame.html")
    if args.screenshot:
        chrome = args.chrome or shutil.which("google-chrome") or shutil.which("chromium")
        if not chrome:
            chrome = "C:/Program Files/Google/Chrome/Application/chrome.exe"
        if not Path(chrome).exists():
            raise FileNotFoundError("Install Chrome/Chromium or provide --chrome PATH")
        target = Path("reports/figures/gameplay.png").resolve()
        subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--window-size=1280,900",
                "--virtual-time-budget=5000",
                "--user-data-dir=" + str(Path("data/raw/chrome-replay-profile").resolve()),
                "--screenshot=" + str(target),
                (destination / "frame.html").resolve().as_uri(),
            ],
            check=True,
            timeout=30,
            capture_output=True,
        )
        from benchmark import provenance

        metadata = {
            **provenance([args.artifact, args.opponent]),
            "seed": args.seed,
            "frame": args.frame,
            "renderer": "official kaggriculture HTML renderer",
            "viewport": [1280, 900],
        }
        target.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
