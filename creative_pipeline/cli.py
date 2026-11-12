"""Command-line entry point.

  python -m creative_pipeline examples/brief.yaml
  python -m creative_pipeline examples/brief.yaml --provider openai --out outputs
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .brief import BriefError, load_brief
from .pipeline import DEFAULT_MANUAL_MINUTES, run
from .providers import get_provider


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="creative_pipeline", description="Generate social ad creatives from a campaign brief.")
    ap.add_argument("brief", help="path to brief .yaml/.yml/.json")
    ap.add_argument("--assets", default=None, help="input assets folder (default: <brief dir>/assets)")
    ap.add_argument("--out", default="outputs", help="output folder (default: outputs)")
    ap.add_argument("--provider", default="auto", choices=["auto", "openai", "mock"],
                    help="image generator; auto = openai if OPENAI_API_KEY is set, else mock")
    ap.add_argument("--manual-minutes", type=int, default=DEFAULT_MANUAL_MINUTES,
                    help="assumed manual minutes per creative, for the time-saved metric")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO, format="%(message)s")

    try:
        brief = load_brief(args.brief)
    except BriefError as e:
        print(f"Brief error: {e}", file=sys.stderr)
        return 2

    assets = Path(args.assets) if args.assets else Path(args.brief).parent / "assets"
    report = run(brief, assets, Path(args.out), get_provider(args.provider), args.manual_minutes)

    s = report.summary()
    print(f"\n{s['creatives']} creatives in {s['run_seconds']}s | heroes reused {s['heroes_reused']}, "
          f"generated {s['heroes_generated']} | flagged {s['flagged_for_review']} | "
          f"~{s['est_minutes_saved']} designer-minutes saved")
    print(f"Report: {Path(args.out) / brief.campaign_id / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
