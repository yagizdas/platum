# Mensa Plate

A static lunch picker for TUM students at **Mensa Arcisstraße**. Choose Bulk, Cut or Budget, with an independent Vegan option. Each variant offers up to five lunches with different mains. Python computes portions, student prices, nutrition estimates and ranking; models propose plausible trays and describe the final choices.

The landing page is `index.html`; the picker is `menu.html`. Both retain the Bricolage Grotesque type, TUM Blue, supplied illustrations and reduced-motion behavior documented in `DESIGN.md`. The site works under a GitHub Pages repository subpath and has no browser API key or service worker.

## Run locally

Python 3.12+, Node 22+ for the JavaScript tests. Set `GEMINI_API_KEY` in the environment or a git-ignored `.env`.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scrape.py --week
python tag.py --week
python pick.py --week
python -m http.server 8000 --bind 127.0.0.1
```

Open <http://127.0.0.1:8000>. `--date YYYY-MM-DD` fixes the reference date. `--no-llm` uses cached proposals or deterministic fallback trays and English item names. `pair.py --week` remains available for legacy pairing knowledge; it does not decide the new plate ranking.

## Staging

Push changes to the `staging` branch, then check them at <https://yagizdas.github.io/platum/staging/>. When the staged site is ready to ship, merge `staging` into `main`; the deployment workflow publishes both sites together with the same daily menu data.

The private preference labeler is at <https://yagizdas.github.io/platum/staging/label/>. Select a ranking goal to keep its judgment count, undo, and JSON export separate. Existing browser judgments are preserved and filtered by their recorded goal. **Reset this goal** asks for confirmation and deletes only that goal's browser judgments; export first to keep a copy. Cards show calories from protein as `protein (g) × 4 ÷ kcal × 100`, rounded to a whole percentage.

To fit exported cut judgments without overwriting the bulk model:

```sh
python train_pairwise_score.py --goal cut --input /path/to/platum-cut-judgments.json --output data/models/cut-score.json
```

Training writes the model; activating it for meal scoring is a separate configuration change.

## Pipeline and history

The official menu supplies dishes and dietary markers. eat-api supplies prices only for a conservative normalized-name match. Source failures are labeled; two failed sources never manufacture a closed day. Configured rice and potato salad are appended only to real open menus. Unknown dietary status is never vegan.

`tag.py` repairs **fresh** model responses before validation: an explicit positive piece count such as “(1 Stück)”, “(2 Stück)” or “(6 Stück)” forces fixed-serving service with the portion-range midpoint, and finite out-of-range weights are clamped. `is_per_piece` means one fixed serving; `piece_weight_g` describes the entire named serving, including all pieces and named accompaniments. The optimizer keeps it at one serving and applies its base surcharge once. Existing cache entries are validated rather than automatically repaired, re-tagged or migrated. The lamb-steak (2 Stück) and Cevapcici (5 Stück) entries were explicitly corrected to fixed servings using their existing portion-range midpoints, preserving their nutrition estimates per 100g. Every new success is saved immediately. A bad dish is skipped after its retries, and later dishes and dates continue. `data/tag_failures.json` records skipped names and errors. The command succeeds if any new dish was tagged or all dishes were cached; an entirely unsuccessful tagging run still reports failure.

`pick.py --week` omits missing tags with a warning and isolates errors by date. `scrape.py` preserves existing past-date menus if a source now calls them closed or empty, using the current Berlin date. The week index, dated plates and `today.json` are written under `data/`.

On load, `menu-days.js` opens today's open menu before **14:30 Europe/Berlin**, otherwise the next open date. A valid week's older `generated_on` does not expire its individual dates. Past dates require explicit selection or `?date=YYYY-MM-DD`; fallback data cannot silently show an old meal.

## Proposals and scoring

For every open day there are **six separate proposal calls**: `bulk_all`, `cut_all`, `budget_all`, `bulk_vegan`, `cut_vegan`, `budget_vegan`. Goal instructions live in `config.yaml` under `proposals.instructions`. Vegan calls receive only confirmed vegan dishes and vegan standing sides. Inputs contain stable dish IDs, English names, roles, stations, standing-side status, existing calorie and protein/carbohydrate/fat estimates per 100g, estimated serving ranges and piece weights. Prices are not included. Each call requests 15 unranked combinations of one to three IDs; code still chooses portions and computes totals and ranking. Validation can leave fewer than 15 distinct valid combinations.

Each variant is cached at `data/proposals/YYYY-MM-DD/<variant>.json`. An existing file prevents another call, including after failure or when no key is available. Failed calls cache the fallback: every main alone and every main with each eligible standing side. Unknown IDs, repeated dishes, multiple soups, dessert-only trays and non-vegan items in vegan variants are discarded. Keep these caches committed; remove a file only when intentionally requesting new proposals.

For each combination, code tries one to three scoops per scoop-served item. Configured role/station scoop caps still apply; pieces retain their cached weight and one-piece count. There is **no whole-plate weight cap** and there are **no hard energy or protein floors**. Price affects ranking through the configured score terms, not a maximum-price filter.

With `e` = euros, `k` = kcal, `p` = protein grams and `h(x;u,d) = u*x` for nonnegative `x`, otherwise `d*x`:

```text
Bulk   = -2*e/4 - max(0,e-7) + .25*(k/e)/250 + .5*(p/e)/12 + 1.5*p/10 + h(k-500;.25,3)/300
Cut    = -e/4 - max(0,e-7) + 2*(p/k*100)/8 + .5*(p/e)/12 + h(p-30;.5,3)/15 + h(700-k;0,2)/200
Budget = -2*e/4 - max(0,e-7) + (k/e)/250 + h(k-550;.2,3)/300 + h(p-20;.2,3)/15
```

Every weight, normalizer, pivot and asymmetric slope lives under `scoring.<goal>` in `config.yaml`. All goals lose an additional point per euro above €7, a soft penalty rather than a hard price cap. Cut also deducts 0.25 points per euro across the entire price; Bulk and Budget deduct 0.5. Bulk rewards total protein linearly at 0.15 points per gram, without a protein target, with smaller value and calorie terms. The [November bulk calibration](docs/bulk-calibration-2026-11-09.md) records the comparison and its limits. Sort by score rounded to four decimals descending, price ascending, then sorted dish IDs. Keep the best portioning and up to five plates, with no repeated main in a variant. Fewer distinct mains means fewer alternatives. Score terms and total are saved under each plate's `score` and never displayed.

`judge.py` now writes only a short English title and reason for **every final plate**. `data/title_cache.json` caches this optional daily call; IDs apply copy to the existing order. Missing, invalid or failed copy cannot change plates, portions, totals or ranking. Fallback titles use short English item names. The old pairing and judge caches are retained; pairing values no longer constrain plate selection.

## Impossible-plate reports

Reporting is enabled through the production Worker at `https://mensa-plate-reports.mensa-plate-reports.workers.dev`. `report-config.js` contains the single `MENSA_REPORT_ENDPOINT` setting; an empty string hides the button and makes no backend requests. A configured endpoint enables **“Can't get this plate?”** below the plate. The sheet lists short English dish names and “Something else”, traps keyboard focus, closes on Escape, adapts to dark mode and has targets at least 44px tall. After a successful report, this device skips that plate, including after reload. The confirmation is announced and the next available plate appears.

