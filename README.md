# Wei-Hao Chiu Academic Website

Official academic website and research portfolio of **Dr. Wei-Hao Chiu**.

**Website:** https://weihaochiu.github.io/

## Overview

This repository hosts a multi-page academic website published through GitHub Pages.  
The website presents research interests, publications, patents, projects, professional experience, education, and awards.

The current primary navigation is:

- About
- Research
- Publications
- Patents
- Projects

Legacy Experience, Education, and Awards URLs are retained as redirects to the corresponding sections of the About page.

## Repository structure

```text
.github/workflows/   GitHub Actions workflows
assets/              Stylesheets, JavaScript, images, icons, and other web assets
data/                Verified publication, patent, project, award, and metric data
docs/                Maintenance, setup, requirements, and archived update documentation
scripts/             Data-processing and maintenance scripts
*.html               GitHub Pages website pages and redirect pages
```

## Deployment

The website is deployed from:

- Branch: `main`
- GitHub Pages source: `/ (root)`

Files required by the website, including HTML pages, `.nojekyll`, `robots.txt`, `sitemap.xml`, and `site.webmanifest`, should remain in the repository root.

## Local preview

Because the website loads records from JSON files, preview it through a local web server rather than opening the HTML files directly:

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000/
```

## Data integrity

Verified records in `data/` are authoritative. Do not replace verified publication, patent, project, award, taxonomy, or metric data with inferred or unverified content.

Automated scripts and GitHub Actions should preserve the last valid data when an external service is temporarily unavailable.

## Documentation

- [Documentation index](docs/README.md)
- [Website requirements and maintenance record](docs/WEBSITE_REQUIREMENTS.md)
- [Unpaywall and publication sharing setup](docs/UNPAYWALL_SHARE_SETUP.md)
- [Archived V20–V21 update notes](docs/archive/V20_V21_UPDATE_NOTES.md)

## Maintenance principle

Keep only this primary `README.md` in the repository root. Place other Markdown documentation under `docs/` so that the GitHub Pages root remains easy to review and maintain.
