The 23 original PNGs are retained in `new_icons/`. Their matching web assets are in `ui/`; the old illustrations and install icons have been replaced.

The browser receives WebP copies at 640px, with the hero tray at 1254px. They preserve the white background. `artwork.json` records the original sources and content bounds; `artwork.css` clips the white margins at display time and blends the white into the page surface. Install PNGs derive from the new tray.

`dish-icons.js` selects food categories from German and English dish identities. It ignores a sauce or side introduced by “mit” or “with”, so schnitzel with mushroom sauce remains schnitzel, and chicken soup is soup. No menu, diet, or nutrition data is changed. Categories without an exact supplied illustration, such as pizza, savory pastries, or roast beef, use the neutral tray; unknown future dishes receive a category or generic fallback.

| Artwork | Use |
| --- | --- |
| Dumbbell, measuring tape, coins, leaf | Bulk, Cut, Budget, independent Vegan filter |
| Fish, chicken, schnitzel, sausage, meatballs | Main-dish protein or preparation category |
| Pasta, rice, dumplings | Pasta, grains, dumplings and rice balls |
| Broccoli, vegetables, salad | Vegetable dishes, curries, salads and sides |
| Soup, stew | Soups, stews, goulash and ragouts |
| Fries | Fries, wedges and rösti |
| Cake, dessert | Pastries, cakes, strudels, creams and puddings |
| Tray | Landing hero, install icons, generic dish fallback |
| Pink/red sad faces | Empty or failed menu states |

Each ingredient row and selected extra has an icon. Details is a permanent section, and the large summary illustration follows the selected main dish. The same mapping is used for today's pick on the landing page.

Only `ui/` and `artwork.css` are included in the public website package. The source PNGs stay in the repository for future asset preparation.
