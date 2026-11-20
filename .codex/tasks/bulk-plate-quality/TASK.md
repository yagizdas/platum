# Bulk plate quality bug (Fri 20.11.2026, Mensa Arcisstraße)

**Goal:** Find out why Bulk mode recommends bad plates and fix it.
On 20.11 Bulk showed: #1 Kaiserschmarrn mit Zwetschgenröster + potato salad (€6.75, ~1200 kcal, ~28 g protein), #3 lentil stew alone (€1.49, ~428 kcal).
The official menu that day had Pasta Bolognese, Lasagne Bolognese (hausgemacht), Schweinesteak vom Grill mit Champignonsauce, pizzas. None of them showed up.

**Done when:**
- Root cause explained in your reply: are Pasta/Grill/Pizza dishes missing from the candidate pool (scraping, eat-api, missing/per-100g prices, filters, 9 € cap) or present but out-scored? Show where in the code.
- For 20.11 data, Bulk picks a real main (e.g. lasagne/bolognese/steak) over a sweet dish.
- Süßspeisen/desserts can never be the main of a plate (at most an add-on).
- A plate must be a full meal: a lone cheap side/soup (~400 kcal) is not shown as a Bulk plate; protein gets real weight in Bulk.

**Notes:** Check the Kaiserschmarrn kcal estimate, it looks inflated. Keep the learned bulk model; fix data/filters/constraints around it. Delete this TASK.md in your final commit.
