Mensa Plate's landing page turns its compartmented canteen tray into an oversized floating poster object. The selected direction is Loud and flat (seed 1845759322). The brief overrides its saturated hero field, navigation, mosaic, editable headline, and shutter motion: the requested page has an off-white ground, one vegetable-green accent, four goal cards, and one daily pick. No extra sections or copy are added.

The inventory is specific to the supplied project: the Mensa Plate name, Arcisstraße, the compartmented tray, pasta, strawberries, green vegetables, dumbbells, a bowl, euro coins, a leaf, and the generated daily prices and macros. The live interaction is selecting Bulk, Cut, Budget, or Vegan to update one real daily plate. Vegan maps to the existing bulk-vegan variant. The original full app remains at `menu.html`.

Visible copy is reused from the existing app and the request: “Mensa Plate”, “Your lunch, sorted.”, “Your plate”, “Goal selector”, the four goal words, and “Today's pick”. Plate titles, prices, and macro numbers come from generated data. Normal sections contain 7, 6, and at most 15 visible words respectively. No sample dishes, prices, nutrition, or claims are invented.

One locally served display family, Bricolage Grotesque, carries every size. The hero title is 13.2vw on desktop and 25vw on phones. The supplied PNGs have white backgrounds; CSS multiply blending makes them sit on the flat surfaces without modifying the original files. The floating hero gets one soft ground shadow and a fixed -7 degree rotation. Motion is limited to its seven-second vertical float and one-time scroll fade-ups; reduced motion exposes every section immediately and disables the float.

Validation: source lint passes, browser inspection passes at 1440, 768, and 390 pixels. Extra browser checks cover 320 pixels, all four goal selections, exact JSON totals, copy limits, keyboard interaction, the detailed-menu handoff, unavailable storage, closed/stale/failed menus, and reduced motion. The inspector's footage, motion-volume, name-only title, and off-white palette warnings are retained because the user's brief explicitly limits those choices. Screenshots and the detailed reports live in `.taste-skill/landing-final/` and `.taste-skill/landing-qa/`.

The original detailed menu app follows the design below.

Mensa Plate answers one question: what should I put on my plate for this goal at Arcisstraße today?

The app uses the Achromatic ledger direction (seed 1475843428), with a pale stone ground from a canteen tray, Geist typography, and a receipt-like list of real dishes. Scoop counts are its distinctive visual element; one blue hue marks those counts. A single centered column suits one daily decision. No chart, sidebar, decorative food imagery, or extra destination is needed.

The content width is 760px: 808px shell minus two 24px gutters. The receipt's item grid is 72px + flexible name column + 62px price, with two 12px gaps; at phone widths it becomes 50px + flexible name column + 52px price with two 8px gaps. The controls and receipt share the same left and right edges.

All displayed dish names and estimates come from the generated JSON. There are no hardcoded example plates in production. Missing estimates, closed days, stale dates, and fetch failures keep a real message in the plate frame. The native buttons and switch retain keyboard controls, focus outlines, pressed/checked state, and a polite result announcement. Rendering uses textContent for external dish names.

The plate title is the card headline, with one muted explanation underneath. Up to three distinct lunches share this same frame: a quiet “Other options” counter and native previous/next buttons cycle them, with arrow-key and horizontal-touch support. A small aria-live region announces the selected title without reading the whole receipt again. Goal/diet changes reset the alternative and tray extras.

Soup and dessert live below the plate as optional “Add to tray” chips. Their selected state is neutral grey; only scoop counts use blue. Totals sum the selected code-computed extras, with a muted “incl. extras” label. Diet labels stay plain muted text. Standing sides say “Beilagen counter · usually there.” A “Share plate” text button uses native sharing or clipboard feedback. Install icons reuse the existing plate drawing on the stone ground; no service worker or offline menu is introduced.

Week view adds one quiet Monday–Friday strip above the goal controls. The selected day uses an ink underline, with no new hue. The date beside the main heading names the selected menu, including future dates. Before 14:30 Berlin time the default is today's open menu; afterwards, on holidays, and on weekends it is the next open date. The following week is prefetched so a Friday or weekend can select Monday. A day change clears extras and alternatives; each response must match its selected date, and older in-flight requests cannot replace a newer selection.
