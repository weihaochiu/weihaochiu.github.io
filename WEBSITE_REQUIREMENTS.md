# Wei-Hao Chiu Academic Website — Requirements and Maintenance Record

## V20 approved information architecture

- Primary navigation: About, News, Research, Publications, Patents, Projects.
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
- Generated-page authorship validation is routed by `publicationType`: international journals, Chinese journals and conference papers require the research-publication author row and applicable affiliation/role legends, while theses require their static Basic Information author-card markup and `CreativeWork` structured data. Unsupported output types must fail validation explicitly rather than inherit another type's rules or be skipped.
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
- A GA4 automatic update is complete only after the generated data is committed to the repository and GitHub Pages reports `built` for the exact commit containing the updated `assets/data/ga-summary.json`.

## Theses and dissertations — 13 August 2026

- The Publications page presents graduate theses in a separate `Theses & Dissertations` section while retaining `data/publications.json` as the single scholarly-output source.
- Thesis records require a stable ID, `publicationType: "thesis"`, an explicit doctoral or master's `documentType`, degree, institution, department, advisor, pages, language, bilingual title, bilingual abstract, bilingual keywords, and a verified institutional repository URL when available.
- Never create or infer a DOI, journal, ISSN, volume, issue, JCR quartile, impact factor, FWCI, OpenAlex work, Crossref record, Mendeley metric, or citation count for a thesis without a verified source.
- Every thesis has all four bibliometric analytics flags set to `false` and `analytics.excludeFromResearchAnalytics: true`. Adding or removing thesis display records must not change homepage publication counts, the research-publication total and core-journal total (currently 57 and 38 respectively), or any citation, journal, authorship, collaboration, FWCI, JCR, IF, publisher, quartile, co-author, corresponding-author or first-author analytics.
- Thesis detail pages are generator-owned, use Schema.org `CreativeWork`, and expose bilingual metadata plus the institutional repository link. They must not show empty or zero-valued journal/citation metric widgets.
- Thesis authors use the same `authors.json`-backed `AuthorCards` renderer and interaction behavior as every other scholarly-output detail page, including the existing `me` styling for Wei-Hao Chiu; no publication type may introduce a separate author-card implementation.
- Manually verified DOI-less thesis metadata is protected with `metadataSource: "manual_verified"` and `automationProtection.protected: true`; automated enrichment must preserve the record unchanged.
- Academic Monitor must suppress duplicate thesis candidates using repository URL or normalized title/year/publication type when DOI identity is unavailable.

## Verified publication addition — 23 October 2026

- Include DOI `10.1016/j.cej.2026.183177` as an international journal publication with all four standard bibliometric analytics flags enabled. The research-output/core-journal totals are now 41/38; the two theses remain excluded.
- Preserve the user-provided Abstract, four Highlights and original graphical abstract. Do not fabricate publisher keywords, equal-contribution statements, citation counts or missing bibliographic fields.

## Actions queue retention — 23 October 2026

- Every workflow using `website-content-write` must set `queue: max` and `cancel-in-progress: false` in its workflow-level concurrency block. Preserve serialized writes and retain pending updates within GitHub's 100-run queue limit.
- A new participant must adopt the same policy and update the concurrency regression test. Do not split this group into per-workflow groups to avoid cancellations, because these jobs write overlapping data and generated files.
- Verify the policy with multiple overlapping workflow runs, including Crossref and journal updates; inspect successful runs, resulting data commits and the deployed data rather than treating a cancelled run as an update.

## Curated academic news — 23 October 2026

- Homepage Latest News shows up to three manually curated updates, newest first, after metrics. View all news opens `news.html`; each complete entry has a stable story URL and historical hash-link compatibility. Primary navigation includes News between About and Research, linking to `news.html`.
- News source is `data/news.json`; rebuild through the SEO generator rather than editing generated news HTML. News does not add scholarly outputs or awards to analytics.
- The SDSE 2026 Honorable Mention poster award is recorded in Awards (11 total), with a separate News entry and the user-provided poster-side group photograph. Publish neither certificate nor award-announcement slide. Preserve the full photograph composition and provide a compressed lazy-loaded preview, accessible caption and full-size link.
- Display 14–16 October 2026 explicitly as conference dates. Preserve certificate author order; do not infer photo identities, a ceremony date, unverified translations or a DOI.

