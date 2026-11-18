# Counter layout for Mensa Arcisstraße

**Goal:** Tag every dish with the counter(s) it is likely served at, show the counter on each plate, and only propose plates whose dishes share at least one counter.

Counters, left to right: Warm 1&2, Pasta, Warm 3/4, Grill.

Heuristic from the in-Mensa screens (Nov 18, 2026), by online menu category:
- Fleisch, Beilagen -> Warm 1&2
- Pasta, Vegetarisch -> Pasta (often also Warm 1&2)
- Vegan -> Warm 3/4 (often also Warm 1&2)
- Grill dishes -> Grill
Example day: Warm 1&2 had Lammgulasch, Bohnen, Süßkartoffeln, Kartoffelsalat, Käsespätzle, Quinoa-Grünkern-Strudel, Räuchertofu. Pasta had Käsespätzle, Kartoffelauflauf, Quinoa-Grünkern-Strudel. Warm 3/4 had Räuchertofu.

**Done when:**
- Each dish has a set of counters, defined in one easy-to-edit mapping.
- Each plate card says which counter to go to.
- No proposed plate mixes dishes with no shared counter.

**Notes:** The chef assigns dishes daily, so this is a heuristic, not ground truth. Delete this TASK.md in your final commit.
