# Garching integration — 23 November 2026

The location selector covers **Mensa Garching, Boltzmannstraße 19**, not the separate StuBistro in the same building. The existing Arcisstraße route and data remain compatible.

## Verified sources

The [official Garching menu](https://www.studierendenwerk-muenchen-oberbayern.de/gastronomie/speiseplan/speiseplan_422_-de.html) is authoritative for dates, dish names, stations, dietary markers, allergens and additives. Its ten published weekdays (23 November–4 December) were inspected directly. The saved schedule is `tests/fixtures/garching-2026-11-23.html`.

The actual markup uses the same dated `c-schedule__item` blocks and `c-menu-dish` fields as Arcisstraße. This permits the existing parser to be reused; it does not establish identical service arrangements. In the inspected Garching schedule, soup is explicitly grouped under **Tagessupe, Brot, Obst**. Arcisstraße also has unlabeled entries and different dessert/soup grouping. A soup named in Garching's combined category is treated as soup without treating future bread or fruit entries as soup.

The [operator's venue page](https://www.studierendenwerk-muenchen-oberbayern.de/gastronomie/standorte-und-oeffnungszeiten/garching) supplies the location and normal 14:15 closing time, used as Garching's lunch cutoff. Vacation hours are earlier; no academic-calendar inference is implemented.

The [operator's pricing page](https://www.studierendenwerk-muenchen-oberbayern.de/gastronomie/preise-und-bezahlung/) describes weight billing and fixed components. Actual student prices are taken only from unambiguous normalized-name matches in the [Garching eat-api feed](https://tum-dev.github.io/eat-api/mensa-garching/2026/48.json). That feed is secondary: it cannot introduce a dish absent from the official menu or override its dietary status. Its documented canteen identity is in the [eat-api repository](https://github.com/TUM-Dev/eat-api).

For example, the inspected Garching bratwurst has a €0.50 base component. Copying the Arcisstraße meat default would be wrong. Soup rates also differ from a generic assumption, so matched feed prices are retained. If a published dish has no unique price match, it is omitted from recommendations with a visible warning. If all prices are missing, that date is unavailable, never falsely closed. One Tuesday dish in the initial batch lacks an unambiguous price match.

## Explicit boundaries

- No permanent rice or potato-salad sides are added to Garching: their presence was not established by the source.
- Garching displays the published station categories and does not enforce a shared-counter restriction. Arcisstraße has no counter assignments or pickup labels.
- Portions and nutrition remain estimates. Exact normalized dish names share cached nutrition/translation estimates; official diet, price, station and campus data remain local to each menu.
- Garching's source menus, proposals, response audits, titles, public dates and completion records live under `data/campuses/garching/`. The shared nutrition cache remains `data/dish_cache.json`.
- Saturdays prepare each campus independently. Sunday skips complete campus batches and retries incomplete ones. A source failure at one campus cannot substitute the other campus's dishes.
- Ordinary publication has no model secret and only rescores each saved batch's exact dates. Packaging copies public `week.json`, `today.json` and `days/`; raw campus menus, proposal audits and batch records are excluded.
- Reports and device-local hidden plates are campus-scoped. Legacy reports default to Arcisstraße. The three-report device limit remains shared across campuses.

The initial Garching batch for 23–27 November uses the official menu, shared exact-name cache entries plus 13 new dish estimates, 30 campus-specific proposal responses, and deterministic portion/ranking code. Original provider responses are preserved in audits, including revalidation against the Garching station policy without extra proposal calls. Some goal/diet variants have no qualifying plate; existing nutrition requirements are retained.

## Operations

```sh
python weekly_batch.py                         # both campuses, coming Monday-Friday
python weekly_batch.py --campus garching --date 2026-11-23
python scrape.py --campus garching --week --date 2026-11-23
python rescore_cached.py                       # both saved batches, no LLM
```

Choose Garching in the header, or use `menu.html?campus=garching`. The campus is remembered independently of goal/diet preferences. Campus switches clear extras and active plate state, protect against stale responses, update the official-menu link, and never fall back to the other location. Shared links retain campus, goal, date and Vegan state under the current deployment path.