## News archive performance and tone — 23 October 2026

- Award announcements use natural congratulatory language rather than certificate-verification prose. Preserve verified award names and collaborators; do not invent personal roles or identities.
- Homepage retains only the latest three summaries. Optional thumbnail links sit beside the text (140 px on desktop/tablet, 88 px on mobile), preserve the complete image composition and use a separate small WebP asset. Photo-free entries have no empty placeholder.
- Latest and annual archive pages contain at most 10 summaries each, with static Previous/Next links and year navigation. Full article text and display photos belong to individual story pages. Do not load all historical news JSON in the browser or implement pagination by hiding already-downloaded full stories.
- Preserve `news.html#<id>` links and existing navigation, analytics, award counts and SEO; include generated news URLs in the sitemap.

## TwIChE 2025 news — 23 October 2026

- Publish the user-confirmed 29–30 November 2025 Frontier Materials Research Group (FMRG) visit to the 72nd TwIChE annual meeting at NCKU in Tainan and congratulate Kun-Mu Lee and Wei-Hao Chiu on their Chemical Engineering Masterpiece Award. Preserve supplied attendee names without inventing English spellings.
- Use the conference group photo as the primary thumbnail, with both group and award-presentation photos on the full story. Optional additional photographs must not increase list-page image payloads. Reuse the existing award record without incrementing the award total.

## CSET award reporting — 23 October 2026

- Include the official CSET 2023 Taiwan Innotech Bronze Medal report as news; label 28 December 2023 as the report publication date. Reuse the existing award without increasing counts.
- The TwIChE 2025 story uses the user-selected two-paragraph celebratory copy beginning “A happy milestone for our team”. Keep the CSET source label dated 18 September 2025, the TwIChE official recipient-list link, November conference dates and photographs. The award record retains the work title.
- News page headers show the title without the generic research-updates subtitle; retain descriptive SEO metadata.

## Experience and Education logos — 23 October 2026

- Experience and Education show the eight user-supplied institution/company logos beside their corresponding records. Preserve original artwork, clip only surrounding whitespace, provide descriptive alt text, and keep marks proportional and readable on desktop/tablet/mobile. The NSP/URECO career record shows both company logos.

- The user-supplied FMRG logo appears on the existing Frontier Materials Research Group service card in Experience.

- Both Energies Guest Editor cards display the user-supplied Energies and MDPI logos; the wide Energies source uses the same whitespace-only CSS crop.

- About logo pairing audit: all three Chang Gung University career entries show its university logo, with the supplied CSET/CRST center logo where available. Each degree shows both its university and original department logo within the existing department link. NSP/URECO and both Energies/MDPI pairs remain present; FMRG and ITRI retain their own marks. No unprovided center or award logo is inferred.

## Funding and award logos — 23 October 2026

- `app.js` maps the existing agency/organization names to local logos without changing academic JSON: NSTC for two NSTC projects, TwIChE for the two chemical-engineering society awards, and the user-supplied year-neutral TIE logo for the 2023/2025 Innotech awards. Unmatched records retain their text layout. Logo images preserve proportions and accessible names on desktop/mobile; About and Projects version their CSS/JS URLs.
- NSTC artwork is the complete original header SVG from https://www.nstc.gov.tw/folksonomy/detail/95e64744-1e2e-42ed-8a16-1b95c91f21d5?l=ch (only `viewBox` attribute casing normalized); TwIChE artwork is https://www.twiche.org.tw/sites/default/files/logo-h.png, linked by https://www.twiche.org.tw/zh-hant. TIE artwork was supplied by the user. All assets reside in `assets/images/institutions/`.

## Chinese publication additions — 23 October 2026

