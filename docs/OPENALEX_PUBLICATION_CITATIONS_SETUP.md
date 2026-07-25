# OpenAlex per-publication citation update

This update adds an OpenAlex citation count and OpenAlex work-record link to every publication card that OpenAlex can match by DOI.

## Files in this update

- `.github/workflows/update-openalex-stats.yml`
- `scripts/update_openalex_publications.py`
- `assets/js/openalex-publications.js`

Upload the ZIP contents to the repository root and preserve the folders. Replace the existing workflow file with the supplied `.yml` file.

## First run

1. Open the repository's **Actions** tab.
2. Choose **Update OpenAlex metrics**.
3. Select **Run workflow**.
4. After the successful run, confirm that `data/openalex_publication_metrics.json` exists.
5. Wait for GitHub Pages deployment, then refresh the Publications page with `Ctrl+F5`.

The workflow also inserts the following script into `publications.html` if it is not already present:

```html
<script src="assets/js/openalex-publications.js"></script>
```

## Display behavior

For an OpenAlex-matched DOI, a publication card shows, for example:

```text
23 Google Scholar citations ↗
19 OpenAlex citations ↗
```

The OpenAlex count links to the corresponding OpenAlex work page. A record that OpenAlex cannot match is left unchanged; no false zero is displayed.

## Update behavior

The workflow runs daily and when the publication list or relevant OpenAlex files change. If the API update fails, the existing JSON remains unchanged and the previous successful values continue to be used.
