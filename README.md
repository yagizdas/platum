# Mensa Plate

A tiny static lunch picker for TUM students at **Mensa Arcisstraße**. Choose Bulk, Cut, or Budget and optionally Vegan. Every recommendation uses one primary main, an optional secondary scoop, and optional side, soup, and dessert, served in whole scoops or one piece.

Python generates JSON; a single vanilla `index.html` reads it. No server, accounts, or runtime API calls from the browser. Nutrition tagging uses **Gemini 3.8 Flash** (`gemini-3.8-flash`), per the updated model choice.

## Local setup

Use Python 3.12+ (including timezone data) and a Gemini API key with access to `gemini-3.8-flash`.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt

# Read the key without putting it in shell history (Bash or zsh):
read -rs GEMINI_API_KEY
export GEMINI_API_KEY

python scrape.py
python tag.py
python pick.py
python -m http.server 8000 --bind 127.0.0.1
```

Open <http://127.0.0.1:8000>. Serve over HTTP; opening `index.html` directly cannot fetch JSON reliably. The site works at a GitHub Pages repository subpath because its fetch URL is relative.

Alternatively, put `GEMINI_API_KEY=your-key` in a local **`.env`** at the repository root. It is git-ignored and read only by the Python tagger and optional judge. An exported environment variable takes precedence. Never put the key in `config.yaml`, JSON data, or the frontend. To make it available to an already running coding-agent session, the local `.env` method avoids depending on environment changes in a separate terminal.

`scrape.py` defaults to today's **Europe/Berlin** date. All script file defaults resolve from this repository, regardless of your working directory. All three commands must succeed before deploying.

## Data flow and files

```text
official HTML + eat-api prices → scrape.py → data/menu.json
                       Gemini → tag.py    → data/dish_cache.json
             menu + tag cache → pick.py   → data/today.json → index.html
```

`data/menu.json` retains names, station, raw station, deterministic vegan/vegetarian status, markers, allergen/additive codes, source labels, and prices. It includes only the requested date. `data/dish_cache.json` maps normalized names to validated tag objects; keep it committed so repeated dishes do not make more paid calls. `data/today.json` contains six variants (`bulk_all`, `cut_all`, `budget_all`, `bulk_vegan`, `cut_vegan`, `budget_vegan`), plate items, totals, and a one-line summary.

The tagger calls Gemini for each new normalized name. When Gemini returns **HTTP 503** or a request **times out**, it waits **30 seconds** before retrying, with a shared limit of **10 total attempts per dish**. This includes read timeouts and connection timeouts wrapped by urllib. Ten consecutive service failures mean nine waits (4½ minutes), plus API response time; each request can itself take up to 90 seconds. Retry progress and successful tags appear immediately in the Actions log. Other errors, including invalid JSON, retain one retry; mixed failures still cannot exceed ten total attempts. These limits are defined by `MAX_GEMINI_ATTEMPTS` and `SERVICE_RETRY_DELAY_SECONDS` in `tag.py` and apply to both daily Actions and local runs.

Structured JSON is validated again locally, including types, finite nutrition values, role/texture, and portion bounds. Each successful tag is saved immediately and atomically, even if a later dish fails. The cache key uses Unicode normalization, case folding, and punctuation/whitespace normalization. Recipe changes with the same name reuse the estimate; delete that exact cache entry to intentionally retag it. Changing model does not invalidate existing entries.

The [official menu](https://www.studierendenwerk-muenchen-oberbayern.de/gastronomie/speiseplan/speiseplan_421_-de.html) defines which dishes exist. eat-api adds prices only for a conservative normalized-name match; there is no fuzzy matching. If the official source fails or its expected structure changes, the smaller eat-api menu is an explicitly flagged fallback. If eat-api fails, official dishes still work with configured prices. Both sources failing stops the pipeline instead of inventing a closed day.

The saved official HTML uses `#c-schedule .c-schedule__item`, `.c-schedule__header`, `li.c-menu-dish-list__item`, `.c-menu-dish__title`, and `.stwm-artname`. These selectors were inspected in the actual downloaded HTML before implementation. Vegan means official `data-essen-fleischlos="2"`, its vegan icon, or an explicit `v` marker; unknown is false. On an API-only fallback, only its `VEGAN` label qualifies. The LLM never decides vegan status. Blank official station labels are retained; only explicitly grouped dessert rows inherit the Dessert station.

