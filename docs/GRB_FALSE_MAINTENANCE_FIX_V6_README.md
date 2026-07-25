# GRB 隱藏維護公告誤判修正 V6

## 問題原因

GRB 的正常計畫詳目頁尾端固定嵌入一個通常隱藏的舊維護公告：

```html
<div id="no-service-container">
  本系統將於 5/30 進行系統升級作業，期間將暫停所有對外服務
</div>
```

原解析器掃描整份 HTML，只要看到「暫停所有對外服務」就直接判定為維護頁，
因此即使頁面已完整載入計畫名稱、計畫編號、研究期間與研究經費，仍被誤判失敗。

## 本版修正

1. 解析前移除專用的隱藏維護公告容器 `#no-service-container`。
2. 只有找不到正式計畫編號／系統編號時，才允許維護公告判定失敗。
3. 優先從 `.planTitle` 與 `.planTitleen` 讀取中英文計畫名稱。
4. 支援 GRB 現行的民國年月格式，例如 `11411 ~ 11510`。
5. 支援 `622千元`、`1083千元` 等研究經費格式。
6. 主管機關 `國家科學及技術委員會(本會)` 可正確對應英文名稱。
7. 新增自動測試，避免隱藏維護公告再次造成回歸錯誤。

## 安裝方式

解壓縮後，將下列檔案上傳至儲存庫根目錄並覆蓋同名檔案：

```text
scripts/update_grb_projects.py
```

GitHub Workflow 已監測此檔案，上傳後會自動觸發；也可手動執行：

`Actions → Update GRB projects → Run workflow`

## 以本次 artifact 驗證的結果

- GRB 18623445：622 千元，NT$622,000
- GRB 19484167：1,083 千元，NT$1,083,000
- GRB 18623445：1 Nov. 2025 – 31 Oct. 2026
- GRB 19484167：1 Aug. 2026 – 31 Jul. 2027

成功後 `data/projects.json` 會加入 `fundingAmountK`、`fundingAmountTwd`、
`fundingSource` 等欄位，現有 Projects 頁面會自動顯示金額。
