# Staging environment

**Goal:** A `staging` branch that deploys to `yagizdas.github.io/platum/staging/` next to the live site, so Codex pushes there and Yagiz promotes to `main` manually.

**Done when:**
- The existing "Daily menu and GitHub Pages" workflow publishes `main` at `/platum/` (unchanged) and the `staging` branch at `/platum/staging/` in the same Pages deployment.
- A push to either `main` or `staging` redeploys both; the daily menu run keeps working.
- Staging uses the same daily menu data as main, and all its paths resolve under `/staging/` (including `/staging/label/`).
- README has a short "Staging" section: push to `staging`, check `/platum/staging/`, merge `staging` into `main` to ship.

**Notes:**
- The `staging` branch already exists (copy of main).
- Do not break the live site or the daily data pipeline.
- Delete this TASK.md in your final commit.
