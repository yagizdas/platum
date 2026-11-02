# Mensa Plate

A static lunch picker for TUM students at **Mensa Arcisstraße**. Bulk, Cut, Budget, and Vegan produce up to three coherent lunches. Python computes every portion, price and total; optional models provide cached food estimates, pairing knowledge and lunch titles.

## Setup

Python 3.12+, with GEMINI_API_KEY in the environment or a git-ignored local .env:

~~~sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scrape.py
python tag.py
python pair.py
python pick.py
python -m http.server 8000 --bind 127.0.0.1
~~~

Open <http://127.0.0.1:8000>. The app works under a GitHub Pages repository subpath. No backend, accounts, service worker, or browser API key.

## Pipeline and caches

~~~text
official HTML + eat-api prices + configured counter sides
  → scrape.py → menu.json
  → tag.py    → dish_cache.json
  → pair.py   → pairing_cache.json
  → pick.py + optional judge.py → today.json → index.html
                              ↳ judge_cache.json
~~~

The official menu defines listed dishes. eat-api supplies student prices only for a conservative normalized-name match. Official source failures may use the explicitly flagged smaller API menu. Both sources failing stops the scrape; a missing date in a valid menu is closed.

Rice and potato salad are explicit **standing sides** from the unlisted Beilagen counter. They are appended only to a successfully obtained open menu, marked standing, priced at the configured default weight rate, and labeled as usually available. They never manufacture an open day. Their vegan status comes solely from config; unconfirmed potato salad is not vegan. Official duplicate names are not appended twice.

Keep all model caches committed:

- **dish_cache.json**: per-normalized-name estimates and translations. Each valid tag is saved immediately. Tagging retries HTTP 503 and timeouts up to ten total attempts, with 30 seconds between failures; other failures get one retry. Request duration is additional to waiting time.
- **pairing_cache.json**: dishes maps names to stands_alone, pairs maps sorted normA||normB to scores, and attempts records each date. One Gemini call per date requests only missing knowledge. Types, scores and requested keys are validated; invalid entries are not saved. Failures never stop picking. Without knowledge, a non-piece dish or Pizza can stand alone, and a non-pizza piece pairs only with a non-piece, non-liquid dish. Standing sides are always partner-only and never per-piece.
- **judge_cache.json**: at most one call per menu date, including failed attempts. One request covers all six variants. The judge ranks up to three candidate IDs with short English titles; only the first has a reason. It cannot add food or return totals. Invalid variants fall back independently to code order. Cache fingerprints prevent stale IDs being reused when the model, prompt or candidates change. Missing keys use rules.

All calls use the existing urllib Gemini client and gemini_model; no extra model SDK is needed. Tests mock every call and never need a key. A closed menu makes no model call. Delete a cache entry only when intentionally requesting it again.

## Plate rules

A plate is one complete main, or two different compatible dishes: two mains or one main with a standing side. Pair score must meet pairing.min_score. Score 3 means classic, 2 normal, 1 odd, 0 incompatible.

- No soups, liquid dishes, desserts, or pairs of standing sides.
- At most one per-piece dish, always exactly one piece. Pizza/Pinsa never pairs.
- Scoop dishes use one to three configured scoops, within their typical maximum.
- A single dish also respects the typical minimum. Two-dish combinations may use smaller accompaniment portions.
- Maximum 650g per plate. **No price cap** for any goal.
- Prices are rounded per dish to cents, then summed. Nutrition is estimated per 100g.
- For each goal, keep only the best portioning per distinct dish set before taking the top candidates.

| Goal | Required | Rank |
| --- | --- | --- |
| Bulk | ≥30g protein | kcal + 4 × protein grams, then lower price |
| Cut | ≥450 kcal and ≥25g protein | protein/kcal, then lower price |
| Budget | ≥550 kcal and ≥15g protein | lower price, then higher protein |

Vegan filters by explicit menu/config status before enumeration; unknown is not vegan. If a vegan goal has no qualifying lunch, only its protein floor is relaxed and a visible note explains it. Other constraints remain.