## Prices and scoops

Edit **`config.yaml`**, then rerun `scrape.py` and `pick.py`. No retagging is needed for price or scoop changes.

```yaml
prices:
  default_per_100g: 0.90
  station_per_100g:
    Studitopf: 0.33
  meat_base: 1.00
  fish_base: 1.50
  flat_by_station:
    Pizza: 5.00

portions:
  default_scoop_g: 150
  station_scoop_g:
    Studitopf: 150
    Dessert (Glas): 100
  max_plate_g: 650
```

The checked-in station scoop overrides are initially empty. eat-api student prices take precedence; its `base_price` is charged once per dish, plus the weight rate. Unknown or malformed billing units fall back to category rules. With category rules, fish takes its base surcharge and meat takes its base surcharge; marked vegetarian/vegan dishes do not get a meat surcharge based on a word like “Schnitzel.” An unlabeled dish uses the default rate. Dessert fallback prices are therefore weight estimates unless eat-api supplies a fixed price. No unlisted generic rice, bread, or side is invented.

Costs are rounded **per dish** to euro cents, then summed. Nutrition is a rough estimate; portion size, recipe, and the actual checkout weight can differ.

## Plate rules

Brute force considers every allowed whole-scoop portion within each dish's typical range and every valid combination. Per-piece food is always one piece and must also be within that range. Every plate has one primary main and may add one different main as **exactly one non-liquid, non-piece scoop**, marked `main_side`. This secondary serving can be smaller than the usual full-main minimum (for example, a 150g curry scoop instead of a 250g main), but cannot exceed its maximum. A station's scoop override applies. Plates still allow at most one side/soup/dessert, at most one liquid item, and at most 650g total (configurable). Duplicate dishes and duplicate physical combinations are excluded.

| Goal | Objective | Constraint | Remaining tie breaks |
| --- | --- | --- | --- |
| Bulk | Highest kcal, then highest protein | At most €7 and at least 30g protein | Lower price, lower weight |
| Cut | Highest protein/kcal ratio | At least 400 kcal and 25g protein | Lower price, lower weight |
| Budget | Lowest price | At least 550 kcal | Higher protein, lower kcal, lower weight |

All thresholds are in `config.yaml`. Vegan filters dishes **before** enumeration. If a vegan Bulk or Cut variant cannot reach its protein floor, it retries without that floor, retaining the price, calorie, portion, and weight rules. The variant has `relaxed: true` and a visible explanatory `note`. Other unavailable goals remain unavailable. There is no extra price limit for Cut or Budget.

```yaml
goals:
  bulk_max_eur: 7.00
  bulk_min_protein_g: 30
  cut_min_protein_g: 25
  cut_min_kcal: 400
  budget_min_kcal: 550
llm:
  enabled: true
  top_k: 10 # 1–10 code-ranked candidates per variant
```

`judge.py` makes **one Gemini call covering all six variants**. It sees only candidate IDs, German/English names, stations, servings, and code-computed price/kcal/protein totals. It selects a coherent lunch from each variant's top candidates and returns a short English reason. It cannot add dishes or supply numbers. `plate_result()` always computes the final items and totals from the selected original candidate.

Each variant records `picked_by: "llm" | "rules"` and `reason` (a string or null). Invalid/missing IDs, extra dish or total fields, invalid reasons, missing keys, malformed JSON, and request errors fall back independently to the rule-based top plate. Judge failures never stop the pipeline; status explanations for unavailable variants use `message`. The UI renders reasons and relaxation notes as text.

`data/judge_cache.json` records the attempt per menu date, including failed calls, so manual reruns do not make another daily judge call. Results are reused only when model, prompt, and candidates match; a changed menu or price set uses rules instead of stale IDs. Missing keys and closed menus do not consume a daily attempt. Delete that date's entry only when intentionally requesting another judgment. The judge uses the existing urllib Gemini client, temperature zero, and a JSON response schema; it has no retry loop. Disable it with `llm.enabled: false` or run `python pick.py --no-llm` for deterministic offline output.