`worker/` contains a Cloudflare Worker with D1 storage. No cookies, accounts, IP addresses or contact data are stored. The browser keeps a random UUID in `localStorage`, with an in-memory fallback when storage is blocked.

- `POST /report`: `{date, variant, plate_dish_ids, tapped_dish_id, device_id}`; the tapped value is an item ID or `"other"`.
- `GET /broken?date=YYYY-MM-DD`: `{date, broken: [plate_key, ...]}`.
- Keys are sorted dish IDs joined with `|`. Portions and variant do not change a physical tray's key; raw reports retain their variant.
- Maximum three accepted reports per device per **submission day in Berlin**, across menu dates. A single conditional SQL insert enforces this under concurrent requests.
- `BROKEN_THRESHOLD` in `worker/wrangler.toml` defaults to two distinct devices. Repeated reports by one device cannot increase its vote.
- Every accepted raw report retains menu date, variant, dish IDs, tapped dish, random device ID and submission time from day one.

The client fetches broken keys for the selected date and skips them. If all alternatives are broken, it uses the existing “No plate fits this goal today” state. An unreachable Worker never blocks lunch selection; unsuccessful submissions remain retryable.

### Deploy or test the Worker

```sh
cd worker
npm ci
npm run migrate:local
npm run dev
```

For a local browser test, temporarily set `MENSA_REPORT_ENDPOINT` to `http://127.0.0.1:8787` and serve the static site on port 8000. The Worker defaults to local storage; no Cloudflare account is required for this test.

