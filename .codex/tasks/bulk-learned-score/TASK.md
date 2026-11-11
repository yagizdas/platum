# Learned bulk score

**Goal:** Replace the hand-written bulk plate score with a model learned from Yagiz's pairwise judgments, and use it in the live flow to pick/rank bulk plates.

**Done when:**
- A small reproducible training script fits a Bradley-Terry / pairwise logistic model (no intercept, on feature differences A−B) from `judgments-bulk-2026-11-11.json` (move the file to a sensible data folder) and writes the learned weights to a file the app reads.
- Bulk ranking in the daily flow uses those weights instead of the old formula; cut/budget/vegan are unchanged.
- The script prints leave-one-date-out accuracy; it should beat the old score (75% agreement on decisive pairs).
- Bulk plates on staging visibly favour ~900-1100 kcal, higher-protein plates over cheap ~600 kcal ones.

**Notes:**
- Ignore `both_bad` rows for training. Data is small (148 decisive pairs, 93 plates): keep features minimal.
- A quick offline fit found kcal, protein, price as features gives ~95% LODO accuracy, ≈1.8 per 100 kcal and ≈1.8 per 10 g protein, price ≈0 (ratio features like kcal/€ only ~70%). Use as a sanity check, not a hard requirement.
- Keep it general enough to retrain later with more judgments (other goals, other users).
- Delete this TASK.md in your final commit (keep the data file).
