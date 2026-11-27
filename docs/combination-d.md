# Staging D: deterministic diversity

D is available on Arcisstraße for Bulk, Cut and Budget, including Vegan and all other dietary profiles. Choose **D · Distinct** on the staging menu or open `/staging/label/d/`. A, B, C, Garching and the main branch keep their existing behavior.

The existing exhaustive search still enumerates one-to-four-dish combinations and allowed portions, applies goal eligibility, dietary exclusions and the 900 g limit excluding soup, and uses the existing preference model. Each distinct dish set retains its best-ranked portioning. D walks the first 100 eligible ranked dish sets in order, always retaining rank 1. It skips a candidate when its similarity to **any** earlier selected plate is at least 0.65, stops at five picks, and returns fewer if the pool does not supply five distinct options. It never relaxes the threshold or changes candidate dishes, portions, nutrition, price or score. The 100-candidate limit is a search boundary, not a new calibrated quality floor.

## Similarity

Existing cached `main` roles identify core dishes; standing foods always count as accompaniments. Complete pasta dishes, stews and vegetarian entrees can be cores. Sides, soup and dessert are accompaniments. D adds no new classification or curation model calls. The inspection page shows the classification of every selected component so incorrect existing roles can be identified.

Within each group, each exact dish identity has presence `min(grams / 150, 1)`. A normal 150 g scoop reaches full presence; extra scoops do not manufacture novelty. Small additions contribute proportionally. Weighted Dice overlap is `2 * sum(min(left_presence, right_presence)) / (sum(left_presence) + sum(right_presence))`. Both groups empty means overlap 1; only one group empty means 0. Final similarity is `0.8 * core_overlap + 0.2 * accompaniment_overlap`. Compare the full precision value to 0.65; UI percentages are rounded only for display.

Chicken + rice + plain pasta versus köfte + rice + plain pasta scores 0.20 and both survive. When the shared pasta is itself a complete main course, the score is 0.60 and both still survive. The same chicken core with different sides scores 0.80 and only its higher-ranked combination survives. This is an initial experiment with exact dish identities, not a semantic claim about related recipes.

## Publication and review

`rescore_cached.py` generates D automatically from the saved menu data with no API calls, alongside A/B/C. It builds the top 100 once and passes only the unchanged top-20 prefix to C and first-five prefix to B. D day JSON and its manifest are written to `label/d/data/` and included by the existing staging publishing workflow. Generated report data is ignored by Git. There is no new labeling, training, LLM selection cache or paid generation step.

The review page offers date, goal and diet selection, full plates with food artwork and exact totals, original preference ranks, core/accompaniment assignments and a ranking-walk table. The table records every accepted or skipped candidate actually examined, its closest earlier selection and the core/accompaniment/combined overlap. It stops with the algorithm, rather than claiming that unexamined lower candidates were rejected. Links preserve the exact context when returning to the menu. Empty, smaller and failed-to-load contexts are explicit.

## Verification and design

Tests cover meaningful core swaps with shared sides, side-only swaps, extra scoops, tiny additions, empty groups, threshold equality, comparison against every earlier selection, scanning beyond rank 20, the rank-100 cap, deterministic ordering, unchanged candidate totals and dietary eligibility, A/B/C preservation, API-free publication and review navigation. Browser checks cover method switching, all goals, Vegan/No pork, four-dish art, empty/small pools, load errors, Garching and 1440/768/390/320 layouts.

The page extends the existing Switzer comparison workspace (Achromatic ledger, seed 1772259688) with a compact ranking-walk disclosure. No redraw, new media, placeholder meals or motion sequence is introduced. The inspector's card whitespace warning is retained because the macro totals need a consistent comparison area across different dish counts; it is not an empty content section.

ROUND 1
Seen in one second: Plato's ranked lunch alternatives, with five actual picks and date/goal/diet controls.
Idea (one sentence): Make the deterministic diversity filter's choices and rejections reviewable beside real plates.
Live thing: Date/goal/diet selection and the accepted/skipped ranking walk, with a context-preserving menu link.
Layout words by section: header=product and scope / controls=context / selections=peer plates / ranking walk=table disclosure / method=explanation disclosure.
Scores: design 6.5 · usability 8 · creativity 6 · content 8 → overall 7.0.
Caps applied: Existing drawn dish artwork, no new photographic art direction; intentionally a working review screen.
Top three problems (most visible first), each with the screenshot it shows in and the fix:
1. Desktop cards retain modest whitespace above totals (`desktop-fold.jpg`); retain this space for portion and macro comparison across cards.
2. Five long plates require substantial phone scrolling (`mobile-page-01.jpg`); the main menu remains the compact carousel, while this report deliberately shows the full comparison.
3. Food illustrations are category-level approximations (`tablet-fold.jpg`); actual dish names and grams remain the source of truth and the existing artwork is preserved.
