# Bulk v2 preference labeling

Open `/staging/label/v2/`. The original labeler links to it and keeps its own progress. The frozen dataset contains 600 comparisons from 25 saved Arcisstraße menu dates, 2026-11-02 through 2026-12-04. It was generated locally with no model calls and does not change A, B, or production scoring.

Choose the lunch you would actually eat, or **Both bad** if neither is acceptable. **Skip for now** postpones a comparison without assigning a label; **Undo** restores the exact last comparison. Arrow left/right choose A/B, arrow down rejects both, U undoes. Progress resumes on the same browser and origin. **Export** downloads a complete training-ready snapshot. **Restore** merges choices from this exact dataset, retaining the latest timestamp for duplicate comparisons. There is no account, upload, or automatic device sync. Old v1 judgments are not mixed in. Compact browser storage keeps the full 600-comparison session below ordinary local-storage limits; exports reconstruct the full plates from the frozen dataset.

## Dataset

`label/v2/build_data.py` uses the exhaustive B candidate generator, one to four distinct dishes and all permitted portions, with the existing Bulk feasibility limits. It enumerated 85,567 eligible portioned plates, then sampled across dish count, energy, fat-energy percentage, weight, and meat-dish count. Each day has four comparisons in each of six groups: different dish counts, portions of the same dish set, fat-share contrasts, meat-quantity contrasts, current-score references, and broad exploration. Fat and meat contrasts match energy/protein approximately when possible. The current score supplies only the reference group, not a cutoff for the exploration pool. Pair orientation and menu-date order are deterministically shuffled. No menu days were skipped.

Cards show the actual portions, serving counts, weight, price, calories, protein, fat, carbs, calories from fat, and weight of meat-containing dishes. Meat-dish weight includes sauces and accompaniments; it is not pure meat quantity. Unknown dietary labels are recorded separately, rather than treating an unlabeled item as confirmed meat. Nutrition remains estimated. Fat energy share is `9 * fat_g / kcal * 100`, without normalizing away inconsistencies in estimates. Dish identity plus portions forms the plate ID, so different servings of the same foods can be compared. Dataset ID fingerprints the complete frozen candidate snapshots and queue.

Reproduce with the source menu/tag snapshot available in a checkout:

```sh
python label/v2/build_data.py --source-root /path/to/source-checkout --output label/v2/data.json
```

Do not routinely regenerate this frozen dataset during publishing. The existing publishing workflows already copy the entire `label` directory to staging. A deliberate new dataset receives a different ID and browser-storage key.

## Export semantics and future training

Exports have schema version 2, experiment `bulk-exhaustive-v2`, the dataset ID, and complete records. Every record includes menu date, comparison strategy, timestamp, both full plate snapshots and features, preference, and separate acceptability values:

| Choice | Preference | A acceptable | B acceptable |
|---|---|---|---|
| A | A | true | unknown (`null`) |
| B | B | unknown (`null`) | true |
| Both bad | none (`null`) | false | false |

Selecting a plate does not label the losing plate unacceptable. Both-bad is not a tie or an arbitrary ranking; it supplies two explicit rejection examples for a future acceptability model. Pairwise preferences and acceptability must be fitted as separate signals. The old three-feature trainer is not a v2 trainer. No new model can be trained until fresh labels are collected; the current models stay active.

Available features include kcal, protein, price, fat/carbs grams, total weight, dish count, fat/protein energy percentages, meat-dish weight and meat-dish count. Keeping raw measurements supports later nonlinear transformations without prescribing a preferred lunch size. Evaluate new models on held-out menu dates, not random portion splits, and compare against current B.

## Design and verification

Achromatic ledger, seed 2067332202, with Plato's Switzer type, neutral ground and food artwork. One question: which of these two actual lunches would you eat? The signature elements are the paired trays and explicit scoop/weight rows. A centered comparison workspace replaces a sidebar because there are only two labeling destinations. On phones the plates stack, with persistent A/B/neither controls. No invented/sample meals or users are used.

## Review the assistant's 150 decisions

Open `/staging/label/v2/review/`, linked from the v2 labeler. It shows the two original plates, portions and macros, the original AI decision and its reason. **Agree & next** confirms the suggestion and opens the next unreviewed case. **Choose A**, **Choose B** and **Both bad** save an explicit human decision while keeping the case open for inspection. You can switch the choice repeatedly, add a note, mark it unreviewed, or jump to any case. Filters show pending, changed, agreed, or all cases; the case browser indicates which have been reviewed. Arrow left/right/down choose A/B/neither; Enter outside controls confirms the AI choice.

The committed `label/v2/review/data.json` contains the 150 assistant judgments from the frozen queue, with their AI provenance and data-quality flags: 54 A, 53 B, 43 both bad. It contains no user reviews. Browser review storage has its own key, independent of v1 and v2 direct labeling. Ordinary publishing copies this snapshot unchanged.

**Export reviews** contains only explicit human reviews, with full original plate snapshots, the original AI choice and reason, the human choice, acceptability values, timestamps and notes. **Download full audit** also includes untouched AI judgments, which stay marked `is_human_judgment: false`. Confirmed and corrected cases are marked `human_review_of_ai`, not blind human judgments. **Restore** merges review files by latest timestamp and does not count unreviewed AI rows as reviewed. The direct v2 labeler rejects AI/review imports so it cannot erase provenance. No ranking model is trained or changed by reviewing.

Design continues Achromatic ledger (review seed 1883000294), with the existing centered comparison workspace rather than an extra icon rail: only two labeling destinations need navigation. The paired trays remain the primary evidence; original reasoning and pending/reviewed state are explicit. Shared plate rendering keeps the direct labeler and review screen aligned. Desktop, tablet and phone layouts are checked, alongside save/resume, all decision transitions, notes, filtering, backup/restore, provenance, completion and storage failures.
