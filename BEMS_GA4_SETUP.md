# BEMS + GA4 Website Insights update

Generated files:
- `bems-fe5049fb.html` — unlisted BEMS landing page
- `website-insight-ea929558.html` — GA4 aggregate dashboard
- `scripts/export_ga4_summary.py`
- `.github/workflows/update-ga4-summary.yml`
- `assets/data/ga-summary.json`
- `requirements-ga4.txt`

The BEMS page links to the existing `publication-insights-4d8c7a.html` page.

## Required GitHub Actions secrets
Repository → Settings → Secrets and variables → Actions:
1. `GA4_PROPERTY_ID`: numeric GA4 Property ID, not the G- measurement ID.
2. `GA4_SERVICE_ACCOUNT_JSON`: complete service-account JSON text.

Grant the service-account email Viewer access to the GA4 property:
GA4 Admin → Property access management → Add users.

Then run:
Actions → Update GA4 summary → Run workflow.

## Security
These HTML and JSON files are public once deployed through GitHub Pages. They contain only aggregated data.
The credential is written only to the temporary GitHub runner directory and is not committed.
Do not add the BEMS URLs to navigation, sitemap, README, or public links.

## Event names expected
`doi_click`, `oa_pdf_click`, `scholar_click`, `cited_by_click`, `patent_click`,
`cv_download`, `orcid_click`, `openalex_click`.

Events will appear only after the website sends them to GA4.
