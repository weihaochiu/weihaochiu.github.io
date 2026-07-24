# GRB 診斷與網址修正 V4

## 本版修正

1. 自動移除 GRB 網址尾端可能誤入的冒號、逗號、句點等標點。
2. GitHub Actions 日誌將 URL 與錯誤分行顯示，避免 GitHub 把冒號包進超連結。
3. Chromium 改用一般 Chrome User-Agent，不再使用明顯的爬蟲 User-Agent。
4. 先開啟 GRB 首頁及研究人員搜尋頁，再進入計畫詳目頁，模擬人工成功路徑。
5. 每次執行保存 GitHub runner 實際看到的 HTML、完整頁面截圖及 metadata。
6. Workflow 不論成功或失敗，都會上傳 `grb-diagnostics-*` artifact。

## 安裝

將 ZIP 內容上傳到儲存庫根目錄並覆蓋同名檔案，接著執行：

`Actions → Update GRB projects → Run workflow`

## 執行後檢查

若仍失敗，在該次 Action 頁面最下方的 **Artifacts** 下載：

`grb-diagnostics-<run id>-<attempt>`

優先查看：

- `known-18623445.png`
- `known-18623445.json`
- `known-18623445.html`
- `known-19484167.png`
- `known-19484167.json`
- `known-19484167.html`

JSON 會明確列出 requested URL、`repr()`、最終跳轉網址、HTTP 狀態、頁面標題與瀏覽器 User-Agent。
