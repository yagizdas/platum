# PWA install + fix failing jobs

**Goal:** Make Mensa Plate installable to the home screen, and find out why the GitHub Actions jobs keep failing and fix it.

**Done when:**
- Valid web manifest (name, 192/512 px icons, `display: standalone`) and a basic service worker; Lighthouse treats the site as installable.
- Android/Chrome: own "Add to home screen" button via `beforeinstallprompt`. iOS Safari: small dismissible hint banner ("Share → Add to Home Screen"). Show either one only from the user's 2nd visit on, never when already running standalone.
- Root cause of the recurring workflow failures identified and fixed; jobs pass on the next run.
- Everything works on the custom domain eatmensa.de as well as the staging path.

**Notes:**
- In your final reply, explain in one or two lines why the jobs were failing.
- Delete this TASK.md in your final commit.
