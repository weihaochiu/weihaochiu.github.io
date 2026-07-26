# Academic Record Monitor

## Included behavior

- One GitHub Action: `.github/workflows/check-academic-monitor.yml`
- Three independent check modules:
  - `scripts/check_publications.py`
  - `scripts/check_patents.py`
  - `scripts/check_projects.py`
- One combined result file: `data/academic-monitor.json`
- One private, non-indexed dashboard: `academic-monitor-4d8c7a.html`
- Copy one record, one category, or every pending record into a ChatGPT-ready request.

The workflow never modifies `publications.json`, `patents.json`, `projects.json`,
`authors.json`, generated publication pages, or SEO files.

## First run

1. Upload all files while preserving their folders.
2. Confirm **Settings → Actions → General → Workflow permissions → Read and write permissions**.
3. Open **Actions → Check academic records → Run workflow**.
4. After the workflow commits `data/academic-monitor.json`, open:
   `https://weihaochiu.github.io/academic-monitor-4d8c7a.html`

## Schedule

The workflow runs Monday and Thursday at 09:10 Asia/Taipei. GitHub scheduled
workflows may start later than the exact cron time.

## Important limitations

- ORCID and Crossref provide structured APIs and are the most reliable monitor.
- Google Patents does not promise a stable public search API. Layout or access
  changes are displayed as a source error.
- GRB does not provide a documented stable public API for this use. Unexpected
  responses are displayed as warnings/errors.
- A zero candidate count is trustworthy only when the relevant source status is
  `success`. It must not be trusted when status is `warning` or `error`.
