# Useful-alternative labeling pilot

Open `/staging/label/diversity/`. Links are also available from the Bulk v2 labeler and D review page. This is a separate human labeling task: **would offering both plates add a meaningful choice for the displayed goal?** It does not ask which plate wins. No current recommendation method, preference model or production page is changed.

## Decisions and review

Choose **Worth offering both** or **Mostly redundant**. Optional reason codes cover main dishes, taste/preparation, price, portions/nutrition and other reasons; an optional note accepts up to 500 characters. **Unsure / skip** defers the pair without a label. Deferred pairs return after fresh pairs. Select a session goal to work only on Bulk, Cut or Budget; All goals mixes them. The displayed scope always identifies the current pair's actual goal.

Each card also has an independent **does not suit this goal** flag. Marking either card disables binary pair judgments and enables **Save suitability & next**. That record has a null usefulness target, preserving rejection information without teaching that bad meals are redundant. An unchecked flag is not an explicit approval. Both cards can be flagged.

**Undo** removes the most recently saved label and reopens that pair. **Revisit a saved label** opens earlier choices, including their flags, reasons and note. Answering again replaces that pair's record; Back to queue retains the saved decision. Undo removes the latest record rather than reconstructing an earlier version of an edited answer. Arrow left/right save worth-both/redundant; arrow down skips; U undoes. Shortcuts do not trigger in editable controls.

## Dataset and future model

The frozen pilot contains 100 distinct comparisons from 25 real saved Arcisstraße menu dates: 34 Bulk, 33 Cut and 33 Budget. All eligible candidates use the exhaustive generator, 1–4 distinct dishes and permitted portions, the existing goal limits and the 900 g maximum excluding soup. A deterministic sample includes core swaps (18), side changes (18), component additions/removals (18), portion changes (16), comparisons within the current top 20 (15), and broad exploration (15). Strategy and rank information are hidden from the labeling screen. No answers are supplied or inferred from D or AI judgments.

Full plate snapshots include exact dish identities, portions, grams, prices, diet labels and estimated macros. Snapshot IDs fingerprint the full serialized facts, preventing differing date-specific prices from silently sharing an ID. The dataset fingerprint binds the snapshots, pairs, seed and feature version. Do not regenerate this frozen dataset during daily publication: a deliberately new dataset receives a new fingerprint and storage key.

`diversity_features.py` creates 27 symmetric numeric measurements: goal indicators; exact core/accompaniment dish and gram overlap; absent-group flags; component counts; changed-component mass fractions; minimum/maximum dish counts and total weights; and absolute price, calorie, protein, fat, carb and fat-energy-share differences. Both-absent groups have overlap zero and their own presence flag, with no fixed 80/20 combination or 150 g cap. Swapping A and B leaves every feature unchanged. Cached roles identify components; standing foods remain accompaniments. Names and full snapshots are retained for later semantic feature experiments, but no embeddings or flavor information are fabricated.

Binary records supply the future gradient-boosted classifier's target: `worth_offering_both` is true or false. Suitability-only records have null targets and must be excluded from that classifier's supervised fit. Optional reasons and notes are annotations, not prediction inputs. Data creation and labeling perform no model calls, no training, and no changes to the live ranking. Evaluate later on held-out menu dates and separately inspect unseen recipes; repeated recipes across dates need attention when testing generalization.

Reproduce with an unchanged source/config snapshot:

```sh
python label/diversity/build_data.py --source-root /path/to/source --output /tmp/diversity-data.json
```

## Storage and export

Progress stays in local storage under `plato-diversity-v1:<dataset_id>`, separate from v1/v2 preference and AI-review labels. There is no account, server upload or automatic cross-device sync. Export a backup before clearing browser storage or switching devices. Saved labels are synchronized between tabs through the browser storage event; use one active labeling tab when making edits.

Exports include schema/feature versions, dataset ID, timestamps, goal, date, sampling strategy, direct-human provenance, decision, usefulness target, suitability flags, reasons, note, trusted pair features and both full plate snapshots. Browser storage keeps compact snapshot references; export reconstructs the complete frozen records. All 100 compact records fit well below ordinary storage limits.

Restore accepts only this dataset's direct-human labels, validates pair/snapshot identities and reconstructs facts from the frozen dataset rather than trusting imported features. It merges by pair ID and latest timestamp. Preference-label and AI-review files are rejected. Failed writes leave the current pair unchanged; unreadable saved data pauses labeling and permits backup restore. A load failure reports an error inside the comparison area.

## Verification and design

Automated checks cover balanced, valid real pairs; sampling strategies; symmetry; absent groups; deterministic generation without model calls; target/suitability separation; save/skip/undo; filtering; completion; review edits; compact storage; provenance; trusted restoration; and nested asset URLs. Browser checks cover actual save/resume, notes, both decisions, flags, review edits, goal selection, export/file restore, invalid imports, quota failures, corrupted-store recovery, completion and 1440/768/390/320 layouts.

This extends the existing Switzer paired-plate workspace (Achromatic ledger, seed 2067332202). No new art direction or media is introduced. Card illustrations are existing category artwork; full dish names and portions provide the actual evidence. The source lint's two border warnings are ordinary select/textarea form controls, allowed on app screens. The rendered inspector reports zero failures and zero warnings.

ROUND 1
Seen in one second: Two real Plato plates and a question about whether both are useful alternatives.
Idea (one sentence): Collect human judgments of useful choice independently of individual plate preference.
Live thing: Two decision buttons, separate suitability flags, saved-answer review and resumable labeling.
Layout words by section: header=question / session=goal and progress tools / pair=two plates / annotations=optional reasons / actions=sticky answers / footer=scope and storage explanation.
Scores: design 6.5 · usability 8 · creativity 6 · content 8 → overall 7.0.
Caps applied: Existing drawn food artwork; this is an established working review screen rather than a new marketing design.
Top three problems (most visible first), each with the screenshot it shows in and the fix:
1. Phone comparison requires scrolling between full plates (`mobile-page-01.jpg`); retain full portions and nutrition, with sticky decisions and explicit plate headings.
2. Some food illustrations are approximate (`desktop-fold.jpg`); preserve established artwork and show actual dish names and grams.
3. Progress and review controls consume phone height (`mobile-fold.jpg`); keep optional reasons collapsed and controls compact without removing backup or correction access.
