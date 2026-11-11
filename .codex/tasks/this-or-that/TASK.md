# This-or-that plate labeler

**Goal:** Replace the drag-to-rank plate labeling page (added in PR #2) with a pairwise "this or that" picker. Two plates side by side, pick the better one. Data feeds a later Bradley-Terry fit; no training in this task.

**Done when:**
- Page shows two plates side by side (dishes, price, kcal, protein). Pick with left/right arrow keys or by tapping a plate (must work well on phone). Down arrow / "both bad" button = skip, `u` / undo button = undo last judgment.
- Pair sampling: ~70% of pairs from the top 15 plates of the day under the current hand score, ~30% random plates, drawn across available menu days.
- Every judgment is stored (date, plate A id + features, plate B id + features, winner or "both_bad") and persists across reloads; JSON export button downloads all judgments.
- A visible counter shows judgments done vs a target of 150.

**Notes:** Throwaway labeling UI, keep it small and separate from the main app. Remove the old drag-to-rank UI (or replace it in place). No ML/training code. Delete this TASK.md in your final commit.
