# GRB 安全更新規則

- `data/projects.json` 為唯一正式 Project 清單。
- GRB 頁面必須同時具有明確標籤，且系統編號、計畫編號、期間與經費符合固定格式，才接受解析結果。
- 計畫資料只會填入目前為空白的 JSON 欄位；任何非空白內容都不會被自動覆蓋。
- 中英文摘要與關鍵字只接受 `中文摘要`、`英文摘要`、`中文關鍵字`、`英文關鍵字` 四個精確標籤，或程式明列的固定 JSON key。
- 不使用近似標籤、整頁文字、最長文字區塊或一般標題推測內容。
- 新發現的計畫只寫入 `grb_projects_pending.json` 供人工檢查，不直接加入正式網站。

## 學術監控人工確認

- 每筆候選資料固定使用三種狀態：`已確認是本人的`、`已確認非本人的`、`尚未確認`。
- 瀏覽器先以 `localStorage` 保存本次確認與備註，並可一次複製成完整 JSON 貼回 ChatGPT。
- ChatGPT 維護 `data/academic_monitor_review_decisions.json`；每筆紀錄包含穩定的 `reviewKey`、判定、完整候選資料、備註與確認時間。
- `confirmed_not_mine` 不會加入成果 JSON，且後續監控會依 `reviewKey` 永久排除，不再重複要求使用者確認。
- `confirmed_mine` 需先查核來源，再更新對應的 `publications.json`、`patents.json` 或 `projects.json`；監控也不再重複顯示已完成判定的項目。
- GRB 監控只讀取 Playwright 更新器產生的結構化 snapshot/pending JSON，不使用 GRB 不支援的 `/search?query=...` 網址。
- 人工確認並加入 `projects.json` 後，才會同步進 `knownPlans`，開始進行空白欄位補值。
- 手動從 `projects.json` 刪除已追蹤計畫時，自動加入 `ignoredGrbIds`，避免再次出現。
- 重新手動加入同一 GRB 計畫時，自動解除忽略並恢復追蹤。
- 既有非空白題名、摘要、關鍵字、期間、經費、單位與其他人工內容都由人工／ChatGPT 修改 JSON 維護。
- 經費以 GRB 千元欄位保存，另換算成 TWD 元並顯示於網站。
- GitHub Actions 每月執行，也會在人工修改 `projects.json` 時同步追蹤狀態。
