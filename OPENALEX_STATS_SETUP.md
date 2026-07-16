# OpenAlex statistics cards

This update adds two source-specific cards to the homepage academic metrics band:

- Google Scholar: Citations, h-index and i10-index, using the website's existing Scholar data workflow.
- OpenAlex: Citations, h-index and i10-index, using the OpenAlex Author API and a daily GitHub Actions workflow.

No annual OpenAlex chart is included in this update. Existing Publications, Mendeley readers, Patents, Projects, Awards, publication sharing and Open Access functions are unchanged.

## Upload

Upload this package over the current repository while preserving the folder structure. The files are additions or a replacement for `index.html`; existing files not included in the ZIP must remain in place.

## GitHub Actions permissions

In the repository, use:

`Settings → Actions → General → Workflow permissions → Read and write permissions`

The workflow also supports manual execution from:

`Actions → Update OpenAlex metrics → Run workflow`

It runs daily at 02:17 UTC, equivalent to 10:17 in Taiwan.

## Optional OpenAlex API key

For a key-backed request, create this repository secret:

- `OPENALEX_API_KEY`

An optional contact email can be saved as:

- `OPENALEX_MAILTO`

Do not put the API key in HTML or JavaScript. The website reads only the generated `data/openalex_metrics.json` file.

## Failure behavior

If the OpenAlex request fails or returns invalid data, the update script exits without replacing the previous successful JSON. The rest of the website continues to work normally.
