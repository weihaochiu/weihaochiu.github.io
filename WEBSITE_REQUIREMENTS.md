# Wei-Hao Chiu Academic Website — Requirements and Maintenance Record

Last consolidated: 14 July 2026

## Version 17 architecture

- Converted the standalone Google Sites embed into a multi-page GitHub Pages website.
- Independent pages: Home, Experience, Education, Research, Publications, Patents, Projects, and Awards.
- Shared CSS and JavaScript are stored under `assets/`; structured records are stored under `data/`.
- GitHub Pages canonical base URL is `https://sandorchiu.github.io/`.
- The v16 content remains the authoritative data source for v17.


This file is the authoritative handoff specification for future revisions.  
Future updates should follow these requirements unless the website owner explicitly changes them.

## 1. Audience and presentation

- The website is a public-facing academic profile, not a maintenance dashboard.
- All visible copy must be written from a visitor’s point of view.
- Do not show internal notes such as:
  - “Static manual edition”
  - placeholder explanations
  - API setup notes
  - maintenance instructions
  - “replace when checking Scholar”
- The main interface is English.
- Chinese information is retained where it is part of an official Taiwan/China record:
  - Taiwan and China patents
  - awards received in Taiwan
  - Taiwan research-project titles and agencies
- English-language journal publications do not require Chinese translations.
- Section titles and top navigation must use one consistent language: English.

## 2. Google Sites compatibility

- The website is embedded in Google Sites through an embedded-code iframe.
- Never use `href="#section"` for the internal navigation.
- Top navigation must use JavaScript in-frame scrolling (`scrollTo` or `scrollIntoView`) so Google Sites does not open a blank iframe page.
- Publication-year bars must be clickable and scroll to the corresponding publication year.
- If a filter hides a selected year, reset the publication filters before scrolling.
- Keep the website responsive on desktop, tablet, and mobile.
- The deliverable must include:
  - `index.html`
  - `google-sites-embed-code.txt`
  - `README.md`
  - `WEBSITE_REQUIREMENTS.md`
  - a ZIP containing all files

## 3. Header and profile

- Display:
  - Wei-Hao Chiu, Ph.D.
  - 邱偉豪
  - Associate Researcher
  - Center for Sustainability and Energy Technologies, Chang Gung University
- Use the official CGU portrait:
  - https://www.cgu.edu.tw/cset-en/ServerFile/Get/4efb2c88-1274-4ef2-b420-d45598415136
- The portrait replaces the CGU/CSET logo.
- Keep the portrait proportional, unobtrusive, and responsive.
- Profile links:
  - Google Scholar
  - ORCID
  - Scopus
  - Web of Science — https://www.webofscience.com/wos/author/record/JCE-6812-2023
  - CGU Pure Publications
  - CGU Profile
  - GRB Projects
  - LinkedIn
  - ResearchGate
  - OpenAlex
  - Frontier Materials Research Group

## 4. Experience

- 2024–Present — Chang Gung University, Center for Sustainability and Energy Technologies, Associate Researcher
- Feb. 2022–Feb. 2024 — Chang Gung University, Center for Reliability Sciences and Technologies, Associate Researcher
- Mar. 2021–Jan. 2022 — Chang Gung University, Center for Green Technology, Postdoctoral Researcher
- Nov. 2012–Feb. 2021 — Neo Solar Power / United Renewable Energy, Principal Engineer / Assistant Manager
- 2008–2011 — Industrial Technology Research Institute, Part-time Student Research Assistant
- Include Frontier Materials Research Group membership.
- Include Guest Editor positions:
  - Advances in Photovoltaic Technologies, Energies
  - Advances in Photovoltaic Technologies II, Energies

## 5. Education

- Ph.D., Electro-Optical Engineering, National Chiao Tung University, Aug. 2011
- M.S., Electro-Optical Engineering, National Chiao Tung University, Jun. 2005
- B.S., Physics, National Sun Yat-sen University, Jun. 2003
- Display a bilingual “Graduate Theses” subsection beneath the degree cards.
- Doctoral dissertation (2011):
  - English title: *Study on Electron Transport Mechanism in Metal Oxide Photoanode Electrode for Dye-Sensitized Solar Cells*
  - Chinese title: 染料敏化太陽電池的金屬氧化物光電極中電子傳遞機制之研究
  - Advisor: Prof. Wen-Feng Hsieh (謝文峰)
  - Language/pages: English, 104 pages
  - Record: https://hdl.handle.net/11296/y6376u
