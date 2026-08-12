# Wei-Hao Chiu Academic Website — Requirements and Maintenance Record

## V20 approved information architecture

- Primary navigation: About, Research, Publications, Patents, Projects.
- The site name links to the homepage; Home is not repeated in the navigation.
- About consolidates Experience, Education and Awards.
- Publications, Patents and Projects retain dedicated searchable pages.
- Homepage uses a long-scrolling profile layout with concise section summaries.
- The annual chart defaults to Publications and can switch to All outputs.
- Research-theme filters are alphabetized; years remain newest first.
- Formal affiliation is displayed with the role, not as a photograph caption.
- Google Scholar metrics are obtained only from profile ID `ZYbNQb8AAAAJ` and retain the last valid values if retrieval fails.
- Social preview metadata uses a dedicated 1200 × 630 image.

## Research page update — 15 July 2026

- The Research page uses three established themes in this order: Perovskite Solar Cells, Redox Flow Batteries, and Dye-Sensitized Solar Cells.
- Do not create an `Advanced Materials and Optoelectronic Research` theme until a coherent body of work has developed sufficiently to justify it.
- The Research page does not use a publication bar chart or separate Research Topics labels.
- Each theme contains an approximately 200–250-word English research narrative synthesized from the abstracts and findings of the existing publications assigned to that theme.
- Each theme automatically calculates its research period from the earliest and latest assigned publications.
- Each theme automatically displays its peer-reviewed publication count.
- Each theme automatically lists the three newest publications and the three most cited publications.
- Featured publication entries display DOI, current Google Scholar citations, and Mendeley readers with outbound links when verified URLs are available.
- Publication selections and metrics must be derived from the existing verified files: `data/publications.json`, `data/publication_taxonomy.json`, and `data/mendeley_metrics.json`.
- The Publications page is not modified by this Research page update.

## Data preservation

Verified collection files in `data/` remain authoritative. Do not replace them with inferred or generated content.

## Publication Open Access and sharing — 15 July 2026

- The website is hosted on GitHub Pages, not Google Sites.
- Each publication DOI is checked through the official Unpaywall API by GitHub Actions.
- A publication displays `Open Access PDF` only when Unpaywall supplies a direct legal PDF URL.
- When Unpaywall supplies only a legal OA landing page, display `Open Access Version` instead.
- A non-OA publication must not display an OA button or an empty placeholder.
- OA links open in a new tab and must not attempt a forced cross-origin download.
- Each publication has a compact `Share` action rather than a permanently expanded social-media list.
- Use the native Web Share interface when supported; otherwise provide Copy link, Email, LinkedIn, X (Twitter), and Facebook.
- Shared links must target a stable DOI-derived publication anchor on `publications.html`.
- Opening a shared publication URL must scroll to and temporarily highlight the target record.
- Unpaywall data are stored separately in `data/unpaywall.json`; verified publication records in `data/publications.json` remain unchanged.

<!-- PUBLICATION_AUTHORSHIP_REQUIREMENTS_START -->
## Publication authorship and affiliation metadata

- `data/authors.json` stores an author's current profile and current affiliation.
- `data/publications.json` stores the affiliation and author role associated with the specific publication.
- Keep the existing `authors` string array for backward compatibility and store structured details in `authorships`, `affiliations`, and `authorshipMetadata`.
- Source priority is manually verified data, Europe PMC/JATS, Crossref, OpenAlex, and explicitly enabled publisher HTML metadata.
- Never infer equal contribution from adjacent author order.
- Never infer a corresponding author from the final author position.
- API failures and empty responses must not erase existing verified values.
- `verified` means the structured fields are complete enough for automatic display and analytics; `partial` means one or more fields remain unknown; `manual` means a human-verified override is authoritative.
- Records with conflicting or incomplete source data must use `requiresManualReview: true` and list the unresolved fields.
- Generated HTML must be rebuilt from the authoritative JSON; individual files under `publications/` must not be edited manually.
<!-- PUBLICATION_AUTHORSHIP_REQUIREMENTS_END -->

## Publication types and analytics scope — 3 August 2026

- `data/publications.json` remains the single source for all scholarly outputs; do not split it into separate files by type.
- Every output must have a unique `id`, `publicationType`, `documentType`, `language`, `peerReviewStatus`, and four explicit boolean `analytics` flags.
- Public presentation is divided into International Journal Publications, Chinese Journal Publications, and Conference Publications; Other and Unclassified sections appear only when records exist.
- Only records with `analytics.coreJournalCount: true` count toward the homepage core-publication number, Research-page peer-reviewed totals, and the default annual publication charts.
- JCR, journal IF, quartile, journal and publisher analytics use only `analytics.journalMetrics: true` records.
- FWCI is displayed or analyzed only for `analytics.fwci: true` records.
- Content-completeness requirements are type-aware. Conference and Chinese professional outputs are not automatically required to have Highlights or a Graphical Abstract.
- Academic Monitor must preserve source document type and language, propose an explainable publication type, show confidence and reason, and require a manually editable final type before a confirmed record is added.
- DOI-less outputs must use the stable `id` for detail-page slugs, anchors, sitemap entries, and duplicate validation.

## International collaboration analytics — 3 August 2026

- Every record in `data/publications.json` stores an `internationalCollaboration` object; the dashboard reads the saved decision and must not recalculate it on every page load.
- International collaboration requires at least one linked Taiwan author address and at least one linked non-Taiwan author address. Author names, nationality and journal country are never used as evidence.
- `needs-review` records are excluded from the collaboration-rate denominator. The denominator is `international + domestic`.
- A manually publisher-verified decision uses `manualOverride: true`. Manually corrected affiliations use `authorshipMetadata.manualAffiliations: true` and locked affiliation fields; automatic Crossref/OpenAlex refreshes must not append rejected affiliations again.
- Partner-country and partner-institution charts count each publication once per unique partner. Publication-level evidence, confidence, warnings and evaluation date remain downloadable as CSV.
- Impact comparisons are descriptive and do not claim that collaboration caused citation or FWCI differences.

## Website Insights traffic sources — 13 August 2026

- Website Insights retains the existing GA4 Traffic channels visualization based on `sessionDefaultChannelGroup`.
- A separate Top traffic sources table displays the GA4 `sessionSource` and `sessionMedium` values with sessions and active users for the last 28 days through yesterday.
- Source and medium values are preserved exactly as returned by GA4; they are not reclassified or converted to hyperlinks.
- The GA4 export stores up to 20 traffic sources ordered by sessions descending in the top-level `trafficSources` array of `assets/data/ga-summary.json`.
- The table remains readable on desktop, tablet and mobile. Missing or empty `trafficSources` data displays `No data` without preventing the rest of Website Insights from loading.
