# GitHub Actions Monitor — installation

## Files to upload

Copy these files into the repository while preserving their paths:

- `bems-fe5049fb.html`
- `actions-monitor-4d8c7a.html`
- `assets/js/actions-data.js`
- `assets/js/actions-summary.js`
- `assets/js/actions-monitor.js`

## Remove the obsolete file

The earlier draft incorrectly created `website-admin-4d8c7a.html`. It is no longer used. Delete it after confirming that `bems-fe5049fb.html` opens normally.

## Monitoring scope

The dashboard includes automated GitHub Actions runs such as:

- `schedule`
- `push`
- `workflow_run`
- `workflow_call`
- `repository_dispatch`
- GitHub Pages/internal automatic runs

The following are excluded:

- `workflow_dispatch` manual runs
- `pull_request`
- `pull_request_target`
- `merge_group`

The table is therefore an automated-workflow monitor, not a copy of every item that may appear in GitHub's workflow sidebar. A workflow that has never produced an automated run in the inspected history will not appear.

## Refresh behaviour

- Data loads when either page is opened.
- Results are cached in the browser tab for 5 minutes.
- If a run is queued or running, the open page checks once again after 10 minutes.
- Up to the most recent 500 repository runs are inspected.

## Security boundary

The pages do not reproduce full logs, secrets, environment variables, request headers, or external API response bodies. Failed job and failed-step names are loaded only for the latest failed run.
