# Creative Automation Pipeline (POC)

A local command-line tool that turns one campaign brief into a full set of localized social ad creatives: every product × every market language × every aspect ratio. It runs brand and legal checks on each one and writes a report.

One command produces **18 finished creatives in under a second** (2 products × 3 locales × 3 ratios) with the offline generator. With a live GenAI model, the time is mostly the image calls, and each new hero is generated **once** and then reused.

> **How this was built.** I build with an AI-accelerated process: I direct the architecture and decisions, and Claude (Anthropic) writes and refactors code with me. My Obsidian notes keep the design record. I review every module and can walk through any line of it. This repo is a working example of that process. See [How this was built](#how-this-was-built) below. — Juan Ogando

> **Scope and proprietary boundary.** This repository is a standalone proof of concept written for the Adobe Forward Deployed AI Engineer assessment. It does **not** contain OCD RAPID STUDIO, KIKO GROUND CONTROL, OCD SPECS, or any of Ogando Creative Design's proprietary tools, proprietary workflow, proprietary product-accuracy verification, or client assets. Where this POC uses a simple public method, the production equivalent is proprietary and is not published here. Those points are marked `PROPRIETARY BOUNDARY` in the code.

---

## Quick start

```bash
git clone https://github.com/juanogando/ocdrapidstudio-creative-automation-pipeline && cd ocdrapidstudio-creative-automation-pipeline
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Offline: no API key, no cost, deterministic placeholder heroes
python -m creative_pipeline examples/brief.yaml --provider mock

# Live GenAI: OpenAI gpt-image-2 generates any missing hero (gpt-image-1 was retired 2026-10-23)
export OPENAI_API_KEY=sk-...                           # Windows: set OPENAI_API_KEY=sk-...
python -m creative_pipeline examples/brief.yaml        # 'auto' picks openai when a key exists

python -m pytest -q                                    # 6 tests, offline
```

Options: `--assets DIR` (default `<brief dir>/assets`), `--out DIR` (default `outputs`), `--provider auto|openai|mock`, `--manual-minutes N` (the assumption behind the time-saved metric), `-q`.

## Example input

`examples/brief.yaml` (fictional brand **Brisa**, two sparkling waters):

```yaml
campaign_id: brisa-summer-launch
region: Mexico & US Hispanic market
audience: Active adults 21-35 who want low-sugar refreshment
message: Real fruit. Zero sugar. All summer.
locales: [en-US, es-MX, ja-JP]
translations:
  es-MX: Fruta real. Cero azúcar. Todo el verano.
  ja-JP: 本物の果実。砂糖ゼロ。夏じゅうずっと。
brand: { name: Brisa, primary_color: "#0B3D2E", secondary_color: "#F4F1E8", logo: brisa_logo.png }
products:
  - { id: citrus-spark, name: Brisa Citrus Spark, description: ... }   # hero exists in assets/ -> reused
  - { id: mango-chili,  name: Brisa Mango Chili,  description: ... }   # no hero -> generated, saved back
prohibited_terms: [healthiest, detox]
```

`examples/assets/` holds `citrus-spark_hero.png` (an "uploaded" asset) and `brisa_logo.png`.

## Example output

```
outputs/brisa-summer-launch/
├── citrus-spark/
│   ├── 1x1/   en-US.jpg  es-MX.jpg  ja-JP.jpg      (1080×1080, feed)
│   ├── 9x16/  en-US.jpg  es-MX.jpg  ja-JP.jpg      (1080×1920, Stories/Reels)
│   └── 16x9/  en-US.jpg  es-MX.jpg  ja-JP.jpg      (1920×1080, landscape)
├── mango-chili/  ... same structure ...
├── report.json     machine-readable: every creative, every check result
└── report.md       human-readable summary + "flagged for review" list
```

Console:

```
citrus-spark   hero reused (citrus-spark_hero.png)
  1:1   en-US  OK   brisa-summer-launch/citrus-spark/1x1/en-US.jpg
  ...
mango-chili    hero generated (mango-chili_hero_generated.png)
  ...
18 creatives in 0.8s | heroes reused 1, generated 1 | flagged 0 | ~360.0 designer-minutes saved
```

Change the message to `Guaranteed detox. Zero sugar.` and the report flags the six English creatives (`legal_terms: ['detox', 'guaranteed']`) for review instead of passing them.

## How it works

```
brief.yaml ──► brief.py (validate) ──► assets.py ──► compose.py ──► checks.py ──► pipeline.py ──► outputs + report
                                         │  reuse hero from assets/
                                         └─ or providers/ (openai | mock) → generate → save back for reuse
```

| Module | Responsibility |
|---|---|
| `brief.py` | Load YAML/JSON and validate once (≥2 products, required fields, ratio format) into dataclasses |
| `providers/` | `ImageProvider` interface. `OpenAIProvider` (gpt-image-2 by default, over plain HTTP), `MockProvider` (offline, deterministic) |
| `assets.py` | Find an existing hero (explicit file → `<product_id>*` in assets), else build a prompt from the brief and generate |
| `compose.py` | Fits the whole product into each ratio (never cropped by default), brand-colour message band in a platform safe zone, auto-fit and wrapped text, logo |
| `checks.py` | Logo present, band matches brand colour, WCAG text contrast ≥ 4.5:1, every character renders in the chosen font (no "tofu" boxes), prohibited-term scan |
| `pipeline.py` | Orchestrates product × locale × ratio, writes `report.json` / `report.md`, computes metrics |
| `cli.py` | Command-line interface |

## Key design decisions

1. **Provider interface, not a hard-coded API.** The pipeline talks only to `ImageProvider.generate(prompt, size)`. Firefly, Stability or a local ComfyUI server is one new class. Nothing else changes.
2. **Generate once, compose many.** Each product gets one large square hero, and every ratio and locale is composed from it. Costs scale with *products*, not products × ratios × locales. Generated heroes are saved back into the assets folder, so the next run or market reuses them.
3. **An offline mock provider by default without a key.** Reviewers can run the whole pipeline with no account, no cost and no network. The output is deterministic, so tests are stable.
4. **The product is never cropped unless the brief says so.** By default (`hero_fit: contain`) the whole product image is fit into the space between the logo and the message band, and the photo's own studio backdrop is extended outwards so the frame stays seamless. The product pixels are never cropped, faded or covered by text. Set `hero_fit: cover` in the brief only when a brand asks for full-bleed crops. A test enforces this.
5. **Layout rules per format, not one template.** Feed (1:1) gets a bottom band. Stories (9:16) keep ~14% clear at top and bottom for platform UI. Landscape (16:9) puts the product left and the message in a side panel, so the product is never cut.
6. **Text that fits any language.** Font size shrinks until the wrapped message fits its band. CJK wraps by character with a basic rule that stops punctuation like `。` starting a line. The brief can name brand typefaces (`brand.font`, `brand.font_cjk`); otherwise system fonts are used. If a market's characters are missing from the font, the glyph check flags the creative instead of shipping empty boxes. This check exists because an early test render of the Japanese posts came out as boxes on a machine with no Japanese font.
7. **Checks flag, they don't block.** A failed check still renders the file but lists it under "Flagged for review". That keeps approvers in the loop on judgment calls (pain point 3) without stopping the batch.
8. **Metrics from the business goals.** The report counts creatives produced, heroes reused vs generated, and run time, and estimates designer-minutes saved against an explicit, overridable assumption (`--manual-minutes`, default 20).

## Assumptions and limitations

- **Translations come from the brief.** I chose approved copy over machine translation for regulated ad copy. Wiring an LLM translator in as a fallback is a small addition.
- **Legal terms are checked as written.** The default and brief lists are English. A translated message is only checked against terms in its own language if the brief includes them. A per-locale term list is the next step.
- **Cropping is geometric** (centred, biased upward), not saliency-based. A product far off-centre in an uploaded asset could be clipped. Subject detection would fix that.
- **Brand checks are deliberately simple:** they confirm the logo was placed and the band colour matches. They don't detect a logo *inside* a generated image.
- **Storage is the local filesystem.** The asset lookup and save are isolated in `assets.py`, so an S3, Azure Blob or Dropbox backend can replace it.
- The OpenAI path needs your own key. Image generation costs are billed by OpenAI.

## How this was built

I built this with my standard working method, which is the method I'd bring to Adobe's customers:

1. **I set the architecture and the decisions:** the provider interface, generate-once-compose-many, per-format layout rules, never cropping the product, checks that flag rather than block, and the metrics tied to the client's goals.
2. **Claude writes and refactors code with me in short loops.** I review every module and run it, and I send back what's wrong. For example, the first 16:9 layout put the message band over the product, and Japanese lines could start with "。". Both were caught on visual review and fixed in `compose.py`.
3. **Obsidian holds the design record:** decisions, assumptions, open questions. That's where the "Key design decisions" above came from.
4. **I understand and defend the code line by line.** In the interview I'm happy to walk through any module, change it live, or extend it (a Firefly or ComfyUI provider, per-locale legal lists).

The point for a Forward Deployed role is speed with judgment. A client brief became a tested, documented, working pipeline in an afternoon, and every trade-off is written down.

## Copyright

© 2026 Juan Ogando / Ogando Creative Design LLC. All rights reserved. Published for evaluation as part of the Adobe assessment. No license is granted for reuse. OCD RAPID STUDIO, KIKO GROUND CONTROL and OCD SPECS are proprietary and are not part of this repository.