- Master’s thesis (2005):
  - English title: *Modified Spontaneous Emission in a Tightly Pumped Nd:YVO₄ Laser with Degenerate Resonator*
  - Chinese title: 微聚焦端泵浦摻釹釩酸釔雷射在簡併共振腔下被修正過的自發輻射
  - Advisor: Prof. Wen-Feng Hsieh (謝文峰)
  - Language/pages: English, 42 pages
  - Record: https://hdl.handle.net/11296/mc89fj

## 6. Publications

- Maintain 37 unique journal publications unless a new verified publication is added.
- Publications must support:
  - keyword search
  - year filter
  - research-theme filter
  - date/citation/title sorting
- Do not display “Copy citation”.
- The author’s name must be highlighted.
- Article title and DOI button must open the official DOI/publisher record.
- Publication-by-year bars must jump to each year’s list.

### Abstract policy

- Do not display publication or patent abstracts, abstract summaries, abstract-status notes, or abstract-expansion controls anywhere on the website.
- Do not retain or index hidden abstract text in the standalone HTML or Google Sites embed code.
- Publication titles and DOI buttons remain linked to official publisher records so visitors can consult the source directly.

### Google Scholar citations

- The citation label must explicitly say “Google Scholar citations”.
- Do not label OpenAlex, Scopus, or Crossref counts as Google Scholar counts.
- Use the hyperlink embedded in the spreadsheet’s `Cited by` cell as the authoritative source for each Cited by button.
- Only apply links that are actual Google Scholar cited-by cluster URLs containing `cites=`.
- Do not use the spreadsheet title hyperlink for the publication title. Publication titles must continue to open the DOI/publisher record.
- Never fabricate or infer a Google Scholar cluster ID.
- For zero-citation records or records absent from the supplied spreadsheet, show the citation count without a misleading hyperlink.
- Current citation snapshot from the owner-supplied spreadsheet (14 July 2026):
  - Total citations: 1,206
  - h-index: 15
  - i10-index: 23
- Citation metrics and cited-by links are manually updated when the owner supplies a new spreadsheet snapshot.

## 7. Patents

- The authoritative patent set is the uploaded `合併12篇專利.pdf`.
- Display exactly these 12 records:
  1. M612985 — 照度可調整之棚架
  2. US 8,470,150 B2 — Method of Fabricating Electrode Structures on Substrate
  3. US 2018/0062002 A1 — Solar Cell
  4. CN102456480A — 太阳电池结构
  5. CN102456482B — 基板电极结构的制造方法
  6. CN206236681U — 太阳能电池
  7. CN207367985U — 双面太阳能电池及太阳能电池模块
  8. I407579 — 基板電極結構的製造方法
  9. I449190 — 染料敏化太陽能電池
  10. M539701 — 太陽能電池
  11. M551346 — 雙面太陽能電池及太陽能電池模組
  12. M611184 — 太陽能電池模組
- Taiwan/China records must show:
  - English title
  - official Chinese title
  - inventors in English and Chinese when available
  - assignee in English and Chinese
  - direct patent-record link
- Do not show a separate raw TIPO-link list.
- Do not add a newly discovered patent until the owner confirms it belongs to him.
- Candidate patent verification must check:
  - inventor name is Wei-Hao Chiu / 邱偉豪 / 邱伟豪
  - assignee is an organization where he worked or collaborated
  - title, inventors, applicant, and dates agree with the official record

## 8. Research projects

Display four projects:

1. NSTC 114-2622-E-182-006  
   產學協作開發用於鈣鈦礦模組製程之智慧真空閃蒸裝置與成膜參數調控技術

2. NSTC 115-2221-E-182-052  
   結合摻雜型二氧化鈦奈米線電極與異質疊層共價有機框架隔離膜之長效全釩液流電池開發  
   Do not display “GRB ID 19484167” as the project number.

3. Chang Gung University innovative prototype project, Apr.–Oct. 2024  
   即時光譜分析應用於全釩液流電池電量監測之微型外掛裝置

4. Chang Gung University innovative prototype project, May–Oct. 2022  
   液流電池材料與系統快速測試模組開發

- Taiwan projects should display English and Chinese titles.
- Show project number, role, period, status, and verified project-record link where available.
- Do not fabricate a project, project period, role, agency, or grant abstract.
- The SPT Alliance record and the low-orbit-satellite project record must not appear unless the owner explicitly supplies and approves verified information in a future update.

## 9. Awards

- Awards are sorted newest to oldest.
- Awards received in Taiwan must display both English and Chinese:
  - award title
  - organizer
  - awarded work
  - recipients
