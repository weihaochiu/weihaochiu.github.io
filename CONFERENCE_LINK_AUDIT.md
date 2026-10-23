# Conference link audit — 23 October 2026

Scope: all 29 conference records, grouped into 18 editions/legacy groups. Checked the live HTTP response, redirects, TLS validation and edition content, plus official organizer evidence. A search-index copy alone does not establish current availability. No credentials or TLS bypass were used.

Only official conference sites, edition-specific organizer pages or official programmes are published as conference links. Unavailable official websites are explicitly disclosed and have no button. Publication repository links remain publication records.

| Event | Records | Published destination | Finding |
|---|---:|---|---|
| MRS proceedings (legacy record) | 1 | No conference link | Existing legacy record has no conference object or conference website. Preserve its DOI and separate publication record; do not infer an event website from conflicting proceedings/event years. |
| SDSE 2025 | 1 | [organizer-page](https://biomed.mcut.edu.tw/p/406-1055-74478%2Cr1770.php?Lang=zh-tw) | Original conference host fails DNS; use the host university conference announcement, which identifies the original official URL. |
| SDSE 2026 | 2 | [conference-site](https://2026.sdsemcut.com/site/mypage.aspx?lang=en&pid=25&sid=1708) | Official event site identifies MCUT as host and the 2026 edition. |
| PESI 2026 | 1 | [conference-site](https://polymers-int.org/) | Official invitation, dates, venue and organizing committee match the event. |
| TwIChE 2025 | 1 | [organizer-page](https://www.twiche.org.tw/zh-hant/news/779) | Previously blank. Society announcement identifies the edition and original 2025twiche.tw domain; that domain fails DNS, so retain the society page. |
| TwIChE 2023 | 3 | [conference-site](https://2023twiche.conf.tw/site/mypage.aspx?lang=cht&pid=901&sid=1494) | Official edition site lists society leadership, NTU venue and 2023 dates. |
| FPG 2023 | 1 | [organizer-page](https://iucc.mcut.edu.tw/p/406-1016-60038,r11.php?Lang=zh-tw) | MCUT organizer report for 18th seminar; encoded comma returned 404, literal comma returns 200. |
| SDSE 2023 | 2 | [organizer-page](https://sdse.mcut.edu.tw/p/406-1063-62228%2Cr1466.php?Lang=zh-tw) | MCUT event announcement explicitly names the original SDSE 2023 website; retain the edition-specific announcement. |
| IEDMS 2023 | 2 | [organizer-page](https://moes.nsysu.edu.tw/p/406-1206-319085,r4857.php?Lang=zh-tw) | Original NSYSU event host has a TLS hostname mismatch. Use NSYSU organizer department announcement identifying the same event and official host. |
| IEDMS 2021 | 2 | No conference link | Removed ECS special-issue call: a journal call is not the conference website. A historical iedms2021.org reference was found in an exhibitor report, but the host fails DNS and no live official replacement could be verified. No conference button is published. The ECS source remains valid evidence for event dates, not a website destination. |
| TwIChE 2021 | 2 | [organizer-page](https://www.twiche.org.tw/zh-hant/news/504) | Official society announcement identifies 2021 branding and January 2022 dates. Historical 2021twiche.conf.tw timed out; retain society announcement. |
| A-COE 2023 | 2 | No conference link | Historical official site was indexed with the correct conference and organizers, but live host fails DNS. No live organizer replacement was verified; no conference button is published. |
| PVSEC-35 | 2 | [conference-site](https://www.pvsec.org/pvsec35/index.html) | Official PVSEC archived edition site, not the current conference homepage. |
| FPG 2024 | 1 | [organizer-page](https://ord.mcut.edu.tw/p/406-1010-64658%2Cr1795.php?Lang=zh-tw) | MCUT official edition-specific announcement identifies the CGU host and 19th seminar. Retain the historical announcement rather than a potentially reused registration portal. |
| FPG 2025 | 2 | [organizer-page](https://iucc.mcut.edu.tw/p/406-1016-73617,r11.php?Lang=zh-tw) | MCUT organizer report for 20th seminar; encoded comma returned 404, literal comma returns 200. |
| WCPEC-9 | 2 | [organizer-page](https://www.pvsec.org/conference/future-conference.html) | Official PVSEC future-conference listing identifies WCPEC-9, 2026 dates and Daejeon. Retain this page; do not follow the former event-domain link without verifying it (currently no readable conference content). |
| ISOS 15 | 1 | [conference-site](https://www.helmholtz-berlin.de/events/isos-15/index_en.html) | Replaced CGU paper repository with HZB official ISOS 15 event site. The paper repository is preserved separately as publicationUrl. |
| EU PVSEC 2025 | 1 | [official-program](https://www.eupvsec.org/images/2025/conference/EUPVSEC2025_ConferenceProgram_web_v3.pdf) | Replaced CGU paper repository with official 2025 programme PDF, which identifies Bilbao and 2025 dates. Indexed recap URL returns 404 live. The paper repository remains publicationUrl. |

All 15 distinct published destinations returned HTTP 200 with a standard browser User-Agent and normal TLS validation. PESI rejects the default Python User-Agent with HTTP 403 but returns the correct 2026 event content for the browser User-Agent. This verifies availability and official edition identity on the audit date, not permanent uptime. IEDMS 2021 and A-COE 2023 remain unresolved for a currently usable official website; the legacy MRS record retains no conference link.
