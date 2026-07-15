# Wei-Hao Chiu Academic Profile — V20 update package

This ZIP is designed to be uploaded **over the existing V19 GitHub Pages repository**.

## Important upload rule

Do not delete the current `data/publications.json`, `data/patents.json`, `data/projects.json`, or `data/awards.json` files. They contain the verified records and are intentionally not duplicated in this update archive.

Upload all V20 files to the repository root and allow them to replace files with the same names. Existing collection JSON files remain in place.

## V20 changes

- Main navigation reduced to **About | Research | Publications | Patents | Projects**.
- Experience, Education and Awards consolidated into `about.html`.
- Old Experience, Education and Awards URLs redirect to the relevant About sections.
- Homepage redesigned as a longer academic-profile page.
- Photo caption removed; formal unit information moved beside the job title.
- Publications / All outputs chart switch added.
- Charts redesigned with clear axes, values, gridlines, hover states and accessible labels.
- Research-theme selector now uses alphabetical order.
- Open Graph and Twitter preview metadata upgraded to a 1200 × 630 social image.
- Profile image supplied in JPEG and WebP formats.
- Google Scholar cited-by URL construction fixed with `urljoin`.
- Site version updated to **V20**.

## Local preview

Because the records are loaded from JSON, preview through a web server:

```bash
python -m http.server 8000
```