- Add Materialsnet articles 51511 and 51512 as separately dated Chinese professional-review installments (2022-10-31 and 2022-11-02), and the Lawdata 537187 Vacuum Technology review (2021-06, 34(2), source-reported page 27). Preserve Chinese author names where verified English forms are unavailable; missing DOI/citation data stay empty. No full article text is republished.
- The supplied Airiti 2021 module-review URL already belongs to `10.29803/ce.202108_68(4).0006` and is not duplicated. Total outputs/research outputs become 46/44; core journal and journal-metric counts remain 38, and the two theses remain excluded. New Chinese records have all four bibliometric analytics flags false. Existing records and manual decisions are preserved.

- Source-verified new Chinese records are automation-protected. Citation-disabled records render no Google Scholar count badge in either static SEO cards or browser-rendered cards; unknown counts must not appear as zero.

## User-provided conference records — 23 October 2026

- Add 13 distinct user-supplied conference manuscripts from SDSE 2023/2025/2026, PESI 2026, TwIChE 2023/2025, IEDMS 2023, and the 18th FPG Applied Technology Seminar (2023). Keep the existing 2008 conference record; conference/overall/research counts become 14/59/57, with 38 core journal records and two excluded theses unchanged. Preserve manuscript author order, abstract, keywords and affiliation links; full-paper versus abstract labels describe supplied document types, without claiming proceedings publication or peer review. No journal DOI, citation count, JIF or FWCI is copied.
- Optional `conference` stores name/acronym, conference date range, location, official URL, presentation/acceptance status, abstract number and presenting author when explicitly evidenced. `sourceDocument` stores only a basename; source Office files, private local paths, login screenshots, template biographies and reviewer comments are not published. All new records are automation-protected. `build_seo.py` and shared `app.js` render matching conference information, preserving source/generator ownership. `sdse.png` is the user-supplied year-neutral conference logo, shared with matching award cards; TwIChE reuses the existing official mark.
- SDSE 2026 LMA is explicitly Accepted, Poster, abstract 00145, with Wei-Hao Chiu as presenting author, supported by the user screenshot and document legend. Other acceptance/presentation claims remain blank unless explicitly evidenced. Preserve Yan-Duo Lin as written in the 2023 SDSE HTM abstract and flag correspondence uncertainty. The Chinese laser-crystallization paper is authored by 陳思羽, Wei-Hao Chiu, Kun-Mu Lee; its asterisk has no explicit correspondence legend. Filename dates are not presentation dates. Preserve the independent existing FPG award record.
- Conference date sources: https://2025.sdsemcut.com/ ; https://2026.sdsemcut.com/site/mypage.aspx?lang=en&pid=25&sid=1708 ; https://sdse.mcut.edu.tw/p/406-1063-62228%2Cr1466.php?Lang=zh-tw ; https://polymers-int.org/ ; https://2023twiche.conf.tw/site/mypage.aspx?lang=cht&pid=901&sid=1494 ; https://iedms2023.nsysu.edu.tw/ ; https://iucc.mcut.edu.tw/p/406-1016-60038%2Cr11.php?Lang=zh-tw . TwIChE 2025 retains the previously verified 29–30 November conference dates.

## Selected conference additions and bilingual FPG names — 23 October 2026

- Add 13 user-selected manuscripts: IEDMS 2021 (2), 2021 TwIChE/68th annual meeting (2), A-COE 2023 (2), PVSEC-35 2024 (2), 19th FPG 2024 (1), 20th FPG 2025 (2), and WCPEC-9 2026 (2). Conference/overall/research-output totals become 27/72/70; core international journals remain 38 and theses remain 2. Retain stable event-specific IDs even where titles resemble other conference or journal outputs.
- FPG conference cards and detail pages explicitly display English and Traditional Chinese conference names, using optional `conference.nameEn` and `conference.nameZh`. Use the user-confirmed English name `19th Formosa Plastics Group Applied Technology Seminar`, adjusting the ordinal to 18th and 20th for the corresponding editions. Preserve existing public URLs and the independent award record.
- 2021 TwIChE retains its event branding but uses its actual conference dates, 6–7 January 2022. WCPEC-9 is scheduled for 15–20 November 2026 in Daejeon; a future event date does not prove completed presentation. Dates come from official event/organizer sources, never filenames.
- Preserve manuscript-specific authors, affiliations, abstracts and supplied keywords. Local abstract/poster author discrepancies are recorded as manual-review warnings; do not merge author lists. Keep missing bibliometrics and unverified acceptance/presentation fields empty, and protect all manually curated records from automated enrichment. Private source documents and local paths are not published.
- Date sources: https://www.electrochem.org/ecsnews/focus-issue-on-selected-papers-from-the-international-electron-devices-and-materials-symposium-2021-iedms-2021 ; https://www.twiche.org.tw/zh-hant/news/504 ; https://www.a-coe2023.com/ ; https://www.pvsec.org/pvsec35/index.html ; https://ord.mcut.edu.tw/p/406-1010-64658%2Cr1795.php?Lang=zh-tw ; https://iucc.mcut.edu.tw/p/406-1016-73617%2Cr11.php?Lang=zh-tw ; https://www.pvsec.org/conference/future-conference.html . WCPEC-9 uses the PVSEC organizer page because the formerly advertised event domain currently displays a parked-domain page.

