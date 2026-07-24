# GRB GitHub Actions timeout fix V5

## 覆蓋檔案

將 ZIP 解壓縮後，把以下檔案上傳至儲存庫根目錄並覆蓋同名檔案：

- `.github/workflows/update-grb-projects.yml`
- `scripts/update_grb_projects_browser.py`

## 本版修正

1. `page.goto()` 改為 `wait_until="commit"`，不再等待可能永遠不觸發的 `DOMContentLoaded`。
2. GRB 首頁載入失敗時仍繼續搜尋頁與兩筆已知計畫頁。
3. 封鎖不影響計畫資料的字型、圖片、影音、分析與 reCAPTCHA 外部資源。
4. HTML 與 JSON 診斷檔優先保存。
5. PNG 截圖改為 5 秒、非全頁；截圖失敗不影響 HTML/JSON。
6. 維護頁被辨識後立即保存，不再額外等待 20–25 秒。
7. URL 仍會自動移除尾端冒號及其他句尾標點。
8. curl 診斷加入連線與總時間限制。
9. GitHub job 設為最長 12 分鐘並使用即時輸出。

## 執行

上傳後進入：

`Actions → Update GRB projects → Run workflow`

## 成功時

`data/projects.json` 會加入：

- `fundingAmountK`
- `fundingAmountTwd`
- `fundingSource`

網站已有經費顯示功能，不需再改前端。

## 若仍失敗

在該次 Action 的 Artifacts 下載 `grb-diagnostics-...`。本版應至少包含：

- `known-18623445.html`
- `known-18623445.json`
- `known-19484167.html`
- `known-19484167.json`

PNG 可能存在，也可能因 GitHub runner 的字型問題而略過。JSON 中會記錄：

- 實際請求網址
- 最終網址
- HTTP 狀態
- User-Agent
- 畫面文字摘要
- 導航錯誤
- 截圖是否成功

若 HTML/JSON 仍顯示舊維護頁，代表 GRB 對 GitHub runner 回傳的內容與台灣一般瀏覽器不同，已不是等待條件造成的程式錯誤。