For production:

```sh
npx wrangler login
npx wrangler d1 create mensa-plate-reports
# Replace database_id in wrangler.toml with the returned ID.
npx wrangler d1 migrations apply DB --remote
npx wrangler deploy
```

The production account and database IDs are retained in `worker/wrangler.toml`; a new deployment to another account must use its own IDs. Set `MENSA_REPORT_ENDPOINT` to the returned HTTPS Worker URL, include the site's origin in `ALLOWED_ORIGINS`, and republish the static site. Workers and D1 offer free allowances; this setup does not require enabling a paid subscription. If the localhost login callback is unavailable, use `npx wrangler login --device` to authorize through the browser with a device code. See [Cloudflare's D1 local-development guide](https://developers.cloudflare.com/d1/best-practices/local-development/) and [D1 migrations](https://developers.cloudflare.com/d1/reference/migrations/).

## Website analytics

Both the landing page and the plate picker load Cloudflare Web Analytics using the public site token registered for `yagizdas.github.io`. No secret analytics credential is included in the site. This uses Cloudflare's free, cookie-free analytics service and its existing dashboard; it adds no database tables or custom analytics server.

Open [Cloudflare Web Analytics](https://dash.cloudflare.com/26098fbb1b3bb06b1719a1e6fb10684f/web-analytics) and select `yagizdas.github.io` to see visits, page views, referring sites, countries, browsers/devices and page performance. Cloudflare's **visits** count incoming visits, not identified unique people. One visit can include both the landing page and the picker. Counts begin after installation, and new data may take a few minutes to appear; blocked JavaScript or analytics blockers can reduce the measured counts. See [Cloudflare's metric definitions](https://developers.cloudflare.com/web-analytics/data-metrics/high-level-metrics/) and [Web Analytics overview](https://developers.cloudflare.com/web-analytics/about/).

To move to a custom domain later, edit the hostname under Web Analytics → Manage site and keep the same site snippet. Also update `ALLOWED_ORIGINS` in `worker/wrangler.toml` so plate reporting accepts the new origin, update `SITE_URL` in `menu.html` for shared links, and redeploy the Worker and static site. See [Cloudflare's setup guide](https://developers.cloudflare.com/web-analytics/get-started/).

## GitHub Pages and tests

Set repository secret `GEMINI_API_KEY` and select **GitHub Actions** in Settings → Pages. `daily.yml` runs weekdays at 07:30 UTC. Scrape, tag, optional pair knowledge and pick run independently of previous generation failures. Packaging and artifact upload still run, and the deploy job accepts an uploaded artifact even if generation failed. A final failing generation status keeps partial failures visible. `publish.yml` deploys committed data without model calls. Raw reports, credentials and private model caches are never included in the static artifact.

```sh
python -m pytest -q
node --test tests/*.cjs
cd worker && npm ci && npm test
```

Tests mock model calls. Coverage includes parsing and source authority, immutable existing tags, repair and retry behavior, ten-day failure isolation, exact golden winners for all six variants, hand-computed equations, byte-identical reruns, six independent proposal caches, Berlin default dates, report fail-open behavior, and an actual `wrangler dev`/D1 integration test with concurrent rate limits and distinct-device votes. The existing fixture estimates remain test data, separate from production caches.
