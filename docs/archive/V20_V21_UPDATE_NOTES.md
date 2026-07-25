# V20–V21 Update Notes

This file preserves version-specific notes that were previously stored in the repository root `README.md`. The root README is now maintained as a long-term project overview.

## V20 update package notes

The V20 package was designed to be uploaded over the existing V19 GitHub Pages repository.

### Historical upload rule

The verified collection files below were not to be deleted or replaced by incomplete update packages:

- `data/publications.json`
- `data/patents.json`
- `data/projects.json`
- `data/awards.json`

These files contain verified records and remain authoritative.

### V20 changes

- Main navigation reduced to **About | Research | Publications | Patents | Projects**.
- Experience, Education and Awards consolidated into `about.html`.
- Old Experience, Education and Awards URLs redirect to the relevant About sections.
- Homepage redesigned as a longer academic-profile page.
- Photo caption removed; formal unit information moved beside the job title.
- Publications / All outputs chart switch added.
- Charts redesigned with clear axes, values, gridlines, hover states and accessible labels.
- Research-theme selector changed to alphabetical order.
- Open Graph and Twitter preview metadata upgraded to a 1200 × 630 social image.
- Profile image supplied in JPEG and WebP formats.
- Google Scholar cited-by URL construction fixed with `urljoin`.
- Site version updated to V20.

## V21 additions

- Unpaywall-powered legal OA links added to the Publications page.
- Compact per-publication sharing added with stable DOI-derived anchors.
- Setup instructions moved to [`../UNPAYWALL_SHARE_SETUP.md`](../UNPAYWALL_SHARE_SETUP.md).

## Local preview

Because records are loaded from JSON files, preview the website through a local web server:

```bash
python -m http.server 8000
```
