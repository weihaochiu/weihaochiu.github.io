# GRB 經費抓取修正 V3

## 問題原因

原更新器使用 requests 讀取 GRB 詳目頁，但 GRB 現在先回傳 HTML 外殼，
計畫編號、期間與研究經費等內容由瀏覽器端 JavaScript 載入。
因此 Action 顯示成功，實際上 `data/projects.json` 沒有寫入經費欄位。

## 本版修正

新增 Playwright/Chromium 瀏覽器 fallback：

- `scripts/update_grb_projects_browser.py`
- 更新 `.github/workflows/update-grb-projects.yml`

執行順序：

1. 原本的靜態解析器先執行。
2. Chromium 開啟 GRB 首頁建立 session。
3. Chromium 開啟每個 GRB 詳目頁，等待 JavaScript 載入。
4. 解析計畫編號、期間、主管機關與本期經費。
5. 寫入 `fundingAmountK` 與 `fundingAmountTwd`。
6. 原有 `app.js` 自動顯示金額。
7. 研究人員搜尋頁也改用 Chromium，以恢復新計畫自動發現。

## 安裝

將 ZIP 內容上傳到儲存庫根目錄，覆蓋同名檔案：

- `.github/workflows/update-grb-projects.yml`
- `scripts/update_grb_projects_browser.py`

上傳後進入 Actions → Update GRB projects → Run workflow。

## 驗證

成功後 `data/projects.json` 的 GRB 計畫應出現：

```json
"fundingAmountK": 1200,
"fundingAmountTwd": 1200000,
"fundingSource": "GRB"
```

實際金額以 GRB 回傳值為準。

`data/grb_projects_snapshot.json` 應顯示：

```json
"fetchMode": "playwright",
"ok": true
```

若 Chromium 仍無法取得任何一筆已知計畫，本版會讓 Action 失敗，
不再以綠色成功狀態掩蓋資料未更新的情況。
