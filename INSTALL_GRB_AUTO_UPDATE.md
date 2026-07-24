# GRB 計畫自動更新安裝包 V2

## 安裝方式

將 ZIP 解壓縮後，把所有資料夾與檔案上傳至
`weihaochiu/weihaochiu.github.io` 儲存庫根目錄並覆蓋同名檔案。

需要上傳的檔案：

- `.github/workflows/update-grb-projects.yml`
- `scripts/update_grb_projects.py`
- `data/grb_project_sources.json`
- `data/projects.json`

上傳完成後，GitHub Actions 的 `Update GRB projects` 會因 push 自動執行。

## V2 的正式加入規則

只要 GRB 詳目頁同時確認：

1. 研究人員包含「邱偉豪／Wei-Hao Chiu／Chiu, Wei-Hao」；
2. 執行機構包含「長庚大學／Chang Gung University」；
3. 具有 GRB ID、計畫編號及計畫名稱；

該計畫就會直接加入 `data/projects.json`，不需要先到 pending 清單核准。

正式加入後，同一次執行也會自動加入 `knownPlans` 持續追蹤清單，之後每月更新期間、狀態、主管機關與本期經費。

## 手動移除即永久排除

`data/projects.json` 是唯一正式來源。

如果你手動從 `data/projects.json` 刪除一筆已追蹤的 GRB 計畫，下一次 Action 會：

1. 確認該 GRB ID 已不在正式 Project 清單；
2. 從 `knownPlans` 移除；
3. 自動加入 `ignoredGrbIds`；
4. 在 `removedPlans` 留下移除時間與原因；
5. 日後即使搜尋再次找到，也不會自動加回。

若之後想恢復，只要把該計畫重新放回 `data/projects.json`，系統會自動解除 ignore 並恢復追蹤。

## pending 清單現在只放什麼

`data/grb_projects_pending.json` 只保留以下例外：

- 姓名符合但單位不符合或缺失；
- 單位符合但姓名不符合或缺失；
- GRB 詳目缺少必要的計畫名稱、計畫編號、年度或 GRB ID；
- 頁面格式異常，無法安全建立完整 Project 資料。

姓名與單位都確認且資料完整的計畫不會進 pending，而會直接正式加入。

## 第一次執行會做什麼

1. 測試 GRB HTML 解析器及自動加入／手動移除邏輯。
2. 在 `assets/js/app.js` 中加入或更新 GRB 經費顯示。
3. 依 GRB ID 更新現有國科會計畫。
4. 搜尋新的 GRB 計畫並自動加入符合姓名與單位者。
5. 擷取「本期經費（千元）」並寫入：
   - `fundingAmountK`
   - `fundingAmountTwd`
   - `fundingDisplayEn`
   - `fundingDisplayZh`
6. 建立：
   - `data/grb_projects_snapshot.json`
   - `data/grb_projects_pending.json`
7. 自動更新 `data/grb_project_sources.json` 的持續追蹤與排除清單。
8. 自動提交真正有變動的檔案。

## 排程

每月 22 日台灣時間約 06:30 自動執行，也可在 Actions 頁面手動執行。

當你手動修改 `data/projects.json` 時，也會觸發一次 Action，以便自動同步追蹤或排除狀態。

## 保護機制

- GRB 無法連線時保留原資料，不清空欄位。
- 不會刪除校內計畫。
- 不會覆蓋人工撰寫的 `scopeEn`、`scopeZh`。
- 現有中英文題名預設不被 GRB 覆蓋。
- 新計畫缺少英文題名時，先以中文題名顯示並標記 `needsEnglishTitle: true`，不會自行翻譯或猜測。
- 計畫編號與既有設定不符時拒絕更新。
- 計畫數量異常減少或經費換算不一致時停止寫入。

## GitHub Actions 權限

請確認：

`Settings → Actions → General → Workflow permissions → Read and write permissions`

否則 Action 可以抓資料，但無法把更新提交回儲存庫。
