# Unpaywall and publication sharing setup

## What is already implemented

The website now contains:

- `scripts/update_unpaywall.py` — checks every DOI in `data/publications.json`.
- `.github/workflows/update-unpaywall.yml` — updates OA links weekly, manually, and whenever the publication data or updater changes.
- `data/unpaywall.json` — local OA data read by the Publications page.
- Publication Share buttons with native sharing and a desktop fallback menu.

## First GitHub run

After uploading this package to the repository's `main` branch:

1. Open the repository on GitHub.
2. Select **Actions**.
3. Select **Update Unpaywall Open Access Links**.
4. Select **Run workflow** and run it on `main`.
5. Wait for the workflow to finish.
6. Confirm that GitHub Actions committed an updated `data/unpaywall.json`.

The workflow also runs automatically every Monday at 12:40 Taiwan time and when any of these files changes:

- `data/publications.json`
- `scripts/update_unpaywall.py`
- `.github/workflows/update-unpaywall.yml`

## Contact email

The updater uses the academic email already publicly displayed on the website as its default Unpaywall contact email.

To override it, create the optional repository secret:

1. **Settings** → **Secrets and variables** → **Actions**.
2. Select **New repository secret**.
3. Name: `UNPAYWALL_EMAIL`.
4. Value: the preferred contact email.

This is optional; the workflow works without adding the secret.

## GitHub Pages setting

Keep the existing GitHub Pages branch publishing configuration. The workflow commits only `data/unpaywall.json` to `main`; GitHub Pages then republishes the updated static site normally. There is no need to switch the Pages source to a separate deployment workflow.

## Display rules

- Direct legal PDF found: `Open Access PDF`.
- Legal OA page found but no direct PDF: `Open Access Version`.
- No OA version found: no OA button.
- API failure: preserve the last valid OA link when available.

## Sharing behavior

- Supported phones and computers open the operating system's native Share interface.
- Other browsers show Copy link, Email, LinkedIn, X (Twitter), and Facebook.
- The shared URL contains a DOI-derived anchor and opens directly at the selected publication.
