# Research Page Update Package — 15 July 2026

This ZIP is designed to be uploaded over the existing `weihaochiu.github.io` repository.

## Files included

- `research.html` — redesigned Research page without charts.
- `assets/css/research.css` — styles used only by the Research page.
- `assets/js/research.js` — dynamically calculates research periods, publication counts, newest papers, most cited papers, Google Scholar citations, and Mendeley readers.
- `data/research_areas.json` — approved research-theme order and abstract-grounded research narratives.
- `WEBSITE_REQUIREMENTS.md` — updated maintenance requirements.

## Upload rule

Upload the included folders and files to the repository root and allow files with the same names to be replaced.

Do not delete or replace these verified data files:

- `data/publications.json`
- `data/publication_taxonomy.json`
- `data/mendeley_metrics.json`
- `data/patents.json`
- `data/projects.json`
- `data/awards.json`

The Publications page is not changed by this package.

## Local preview

Because the Research page loads JSON files, preview it through a local web server rather than opening the HTML file directly:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000/research.html`.
