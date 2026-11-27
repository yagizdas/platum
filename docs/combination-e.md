# Staging E: MMR with simple overlap

Choose **E · MMR** on the staging Arcisstraße menu, or open `/staging/label/e/`. E uses the existing exhaustive candidate pool and preference models for Bulk, Cut and Budget, including all dietary profiles. A–D, the main branch, Garching, the frozen label dataset and local training artifacts remain unchanged. E makes no new model calls and does not load the trained usefulness classifier.

## Selection

Start with the top 100 eligible distinct dish sets and their best-ranked portions. Keep the highest preference-ranked plate first. At every subsequent slot, choose the unselected plate maximizing:

```text
lambda * quality - (1 - lambda) * max_similarity_to_earlier_picks
```

Retain up to five candidates, with no hard similarity rejection. Break ties by higher quality and then the original preference rank, which already incorporates the scorer's deterministic price/identity tie-breaks. Original items, portions, totals, raw scores and rank are preserved. All existing feasibility limits, dietary filters and the 900 g cap excluding soup remain in place. A short pool is not padded.

Three initial settings are available in both the menu and report: Quality first (lambda 0.80), Balanced (0.50, default), and More variety (0.35). These settings are explicit experiment choices, not learned optimal parameters. The menu and report show how many selected plates differ from the plain top five, counting replacements rather than order changes. On the ten saved dates across all-meal Bulk/Cut/Budget (30 contexts with more than five candidates), Balanced changes the actual selected set in 25 contexts and replaces 1.8 slots on average; More variety changes all 30 and replaces 3.37 slots on average. This measures composition changes, not whether users prefer the resulting lunches. Stronger diversity can select lower preference-ranked plates. A lambda of one reproduces the plain preference ordering; a lambda of zero chooses by diversity after the fixed first pick.

## Quality scale

```text
scale = max(1, best_preference_score - worst_preference_score_in_this_pool)
quality = 1 - (best_preference_score - candidate_preference_score) / scale
```

This linear transformation preserves score-gap ratios within the eligible pool and bounds quality between zero and one. The one-unit minimum avoids amplifying tiny raw-score differences to a full zero-to-one range. It also avoids saturating larger gaps so that many clearly inferior candidates become nearly indistinguishable. It is a relative score transformation, not a calibrated probability; changing the pool can change its scale. Each selected plate records the actual scale, quality contribution, repetition penalty and final MMR value. The report exposes those terms and the original preference scores.

## Similarity

E reuses D's exact dish identities, cached core/accompaniment classifications and presence weights `min(grams / 150, 1)`. Weighted Dice overlap is computed separately for core dishes and accompaniments. Core weight is 0.8 and accompaniment weight 0.2. Unlike D, a group absent on both plates has no agreement bonus: omit its weight and renormalize over groups present on either plate. A group present on only one plate has overlap zero and retains its weight. Identical nonempty plates have similarity one. Shared sides with entirely different cores have similarity 0.2, while two completely different core-only plates have similarity zero.

This remains an approximate composition measure. It does not infer taste, cuisine, preparation similarity or personal food preferences. Its result is used as a soft penalty, allowing a strong candidate to survive high overlap. There is no automatic claim that E's full set is better than D's.

## Review and publication

The report offers date, goal, diet and balance controls; shows selected plates in their actual MMR order; retains preference ranks; links to the corresponding D report; and links back to the exact menu context. The alternative browser exposes every candidate in the top-100 pool, including those absent from the five selected plates. Each alternative shows actual portions and nutrition, its score and whether it is already selected. Changing balance preserves a browsed alternative within the same context. The selection-math disclosure shows each pick's quality/repetition terms.

`rescore_cached.py` regenerates E during the ordinary cached publish step. Audit JSON is written under `label/e/data/` and ignored by Git; existing workflows copy it with the rest of `label/`. All three settings are precomputed, so switching balance makes no API call. No user labels or local training files are copied into the site.

## Verification and design

Tests cover missing-group correction, core swaps, extra scoops, small score differences, negative scores, finite inputs, exact MMR maximization, first-pick preservation, stable ties, pure-quality ordering, short/empty pools, all goal/diet variants, unchanged candidates, A–D preservation, API-free publication and report reconstruction. Browser checks cover A/B/C/D/E switching, all goals, balance changes, Vegan/No pork, four-dish art, empty pools, all-candidate browsing, context links, load errors, Garching and 1440/768/390/320 layouts.

The page extends the existing Switzer comparison workspace (Achromatic ledger, seed 1772259688), without a new art direction or new media. Its single inspector whitespace warning is retained for a consistent comparison area around macro totals across different dish counts. The source lint border warning concerns the ordinary alternative-select form control.

ROUND 1
Seen in one second: Five Plato lunch options with a control for quality versus variety.
Idea (one sentence): Make a soft diversity trade-off reviewable while retaining access to every candidate.
Live thing: Date/goal/diet/balance controls, candidate browsing and context-preserving D/menu links.
Layout words by section: header=experiment / controls=context and balance / picks=peer plates / alternatives=full pool browser / selection math=calculation disclosure / footer=method explanation.
Scores: design 6.5 · usability 8 · creativity 6 · content 8 → overall 7.0.
Caps applied: Existing category illustrations and established report layout, rather than new photographic art direction.
Top three problems (most visible first), each with the screenshot it shows in and the fix:
1. Different dish counts leave modest internal whitespace (`desktop-fold.jpg`); retain a consistent macro-comparison area.
2. Five full cards require phone scrolling (`mobile-page-01.jpg`); the main menu remains the compact carousel while this report retains complete evidence.
3. Category illustrations are approximate (`tablet-fold.jpg`); actual dish names, portions and totals remain visible as the source of truth.
