# Font trial + date header

**Goal:** Let Yagiz try 5 fonts live on staging with a button, and replace the "Your Plate" heading with the date.

**Done when:**
- The "Your Plate" heading is replaced by the date of the shown menu (e.g. "Friday, 20 Nov"); the separate weekday label ("Thursday" etc.) is merged into it, no duplication.
- A small floating "Aa" button cycles through these fonts (Google Fonts) and shows the current font name; the choice persists in localStorage:
  1. Plus Jakarta Sans (all text)
  2. DM Sans (all text)
  3. Bricolage Grotesque (headings + numbers) + DM Sans (body)
  4. Fraunces soft, SOFT/WONK axes on (headings) + Figtree (body)
  5. Instrument Serif (headings) + Instrument Sans (body)
  6. Current font (so he can compare)
- Prices/kcal/protein numbers stay aligned (tabular figures where the font supports it); nothing overflows on a ~390px phone.
- Switcher is easy to remove later (one flag/component).

**Notes:** Delete this TASK.md in your final commit.