A valid official menu without today's block writes `closed`. Tagging needs no key on closed days or when every dish is cached; the optional judge falls back to rules without a key. For an initial setup without a key, `python pick.py --allow-missing-tags` writes an honest unavailable state; this option is never used by the daily workflow. The UI also handles fetch failures and refuses to present an old menu as today's after a missed run, on weekends, or on holidays. Goal and Vegan choices persist in guarded `localStorage`; blocked storage does not break the app.

## GitHub Pages automation

1. Push these files to a GitHub repository on its default branch.
2. In **Settings → Secrets and variables → Actions**, add **`GEMINI_API_KEY`** as a repository secret.
3. In **Settings → Pages → Build and deployment**, select **GitHub Actions**.
4. Allow GitHub Actions to write repository contents. If branch protection forbids the bot's data commits, allow that workflow or adapt the data commit step to your policy.
5. Run **Actions → Daily menu and GitHub Pages → Run workflow** for the first deployment.

`.github/workflows/daily.yml` runs on weekdays at **07:30 UTC** (08:30 Munich in winter, 09:30 in summer). It runs tests, scrape → tag → pick, commits `data/`, uploads only `index.html` and `data/today.json`, and deploys with the official GitHub Pages actions. `GEMINI_API_KEY` is passed to both tag and pick. A tagging failure prevents deployment; an optional judge failure still deploys the rule-based choices. A final persistence step retains successful cache additions after a later failure, preventing repeat paid calls on the next run. Runs are serialized. GitHub schedules can be delayed; manual dispatch is also available.

`.github/workflows/test.yml` runs the offline suite for code pushes and pull requests. Tests never need a key. No GitHub remote, repository secret, or Pages setting is created by the local scripts.

**Publish the interface independently:** run **Actions → Publish current site → Run workflow**. This deploys the committed `index.html` and `data/today.json` without calling Gemini. It is useful for the first preview or frontend updates while the model service is unavailable. Pending estimates remain explicitly unavailable in the UI; this action does not manufacture plate data. The daily workflow still requires successful generation before deploying new recommendations. Both publishing paths share a concurrency lock.

## Tests and fixture replay

```sh
python -m pytest -q

# Reproduce the real menu from Monday, 2 November 2026, offline:
python scrape.py --date 2026-11-02 \
  --html tests/fixtures/arcisstr.html \
  --api-json tests/fixtures/eat-api-2026-45.json
python tag.py    # uses Gemini only for names missing from the cache
python pick.py

# Fully offline picker (no judge request):
python pick.py --no-llm

# Refresh the official fixture deliberately; adjust parser assertions if needed:
python scrape.py --save-html tests/fixtures/arcisstr.html
```

Fixtures are unmodified responses fetched from the official URL and [eat-api week 45](https://tum-dev.github.io/eat-api/mensa-arcisstr/2026/45.json) on **2026-11-02**. That day's official menu has **12 dishes**; eat-api has **6**. Tests check the real parser, official superset, closed days, deterministic diet markers, source failure behavior, ISO week-year boundaries, price units, all plate constraints and goal ordering, piece weights, station scoop overrides, cache reuse, Gemini request shape, JSON validation, and retry behavior. Synthetic estimates in tests are separate from the production cache.

The offline suite covers real fixture parsing, ranking and lunch minimums, secondary scoops, vegan relaxation, all judge fallbacks, strict candidate selection, daily judge caching, and tagger 503/timeout retry limits. Every model call in tests is mocked; test configuration disables the judge unless a test explicitly injects a mock. Browser checks cover all six selections, persistence, blocked storage, closed/stale/error states, and responsive layouts. Nutrition remains estimated even when the judge selects a plate.

Gemini request/schema implementation follows Google's [model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) and [structured output reference](https://ai.google.dev/gemini-api/docs/generate-content/structured-output). The model can be changed through `gemini_model` in `config.yaml`.
