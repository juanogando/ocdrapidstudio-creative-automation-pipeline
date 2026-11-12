"""The pipeline: brief -> heroes -> creatives per product x locale x ratio -> report.

Output layout:
  outputs/<campaign_id>/<product_id>/<ratio>/<locale>.jpg
  outputs/<campaign_id>/report.json  and  report.md
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import checks
from .assets import load_logo, resolve_hero
from .brief import Brief
from .compose import compose, save
from .providers import ImageProvider

log = logging.getLogger("creative_pipeline")

# Assumption used for the "time saved" metric: a designer needs ~20 minutes to
# crop, typeset and export one localized variant by hand. Override with --manual-minutes.
DEFAULT_MANUAL_MINUTES = 20


@dataclass
class CreativeRecord:
    product_id: str
    ratio: str
    locale: str
    path: str
    checks: list[dict]
    passed: bool


@dataclass
class RunReport:
    campaign_id: str
    provider: str
    heroes: dict[str, str] = field(default_factory=dict)  # product_id -> reused/generated
    creatives: list[CreativeRecord] = field(default_factory=list)
    seconds: float = 0.0
    manual_minutes_per_creative: int = DEFAULT_MANUAL_MINUTES

    @property
    def flagged(self) -> list[CreativeRecord]:
        return [c for c in self.creatives if not c.passed]

    def summary(self) -> dict:
        n = len(self.creatives)
        manual_min = n * self.manual_minutes_per_creative
        return {
            "creatives": n,
            "heroes_reused": sum(v == "reused" for v in self.heroes.values()),
            "heroes_generated": sum(v == "generated" for v in self.heroes.values()),
            "flagged_for_review": len(self.flagged),
            "run_seconds": round(self.seconds, 1),
            "est_manual_minutes": manual_min,
            "est_minutes_saved": round(manual_min - self.seconds / 60, 1),
        }


def run(brief: Brief, assets_dir: Path, out_dir: Path, provider: ImageProvider,
        manual_minutes: int = DEFAULT_MANUAL_MINUTES) -> RunReport:
    start = time.perf_counter()
    report = RunReport(brief.campaign_id, provider.name, manual_minutes_per_creative=manual_minutes)
    campaign_dir = out_dir / brief.campaign_id
    logo = load_logo(brief, assets_dir)
    band = brief.brand.primary_color if brief.brand else "#111111"
    text = brief.brand.secondary_color if brief.brand else "#FFFFFF"

    for product in brief.products:
        hero = resolve_hero(brief, product, assets_dir, provider)
        report.heroes[product.id] = hero.source
        log.info("%-14s hero %s (%s)", product.id, hero.source, hero.path.name)

        for locale in brief.locales:
            message = brief.message_for(locale)
            legal = checks.check_legal(message, brief.prohibited_terms + checks.DEFAULT_PROHIBITED)
            for ratio in brief.aspect_ratios:
                img, layout = compose(hero.image, ratio, message, locale, band, text, logo)
                path = save(img, campaign_dir / product.id / ratio.replace(":", "x"), f"{locale}.jpg")
                results = [
                    checks.check_logo(layout, logo_expected=bool(brief.brand and brief.brand.logo)),
                    checks.check_brand_color(img, layout, band),
                    checks.check_contrast(band, text),
                    legal,
                ]
                rec = CreativeRecord(product.id, ratio, locale, str(path.relative_to(out_dir)),
                                     [asdict(r) for r in results], all(r.passed for r in results))
                report.creatives.append(rec)
                log.info("  %-5s %-6s %s %s", ratio, locale, "OK  " if rec.passed else "FLAG", rec.path)

    report.seconds = time.perf_counter() - start
    write_report(report, campaign_dir)
    return report


def write_report(report: RunReport, campaign_dir: Path) -> None:
    campaign_dir.mkdir(parents=True, exist_ok=True)
    payload = {"campaign_id": report.campaign_id, "provider": report.provider,
               "summary": report.summary(), "heroes": report.heroes,
               "creatives": [asdict(c) for c in report.creatives]}
    (campaign_dir / "report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    s = report.summary()
    lines = [f"# Run report: {report.campaign_id}", "",
             f"Provider: `{report.provider}`", "",
             "| Metric | Value |", "|---|---|", *[f"| {k} | {v} |" for k, v in s.items()], "",
             "## Flagged for review", ""]
    if report.flagged:
        for c in report.flagged:
            fails = "; ".join(f"{r['name']}: {r['detail']}" for r in c.checks if not r["passed"])
            lines.append(f"- `{c.path}`: {fails}")
    else:
        lines.append("None. Every creative passed brand and legal checks.")
    (campaign_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
