The 28 original PNGs are retained in `new_icons/`. Their matching web assets are in `ui/`; the old illustrations and install icons have been replaced.

The browser receives WebP copies at 640px, with the hero tray at 1254px. They preserve the white background. `artwork.json` records the original sources and content bounds; `artwork.css` clips the white margins at display time and blends the white into the page surface. The complete dish scene also uses multiply blending, so opacity on an error state or menu transition cannot expose a white rectangle. Install PNGs derive from the new tray.

`dish-icons.js` selects food categories from German and English dish identities. It ignores a sauce or side introduced by “mit” or “with”, so schnitzel with mushroom sauce remains schnitzel, and chicken soup is soup. No menu, diet, or nutrition data is changed. Pizza and pinsa, kebabs and skewers, steaks and roasts, and sweet and savory pastries use their supplied illustrations; unknown future dishes receive a category or generic fallback. Poultry steaks retain the chicken illustration, and minced steaks use meatballs.

| Artwork | Use |
| --- | --- |
| Dumbbell, measuring tape, coins, leaf | Bulk, Cut, Budget, independent Vegan filter |
| Fish, chicken, schnitzel, sausage, meatballs | Main-dish protein or preparation category |
| Pasta, rice, dumplings | Pasta, grains, dumplings and rice balls |
| Broccoli, vegetables, salad | Vegetable dishes, curries, salads and sides |
| Soup, stew | Soups, stews, goulash and ragouts |
| Fries | Fries, wedges and rösti |
| Pizza | Pizza, pinsa and flammkuchen |
| Kebabs | Kebabs, shashlik and meat or vegetable skewers |
| Steak | Steaks, roasts and chops |
| Sweet pastry, savory pastry | Sweet strudels, croissants and doughnuts; savory strudels, yufka and filled pastries |
| Cake, dessert | Cakes, pancakes, creams and puddings |
| Tray | Landing hero, install icons, generic dish fallback |
| Pink/red sad faces | Empty or failed menu states |

Each ingredient row and selected extra has an icon. Details is a permanent section. `DishIcons.compose` keeps the main dish larger, with the first smaller companion on the right and a third item on the left. Their edges lightly touch, like dishes arranged together on a table. A selected extra can fill a companion slot; illustrations stop at three items. It clears companions in empty/error states and restores the centered layout for a single dish. Today's pick on the landing page uses the same composition and mapping.

Only `ui/` and `artwork.css` are included in the public website package. The source PNGs stay in the repository for future asset preparation.
