# Bulk calibration — November 9, 2026

The selected weights promote substantial protein servings while retaining price sensitivity. This is a practical starting point based on the available candidates and the user's stated preference, not a universal optimum.

The reference preference was **950 kcal, 60g protein, €6.50** over either **1,200 kcal, 35g protein, €5.50** or **750 kcal, 45g protein, €4.00**. The last option has more protein per euro (11.25g/€ versus 9.23g/€), so simply increasing the protein-per-euro weight can favor the wrong plate.

## Method

Reused cached proposals for November 2–6 and November 9–13, with current serving rules and corrected fixed-serving weights. Enumerated portions and evaluated the first-ranked plate in each daily Bulk variant, preserving the production sort order and distinct-main selection. No new proposals were generated during calibration. All nutrition values remain estimates.

Tested 1,344 combinations of the existing terms:

- Energy-value weights: 0.25, 0.5, 1, 2.
- Protein-value weights: 2, 3, 4, 5, 6, 8, 10.
- Above-500-kcal slopes: 0.125, 0.25, 0.5, 0.75, 1, 1.5, 2, 3.
- Price weights (deductions, divided by four): 0.25, 0.5, 1, 1.5, 2, 3.

None of those tested settings satisfied both reference preferences. This does not prove that no possible weights could do so.

Then tested 324 combinations with a linear total-protein reward:

- Energy-value weights: 0.25, 0.5, 1.
- Protein-value weights: 0, 0.5, 1.
- Above-500-kcal slopes: 0.25, 0.5, 0.75.
- Price weights (deductions, divided by four): 1, 1.5, 2.
- Total-protein weights (divided by ten): 0.5, 1, 1.5, 2.

279 settings satisfied both reference preferences. The selected setting balances protein, lunch size and price; it was not selected merely by maximizing protein. The below-500-kcal slope of three and the additional one-point deduction per euro above €7 stayed fixed throughout both sweeps.

## Selected equation

With `e` = euros, `k` = kcal, `p` = protein grams, and `h(x;u,d)` = `u*x` for nonnegative `x`, otherwise `d*x`:

```text
Bulk = 0.25*(k/e)/250 + 0.5*(p/e)/12 + 1.5*p/10
       + h(k-500;0.25,3)/300 - 2*e/4 - max(0,e-7)
```

This rewards total protein at 0.15 points per gram, reduces cheap-calorie incentives, and deducts 0.5 points per euro plus an extra point per euro above €7. There is no protein target or hard price, calorie or plate-weight cutoff. Fixed-serving and individual scoop limits still apply. Cut and Budget weights were not changed by this calibration.

## Results

These are means across the five first-ranked `bulk_all` plates in each week, not averages over every displayed alternative.

| Sample | Setting | Calories | Protein | Price |
|---|---|---:|---:|---:|
| Nov 9–13 | Before | 1,108 kcal | 38.3g | €5.24 |
| Nov 9–13 | Selected | 927 kcal | 49.1g | €5.90 |
| Nov 2–6 | Before | 1,056 kcal | 32.4g | €5.61 |
| Nov 2–6 | Selected | 865 kcal | 46.3g | €5.88 |

For November 9–13, days with a first-ranked plate reaching 50g protein increase from one to three. Only three days have a cached bulk candidate reaching 50g, so these weights cannot achieve that threshold on Monday or Friday.

| Date | First-ranked plate, including accompaniments | Calories | Protein | Price |
|---|---|---:|---:|---:|
| Nov 9 | Cevapcici, pumpkin soup and rice | 986 kcal | 39.8g | €6.58 |
| Nov 10 | Chicken, quark dessert and rice | 854 kcal | 57.1g | €6.49 |
| Nov 11 | Duck, jam doughnut and rice | 1,114 kcal | 65.1g | €5.82 |
| Nov 12 | Beef Stroganoff and rice | 802 kcal | 55.8g | €6.40 |
| Nov 13 | Farmer's stew and apple strudel | 878 kcal | 27.8g | €4.19 |

For `bulk_vegan`, current-week first-ranked averages change from 1,130 kcal / 41.9g / €5.54 to 1,167 kcal / 42.7g / €5.81. Vegan candidate availability and outcomes differ; the non-vegan improvements should not be generalized to that pool.

## Sensitivity and limits

Independently varied each of the five selected weights by −10%, 0%, or +10% (243 settings). All 243 retained the reference preference and three first-ranked days reaching 50g protein. Mean protein ranged from 46.1g to 49.9g. Mean calories ranged from 770 to 1,014 kcal and mean price from €4.89 to €6.17: portions remain sensitive near score ties, even when main selection is stable. Some nearby settings choose several plates below 800 kcal.

The selected setting puts this week's first-ranked plates between 802 and 1,114 kcal, all below €7, but those are observed results rather than enforced limits. Last week's sample still includes a first-ranked plate below 800 kcal. Two weeks of estimated nutrition and cached proposal coverage cannot establish a general optimum; future preference examples and menus should guide further tuning.
