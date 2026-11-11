# Plate ranking UI (manual preference labeling)

**Goal:** A simple separate page where Yagiz ranks Mensa Plate candidate plates for a given day and goal, and can export his rankings. It is a throwaway labeling tool for now; the ML training will be built later from the exported data.

**Done when:**
- A separate page at its own subpath (e.g. `yagizdas.github.io/platum/label/`), apart from the main app, shows the candidate plates for a chosen day and goal.
- Yagiz can reorder them (drag to rank, works on phone) and save the ranking.
- Rankings persist in the browser between visits, and an Export button downloads all of them as JSON.
- Each record has: timestamp, menu date, goal, the ranking, and a snapshot of each plate (dishes, kcal, protein, price), so the export is usable without the old menus.

**Notes:**
- No training, no backend, no accounts. Keep it minimal.
- Allow picking past days too, not only today.
- Delete this TASK.md in your final commit.
