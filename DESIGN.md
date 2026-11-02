Mensa Plate answers one question: what should I put on my plate for this goal at Arcisstraße today?

The app uses the Achromatic ledger direction (seed 1475843428), with a pale stone ground from a canteen tray, Geist typography, and a receipt-like list of real dishes. Scoop counts are its distinctive visual element; one blue hue marks those counts. A single centered column suits one daily decision. No chart, sidebar, decorative food imagery, or extra destination is needed.

The content width is 760px: 808px shell minus two 24px gutters. The receipt's item grid is 72px + flexible name column + 62px price, with two 12px gaps; at phone widths it becomes 50px + flexible name column + 52px price with two 8px gaps. The controls and receipt share the same left and right edges.

All displayed dish names and estimates come from the generated JSON. There are no hardcoded example plates in production. Missing estimates, closed days, stale dates, and fetch failures keep a real message in the plate frame. The native buttons and switch retain keyboard controls, focus outlines, pressed/checked state, and a polite result announcement. Rendering uses textContent for external dish names.

The plate title is the card headline, with one muted explanation underneath. Up to three distinct lunches share this same frame: a quiet “Other options” counter and native previous/next buttons cycle them, with arrow-key and horizontal-touch support. A small aria-live region announces the selected title without reading the whole receipt again. Goal/diet changes reset the alternative and tray extras.

Soup and dessert live below the plate as optional “Add to tray” chips. Their selected state is neutral grey; only scoop counts use blue. Totals sum the selected code-computed extras, with a muted “incl. extras” label. Diet labels stay plain muted text. Standing sides say “Beilagen counter · usually there.” A “Share plate” text button uses native sharing or clipboard feedback. Install icons reuse the existing plate drawing on the stone ground; no service worker or offline menu is introduced.
