# GitHub Actions Monitor installation

Copy the following files into the repository while preserving their paths:

- `website-admin-4d8c7a.html`
- `actions-monitor-4d8c7a.html`
- `assets/js/actions-data.js`
- `assets/js/actions-summary.js`
- `assets/js/actions-monitor.js`

## Behaviour

- Only workflow runs whose GitHub event is `schedule` are included.
- Manual (`workflow_dispatch`) and push-triggered runs are excluded.
- The pages read the public GitHub REST API without storing a token.
- Results are cached in the current browser tab for five minutes.
- There is no continuous polling when all workflows are idle.
- If a workflow is queued or running, the open page checks again after ten minutes.
- Failed Job and Step summaries are fetched only for the latest failed scheduled run.
- Full logs, environment variables, secrets and external API response bodies are never copied into the page.

## API usage per page load

Typical load:

- 1 request for the workflow list.
- 1–3 requests for recent scheduled runs, depending on the number of runs.
- 1 additional request for each workflow whose latest scheduled run failed.

The summary page does not request job details.

## Optional navigation link

Add this link to any existing private-link administration or analytics navigation:

```html
<a href="website-admin-4d8c7a.html">Website administration</a>
```

## Important security boundary

The random filename and `noindex` directives reduce accidental discovery but do not provide authentication. The detail page intentionally displays only low-to-moderate-risk operational metadata already obtainable from the public repository’s GitHub Actions API.