The judge ranks only the code-built shortlist. Every final number comes from plate_result(), even after model selection. Disable it with llm.enabled: false or run python pick.py --no-llm.

Soups and desserts are exported separately as extras.all and extras.vegan, each with a code-computed serving and totals. Adding an extra is a personal tray choice, outside the plate optimizer and its weight cap. Diet labels use official positive vegan/vegetarian markers and meat/fish patterns; unknown broth is conservatively non-meatless.

## Configuration

Edit config.yaml; price/scoop changes require no retagging.

~~~yaml
pairing:
  min_score: 2
llm:
  enabled: true
  top_k: 8
goals:
  bulk_min_protein_g: 30
  bulk_protein_weight: 4
  cut_min_protein_g: 25
  cut_min_kcal: 450
  budget_min_kcal: 550
  budget_min_protein_g: 15
portions:
  default_scoop_g: 150
  station_scoop_g: {}
  max_plate_g: 650
standing_sides:
  - {name: Reis, name_en: Rice, station: Beilagen, is_vegan: true}
  - {name: Kartoffelsalat, name_en: Potato salad, station: Beilagen, is_vegan: false}
~~~

Price rules: €0.90/100g default, Studitopf €0.33/100g, meat base €1, fish base €1.50, Pizza €5 flat. Matched eat-api student prices take precedence for official dishes. Standing sides always use the default configured rate.

## Data and states

today.json schema **2** contains six goal/diet variants. A ready variant has plates (up to three), plus relaxed and note. Each plate has title, reason, picked_by, items, total, and price-estimate metadata. Each item includes code-derived diet and standing. Only the first plate has a reason.

Closed, unavailable, request-error and stale-menu states remain explicit. No partial menu is silently optimized; --allow-missing-tags is only for an honest first-run unavailable state.

## Using a plate

Use the “Other options” buttons, left/right arrow keys, or a horizontal swipe to cycle through up to three different lunches. The selected title is announced for screen readers. Changing goal or Vegan resets the option and extras.

“Add to tray” chips add optional soup or dessert to the displayed totals immediately. An “incl. extras” label identifies the larger tray. Share plate uses native sharing when available, otherwise copies the chosen lunch and selected extras with their computed totals and the site URL. Counter staples are labeled “Beilagen counter · usually there.”

The web manifest and logo-derived icons support installation. There is deliberately no service worker or offline menu cache, so installation does not create an offline copy of a stale menu.

## GitHub Pages

Set repository secret GEMINI_API_KEY and select **GitHub Actions** under Settings → Pages. The daily workflow runs weekdays at **07:30 UTC**, in this order:

~~~text
pytest → scrape → tag → pair → pick → commit data → deploy
~~~

Pairing and judging are optional and never fail deployment. Mandatory tagging failures stop deployment, while the final persistence step saves successful tags and attempt records. Runs share a concurrency lock with the manual **Publish current site** workflow, which publishes committed data without model calls.

## Offline tests and golden replay

~~~sh
python -m pytest -q
python pick.py --no-llm \
  --menu tests/fixtures/menu-2026-11-02.json \
  --cache tests/fixtures/dish-cache-2026-11-02.json \
  --pairing-cache tests/fixtures/pairing-2026-11-02.json \
  --output /tmp/mensa-golden.json
~~~

The original saved HTML has 12 dishes; the later official menu snapshot includes Fleischpflanzerl, bringing it to 13. The dated golden fixture adds the two configured counter sides. Its side kcal/protein values and pairing knowledge are **user-supplied test mocks**, not production model results; unused side carb/fat fields are test placeholders. Other dish estimates are a snapshot of the existing cache. The raw HTML fixture remains unmodified.

Tests cover real parsing, authority/closed states, prices, pairing schema/cache/fallbacks, standing-side guarantees, plate rules, distinct-lunch pools, golden rankings, judge validation and per-variant fallback. Browser checks cover six variants, alternatives, extras, safe text rendering, share, responsive layout, storage and stale/error states.
