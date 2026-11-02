Mensa Plate answers one question: what should I put on my plate for this goal at Arcisstraße today?

The app uses the Achromatic ledger direction (seed 1475843428), with a pale stone ground from a canteen tray, Geist typography, and a receipt-like list of real dishes. Scoop counts are its distinctive visual element; one blue hue marks those counts. A single centered column suits one daily decision. No chart, sidebar, decorative food imagery, or extra destination is needed.

The content width is 760px: 808px shell minus two 24px gutters. The receipt's item grid is 72px + flexible name column + 62px price, with two 12px gaps; at phone widths it becomes 50px + flexible name column + 52px price with two 8px gaps. The controls and receipt share the same left and right edges.

All displayed dish names and estimates come from the generated JSON. There are no hardcoded example plates in production. Missing estimates, closed days, stale dates, and fetch failures keep a real message in the plate frame. The native buttons and switch retain keyboard controls, focus outlines, pressed/checked state, and a polite result announcement. Rendering uses textContent for external dish names.
