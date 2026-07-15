Wei-Hao Chiu Academic Website — Complete v23 Upgrade

This package completes all requested AI/SEO updates and corrects the email links on every page.

Upload all files to the repository while preserving folders:
- scripts/build_seo.py
- .github/workflows/build-seo.yml
- data/site_meta.json

After upload, GitHub Actions automatically runs "Build v23 AI and scholarly metadata".
It reads the existing 37 records in data/publications.json and commits the generated files back to main.

The build performs all of the following:
1. Adds 37 ScholarlyArticle JSON-LD records.
2. Inserts crawler-readable static publication cards into publications.html while preserving the existing JavaScript animation, search, sorting, filters, Unpaywall, Mendeley and sharing functions.
3. Generates 37 individual article pages under publications/.
4. Adds article-specific citation metadata and DOI metadata.
5. Adds article-specific Open Graph and Twitter metadata.
6. Upgrades Person Schema on every main HTML page.
7. Adds both correct emails to Person Schema and llms.txt:
   - weihao.chiu@gmail.com
   - d000019005@cgu.edu.tw
8. Replaces the footer email links on every main page with:
   - Personal Email
   - CGU Email
9. Updates the homepage Contact button to weihao.chiu@gmail.com.
10. Generates llms.txt with all main pages and all 37 publications.
11. Generates sitemap.xml with lastmod and all individual publication pages.
12. Expands robots.txt for Googlebot, Bingbot, OAI-SearchBot, GPTBot, ChatGPT-User, ClaudeBot, Claude-SearchBot, PerplexityBot, Google-Extended and Applebot-Extended.
13. Updates the displayed website version to v23.

After the workflow finishes, verify:
- https://weihaochiu.github.io/llms.txt
- https://weihaochiu.github.io/sitemap.xml
- https://weihaochiu.github.io/robots.txt
- https://weihaochiu.github.io/publications.html

The Actions workflow requires repository Settings > Actions > General > Workflow permissions to allow Read and write permissions.
