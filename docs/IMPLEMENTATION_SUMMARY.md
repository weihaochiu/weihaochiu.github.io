# GRB 自動更新 V2 實作內容

- `data/projects.json` 為唯一正式 Project 清單。
- 姓名、單位、GRB ID、計畫編號及名稱皆符合時，直接正式加入。
- 正式加入後，自動同步進 `knownPlans`，不需手動維護第二份清單。
- 手動從 `projects.json` 刪除已追蹤計畫時，自動加入 `ignoredGrbIds`，避免再次出現。
- 重新手動加入同一 GRB 計畫時，自動解除忽略並恢復追蹤。
- `grb_projects_pending.json` 僅保留身分匹配不完整或必要欄位不足的例外資料。
- 自動欄位：計畫編號、主管機關、期間、年度、狀態、經費、來源網址。
- 保留人工欄位：中英文簡介、人工修訂後的題名、校內計畫。
- 經費以 GRB 千元欄位保存，另換算成 TWD 元並顯示於網站。
- GitHub Actions 每月執行，也會在人工修改 `projects.json` 時同步追蹤狀態。
