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