## CGU Pure conference additions — 23 October 2026

- Added two source-verified proceedings records: ISOS 15 (2024, Berlin, 30 September–2 October) and EU PVSEC 2025 (Bilbao, 22–26 September). Preserve the distinct ordered author lists and institutional source URLs. Publication year is known; event dates remain conference metadata. DOI, abstract, presentation type, correspondence and per-author affiliation links remain unknown. Both records are automation-protected and excluded from bibliometric metrics; international collaboration remains unknown.
- Conference/overall/research-output totals are now 29/74/72; 38 core journals and two excluded theses remain unchanged. The existing generator creates `publications/isos-15-2024-pvdf-hfp-space-reliability.html` and `publications/eu-pvsec-2025-pvdf-hfp-space-reliability.html`, listing and discovery entries from the authoritative JSON and taxonomy.
- Static and browser conference labels distinguish proceedings papers, full manuscripts, extended abstracts and abstracts using the existing document type.


## Publication attention widgets — 23 October 2026

DOI-bearing research outputs display official PlumX PlumPrint and Altmetric donut widgets at the right of each article, with provider popovers and clickable details. DOI-less outputs and theses are excluded. Empty PlumX data and Altmetric records without mentions are hidden. DOI presence does not guarantee provider coverage. Preserve official metric values, labels and artwork, including available X-user counts, patent references and Mendeley readers. Mobile places widgets below article content; external service failures must leave publication content usable.

Independent DOI-bearing article pages must also show both attention widgets beside the bibliographic overview. Keep the abstract, highlights, graphical abstract and citation history at full width; stack widgets after the overview on mobile.

Attention widgets and author metadata must initialize in either order without duplicating the author-affiliation block.

Mobile centers the widget pair and opens PlumX popovers above the graphic; Altmetric popovers open above the donut. Desktop PlumX popovers open left. Resize updates the PlumX direction to avoid clipping on narrow screens.

- WCPEC-9 conference records use the user-supplied original `assets/images/institutions/wcpec-9.png` logo in both `app.js` publication cards and `build_seo.py` detail pages, with proportional responsive sizing and descriptive alt text.
- PVSEC-35 records likewise use the user-supplied original `assets/images/institutions/pvsec-35.png` logo in publication cards and generated detail pages.

- ISOS 15 uses the user-approved white-background `assets/images/institutions/isos-15.png` logo in shared publication cards and generated detail pages, preserving proportions, responsive sizing and accessible alt text.

## Conference link audit — 23 October 2026

- Conference URLs must identify the correct edition on an official conference or organizer site; publication repositories and journal special-issue calls are not conference websites. `conference.urlType` distinguishes `conference-site`, `organizer-page`, `official-program`, and `unavailable`; optional `websiteNote` explains an unavailable official website. Shared browser cards and SEO-generated pages use matching labels; no URL means no external conference button. Preserve publication/source URLs and all scholarly metadata.
- See `CONFERENCE_LINK_AUDIT.md` for the audit of all 29 conference records (18 event groups), verified destinations and unavailable sites. Do not restore failed/repurposed historical domains without rechecking their live content and edition.
