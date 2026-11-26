# Staging A/B/C comparison

Arcisstraße has A/B/C controls for Bulk, Cut and Budget, including Vegan, Vegetarian, No pork, No beef and the combined exclusions. A keeps the existing pipeline. B enumerates all one-to-four-dish combinations and allowed portions, enforces existing goal limits plus 900g excluding soup, and returns the preference model's top five distinct dish sets. The existing Bulk B recommendations remain the same. Each dish set keeps its highest-ranked portioning; mains may be reused in different sets.

C takes the same exhaustive pool, ranks it using the existing goal preference model, retains up to twenty distinct dish sets, and asks the configured Gemini model to select up to five by candidate ID. The prompt asks for ordinary edible Mensa lunches, permits mixed mains, separate bowls and unconventional combinations, and does not impose restaurant-style pairing rules or new macro targets. The model cannot add dishes or change portions, prices, scores, or nutrition. The returned order becomes C's display order. Candidate IDs, counts, uniqueness and response fields are strictly validated.

The inspection page is `/staging/label/c/`. Choose date, goal and dietary profile; inspect all ranked candidates or just C's picks. Mathematical ranks stay visible, alongside the LLM choice order, short practical reasons, exact prompt, model version and token usage. Counts reflect actual availability: a context with fewer eligible candidates is not padded. An unavailable context or missing model selection is labeled honestly. Main-menu links preserve goal and diet.

## Running and caching

```sh
python combination_c.py --source-root /path/to/current-main-checkout
python combination_c.py --source-root /path/to/current-main-checkout --run-llm --workers 3
```

The first command counts needed calls without contacting the model. The second explicitly allows new calls. `--date` and `--variant goal_profile` select a subset. Successful selections and request/visible-response audits are saved atomically in `data/selection_c.json`. Only final response text and usage are cached; hidden model reasoning is not stored. The key is read through the existing Gemini integration and never stored in the cache. Identical goal/pool requests across dietary profiles share one fingerprint and call. Fingerprints include the exact prompt, schema, model, goal, ranked candidates, portions, scores and totals. A changed shortlist never reuses stale selections. Failed contexts remain unavailable; they are not passed off as LLM decisions using a ranking fallback.

`rescore_cached.py` is read-only with respect to the API: it generates all-goal B rankings, attaches only matching cached C choices to public day JSON, and writes the top-twenty audit data under `label/c/data/`. Existing publishing workflows copy that folder as part of `label/`. No workflow or browser makes new model calls. New dates or changed pools require an explicit generation run; A and B keep working while C waits. Garching and production behavior are unchanged.

## Model and labels

C uses the current Bulk/Cut/Budget preference models, not the provisional AI labeling seed. There is no retraining or automatic use of browser reviews. It is an experiment in moving LLM curation after mathematical ranking. A narrow top-twenty pool can still limit variety even when the LLM is allowed to choose freely within it.

## Design and verification

The inspector uses Plato's Switzer type and food artwork with the Achromatic ledger direction (seed 1772259688). It keeps the centered comparison workspace instead of adding navigation chrome for a single report. Cards show actual portions and computed totals; goal/date/diet and all-versus-selected controls are the primary interaction. Missing data and genuine zero selections remain explicit. Automated coverage checks pool/rank preservation, A and Bulk B invariance, immutable C selections, invented/duplicate ID rejection, short pools, stale/missing caches, API-free publication, and context navigation. Browser checks cover desktop/tablet/phone layouts, A/B/C switching, diet filters and the top-twenty inspection page.

The initial run covered all ten saved dates, November 23 through December 4, 2026: 177 nonempty goal/diet contexts were served by 126 distinct cached model calls, all successful. Three vegan contexts on November 27 have no feasible candidates. Available shortlists have their real counts; some vegan contexts have only three or four distinct feasible dish sets. Generated public audit JSON is ignored by Git and rebuilt during cached rescore.

The inspector’s long-list notice is intentional: All candidates is the full requested catalog, not twenty separate dashboard blocks. Cards within a row align their macro totals so different dish counts can be compared; the resulting whitespace is retained for that alignment. Selected-card borders are kept pale, with explicit C choice labels carrying the selection state.