- Current award list:
  1. 29 Nov. 2025 — 化工傑作獎 / Chemical Engineering Masterpiece Award
  2. 18 Oct. 2025 — 2025台灣創新技術博覽會發明競賽銀牌獎 / Silver Medal Award, 2025 Taiwan Innotech Expo Invention Competition
     - Awarded work: 太陽能電池模組及其製造方法 / Solar Cell Module and Manufacturing Method Thereof
     - Patentee / patent applicant: 長庚大學 / Chang Gung University
     - Inventors: 李坤穆、邱偉豪、賴朝松 / Kun-Mu Lee, Wei-Hao Chiu, and Chao-Sung Lai
     - Award date and place: 18 Oct. 2025, Taipei City
     - Source: owner-supplied award certificate
  3. 17 Oct. 2025 — Excellent Poster Award / 優良壁報獎, SDSE 2025
  4. 14 Oct. 2023 — Taiwan Innotech Expo Bronze Medal / 台灣創新技術博覽會發明競賽銅牌獎
  5. 14 Jun. 2023 — Formosa Plastics Group Applied Technology Seminar Excellence Award / 優等獎
  6. 6 Apr. 2023 — Green Energy and Battery Symposium First Prize / 壁報競賽第一名
  7. 6 Apr. 2023 — Green Energy and Battery Symposium Honorable Mention / 壁報競賽佳作
  8. 6–7 Jan. 2022 — Taiwan Institute of Chemical Engineers Annual Meeting Honorable Mention / 壁報論文競賽佳作
  9. 1 Dec. 2011 — ITRI Paper Award / 工研院論文獎
  10. 21 Nov. 2008 — Materials Science Student Paper Award, Honorable Mention / 材料科學學生論文獎佳作

## 10. Data integrity rules

- Prefer official publisher, DOI, patent office, GRB/NSTC, university, or award-certificate sources.
- Do not guess:
  - Google Scholar cluster IDs
  - project numbers
  - patent ownership
  - award dates
- If exact information cannot be verified, clearly flag it in this requirements file or the README, not in visitor-facing copy.
- New records must be deduplicated by DOI, patent number, project number, or award identity.

## 11. Future update workflow

When the owner provides a new publication, patent, project, award, metric, or corrected link:

1. Read this `WEBSITE_REQUIREMENTS.md`.
2. Verify the new information against the most authoritative available source.
3. Update the single-file HTML and embedded-code text.
4. Update this requirements file if a rule or long-term preference changes.
5. Run validation checks:
   - no internal `href="#..."` navigation
   - no maintenance-facing notes
   - no abstract content or fabricated Scholar ID
   - correct counts in section chips
   - all external links use a new tab
   - mobile layout remains usable
6. Package all files into a new versioned ZIP.


## v13 updates (2026-07-14)
- Main section order: Experience → Education → Research → Publications → Patents → Projects → Awards.
- Top navigation displays synchronized totals for Publications, Patents, Projects, and Awards.
- Patents, Projects, and Awards use the same annual bar-chart, year-grouping, newest/oldest/title sorting, single-column card layout, search, year filter, and clear-filter interaction pattern as Publications.
- Patent annual counts use the patent grant/publication year. Project annual counts use the documented or project-number-derived start year, with each multi-year project counted once. Award annual counts use the award date.
- Added “SPT Alliance – Development of Perovskite–Silicon Tandem Solar Cell and Module Technologies” (2025-04-01 to 2029-03-31), role: Co-Principal Investigator (共同主持人).
- Standardized the two Chang Gung University innovative prototype projects to Principal Investigator (PI / 計畫主持人).


## v14 updates (2026-07-14)
- Expanded the homepage statistics panel to seven cards: journal publications, total citations, h-index, i10-index, patents, research projects, and awards.
- Publication, patent, project, and award totals in the homepage cards are synchronized from the embedded datasets.
- Removed all publication and patent abstracts, summaries, status labels, expansion controls, abstract-search indexing, and abstract-related data from the website.


## v15 updates (2026-07-14)
- Removed every instance of the unsupported SPT Alliance project.
- Did not add the withdrawn low-orbit-satellite project.
- Research-project totals are 4 across the navigation, homepage statistics, section chip, annual chart, filters, and dataset.
- Award totals are 10 across the navigation, homepage statistics, section chip, annual chart, filters, and dataset.
- Award cards with no public record URL do not display an empty “Award record” button.

## v16 updates (2026-07-14)
- Corrected the 2025 certificate-derived award entry and removed all data from the prior incorrect entry.
- Added “2025台灣創新技術博覽會發明競賽－銀牌獎 / Silver Medal Award, 2025 Taiwan Innotech Expo Invention Competition.”
- Awarded work: “太陽能電池模組及其製造方法 / Solar Cell Module and Manufacturing Method Thereof.”
- Patentee / patent applicant: Chang Gung University. Inventors: Kun-Mu Lee, Wei-Hao Chiu, and Chao-Sung Lai.
- Award date: 18 Oct. 2025, Taipei City.
- The award total remains 10 and the 2025 annual count remains 3.