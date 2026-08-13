# Wei-Hao Chiu Academic Website — Codex 專案工作規則

本規則適用於整個 `weihaochiu/weihaochiu.github.io` repository。

## 專案定位

- 這是 Wei-Hao Chiu 的個人學術網站與 GitHub Pages repository。
- 預設工作 branch 為 `main`。
- GitHub repository 必須是 `weihaochiu/weihaochiu.github.io`。
- 進行修改前，優先閱讀：
  - `WEBSITE_ARCHITECTURE.md`
  - `WEBSITE_REQUIREMENTS.md`
- 若本次修改改變網站架構、資料流、自動化流程、頁面責任或重要檔案關係，必須同步更新 `WEBSITE_ARCHITECTURE.md`。
- 若本次修改改變既有需求、資料規則或長期行為，必須同步更新 `WEBSITE_REQUIREMENTS.md`。

## 基本 Git 規則

- 預設直接在 `main` 工作。
- 不自動建立新的 branch。
- 不建立 Pull Request。
- 除了下方「GitHub Actions / Pages 驗證可以使用 `gh`」的明確例外，不使用 GitHub CLI（`gh`）。
- GitHub 更新只使用標準 Git 指令。
- 不修改與本次需求無關的檔案。
- 不使用 `git push --force`。
- 不自動執行 `git reset --hard`。
- 不刪除使用者既有未提交修改。
- 不把 `backup/`、備份 ZIP、暫存檔、Python cache 加入 Git。

## 只有明確要求修改時才修改

若使用者只是要求：
- 分析
- 評估
- 規劃
- Review
- 找原因
- 說明架構
- 比較方案

則：
- 不修改檔案
- 不 commit
- 不 push

只有當使用者明確要求：
- 修改
- 修正
- 新增
- 實作
- 更新
- 重構
- Debug 並修復
- 套用變更

才進入正式修改流程。

## 修改前檢查

先執行：

```powershell
git status
git branch --show-current
git remote -v
```

確認：
- repository 是 `weihaochiu/weihaochiu.github.io`
- branch 為 `main`
- 沒有與本次任務無關、來源不明的既有未提交修改

如果 branch 不是 `main`、remote 指向錯誤 repository，或有來源不明的既有修改：
- 可繼續做安全的分析
- 不得自動 commit / push
- 回報使用者目前阻擋原因

## 學術資料與 JSON 規則

- 不猜測論文、作者、專利、獎項、計畫、引用、DOI、ORCID、Scopus、Scholar、OpenAlex、Crossref、單位或其他學術資料。
- 外部資料找不到時保留空白或既有值，不自行補造。
- 使用者已人工確認、manual override、confirmed decision、永久排除或其他人工校正資料，不得被自動同步流程覆蓋。
- 修改資料 JSON 時，必須檢查使用該 JSON 的頁面、產生器、analytics、SEO、自動更新腳本與 GitHub Actions 是否需要同步調整。
- 修改 publication / author / patent / project 等 schema 時，必須搜尋所有讀取該欄位的程式碼，避免只改一端。
- 若有 source JSON 與 generated HTML 並存，應優先修正 source / generator，並依專案既有流程重新產生必要靜態頁面；不得只修正會被下次自動生成覆蓋的輸出檔。

## 網站相容性與既有功能保護

- 不因局部需求移除既有導覽、SEO、analytics、citation、author card、publication detail、academic monitor、insights 或 GitHub Actions 功能，除非使用者明確要求。
- HTML / CSS / JavaScript 修改需同時考慮 desktop、tablet、mobile。
- 連結修改後需確認 URL 格式正確；對可由程式驗證的內部連結，不留下明顯 broken path。
- 不任意重新命名現有公開 URL、帶 hash 的後台頁面或資料檔路徑。
- 若修改 GitHub Actions 或自動生成腳本，必須確認不會覆蓋人工校正資料。

## 修改完成後測試

先執行與本次修改直接相關的檢查或產生器。

最低限度執行完整 Python 單元測試：

```powershell
python -m unittest discover -s tests
```

並依修改內容增加必要檢查，例如：
- JSON 修改：確認 JSON 可解析，且必要 key / schema 正常。
- Python 修改：至少執行相關腳本的 syntax / unit test。
- 產生器修改：執行對應 generator，確認可正常完成。
- HTML / JS / CSS 修改：檢查受影響頁面引用的本機檔案路徑與明顯語法問題。
- GitHub Actions 修改：檢查 YAML 語法與 action 路徑、script 名稱是否存在。

如果測試或必要驗證失敗：
- 不 commit
- 不 push
- 保留目前修改
- 回報失敗原因與失敗項目

若某項測試因外部 API、憑證、網路或本機缺少依賴而無法執行，必須明確回報，不得把「未執行」說成「通過」。

## Push 前強制備份 GitHub 舊版本

任何 commit 或 push 前，先執行：

```powershell
git fetch origin main
```

fetch 成功後，先確認最新 `origin/main` 沒有意外追蹤 `backup/`：

```powershell
git ls-tree -r --name-only origin/main -- backup/
```

若沒有任何輸出，才執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\backup_before_push.ps1"
```

備份腳本必須：
1. `git fetch origin main`
2. 從最新 `origin/main` 建立 ZIP
3. 儲存到 `backup\backup_YYYYMMDDHHMM.zip`
4. 備份來源只能是 `origin/main`
5. 不得把本機尚未 push 的修改混入 ZIP
6. ZIP 檔案大小必須 > 0
7. 只整理符合 `backup_*.zip` 的本機備份
8. 依 LastWriteTime 由新到舊排序，只保留最新 10 個
9. 不得刪除其他 ZIP、其他使用者檔案或 `backup` 資料夾本身
10. 輪替完成後 `backup_*.zip` 數量必須 <= 10

如果備份或備份輪替失敗：
- 不 commit
- 不 push
- 保留目前修改
- 回報錯誤

## GitHub Backup 清理

`backup/` 只允許存在於本機；其中 `backup/backup_*.zip` 絕對不得被 Git 追蹤或上傳 GitHub。

每次準備更新 GitHub 時，在 `git fetch origin main` 成功後執行：

```powershell
git ls-tree -r --name-only origin/main -- backup/
```

若遠端已意外追蹤 `backup/`：
1. 不得刪除本機 `backup` 資料夾或 ZIP。
2. 只移除 Git / GitHub 對 `backup/` 的追蹤。
3. 確認 `.gitignore` 包含 `backup/*.zip`。
4. 只有 local `main` 可安全 fast-forward，且沒有來源不明的本機修改時，才可同步並執行：

```powershell
git rm -r --cached --ignore-unmatch backup
```

5. 再次確認本機 `backup` 與 ZIP 仍存在。
6. 建立清理 commit，例如：

```powershell
git commit -m "Remove accidentally uploaded backup files"
git push origin main
```

7. 再次 fetch 並確認 `origin/main` 不再追蹤 `backup/`。

若出現 divergence、conflict、無法 fast-forward、來源不明修改，或無法安全判斷：
- 不自動清理
- 不 force push
- 不 reset --hard
- 不刪除本機 backup
- 停止並回報使用者

## 備份成功後自動 commit / push

備份成功後依序執行：

```powershell
git status
git diff --stat
git add <本次任務相關檔案>
git status
```

再次確認：
- staged files 全部屬於本次任務
- `backup/` 沒有 staged
- 沒有意外加入大型產物、cache、暫存檔或秘密資訊

然後：

```powershell
git commit -m "<依本次修改內容自動產生簡潔 commit message>"
git push origin main
```

禁止：
- force push
- 自動建立 branch
- 建立 PR
- 使用 `gh` 取代一般 Git 操作，或進行與本次實機驗證無關的 GitHub 操作

如果 push 被拒絕、`origin/main` 已有新版本、需要 merge/rebase、出現 conflict 或任何遠端同步異常：
- 停止
- 不自行覆蓋遠端
- 回報使用者

## Push 後確認

執行：

```powershell
git fetch origin main
git ls-tree -r --name-only origin/main -- backup/
git status
git log -1 --oneline
```

`git ls-tree` 應無任何輸出。

## GitHub Actions / Pages 驗證可以使用 `gh`

一般 repository 更新仍使用 `git status`、`git fetch`、`git add`、`git commit`、`git push` 等標準 Git 指令；不得使用 `gh` 取代正常 Git 操作。

Codex 只有在 GitHub Actions 實機驗證所必需時，才可使用 GitHub CLI `gh`：
- 執行 `workflow_dispatch`
- 查詢 workflow run、等待完成、查看 conclusion 與 logs
- 查詢 GitHub Pages build / deployment
- 其他與本次 GitHub Actions 實機驗證直接相關的 read / dispatch 操作

即使在上述例外中，仍不得使用 `gh`：
- 建立或 merge Pull Request
- 建立、切換或修改 branch
- 取代正常 `git push`
- 執行與本次任務無關的 GitHub 操作

## Push 後 GitHub Actions / 正式網站實機驗證

### 判斷最終效果是否依賴 Action

如果本次修改涉及 GitHub Actions workflow、只能在 Actions 執行的外部 API、GitHub Secrets、GA4、citation 自動更新、OpenAlex、Crossref、Mendeley、Scholar、自動生成 JSON / HTML、Action commit 回 repository 的資料或 GitHub Pages deployment，而且不實際執行 Action 就無法看到最終效果，則 push 後必須執行與本次修改直接相關的 Action。不能只做 local syntax test 就宣稱功能完成。

純 CSS、靜態文字或不依賴 generator 的 HTML 等修改，不需要為了形式執行 Action。應依 data flow、generator、workflow、source JSON 與 generated HTML 判斷真正需要執行哪一個 workflow；不得任意執行 `run-all-workflows`。

### 執行並等待 workflow

若對應 workflow 支援 `workflow_dispatch`，push 後先執行：

```powershell
gh auth status
```

確認已登入後，執行與本次修改直接相關的 workflow，例如：

```powershell
gh workflow run update-ga4-summary.yml --ref main
```

取得這次新 run 的 ID，使用 `gh run watch <RUN_ID> --exit-status` 或同等方式等待完成。只有 `conclusion == success` 才能進入正式資料驗證；若為 `failure`、`cancelled`、`timed_out` 或 `action_required`，必須查看 logs、找出原因並修正，不得回報功能已完成。

如果 `gh auth status` 失敗或 GitHub CLI 未安裝，不得把 Action 驗證說成通過；必須明確回報應執行的 workflow、無法執行的原因，以及尚未驗證的項目。

### 驗證 Action 產物與 bot commit

GitHub Action 顯示 Success 不代表網站功能已驗證完成。如果 Action 會產生 JSON、HTML、citation / analytics data 或 generated pages，必須確認產物存在且內容符合本次需求。

若 workflow 產生新的 bot commit，必須執行 `git fetch origin main`，並記錄 workflow run ID、workflow conclusion、Action 產生的 commit SHA 與最新 `origin/main` SHA。不要把原本程式碼 commit SHA 誤認為最終 remote SHA。

如果本機因此落後 `origin/main`，只有 working tree 乾淨且可安全 fast-forward 時才能同步；不得 force push、`reset --hard` 或覆蓋 Action 產生的 commit。

### 驗證 GitHub Pages 與正式網站

若最終結果應顯示在 `https://weihaochiu.github.io/`，必須確認 GitHub Pages 部署的 commit SHA 包含最新 Action 產物；不可接受 `Action data commit = NEW_SHA` 但 `Pages commit = OLD_SHA`。

使用靜態 JSON 的功能還必須讀取正式網站 JSON，可加上 `?ts=<current timestamp>` 避免 CDN / browser cache 誤判，並確認：
- HTTP request 成功
- `generatedAt` 已更新
- 必要 key 與資料存在
- 不是舊版資料

最後必須檢查使用者實際看到的正式頁面。若正式 JSON 正確但頁面仍異常，繼續檢查 Pages cache、HTML deployment、JavaScript、JSON fetch 與 browser console，在找到原因前不得宣稱完成。

最後回報：
- 修改摘要
- 驗證 / 測試結果
- 測試通過數量（若測試框架有提供）
- 修改檔案數
- Backup ZIP 路徑
- Backup ZIP 大小
- Commit message
- Commit SHA
- Push 是否成功
- 最終 `git status`

## Backup 規則

- `backup/*.zip` 不得加入 Git repository。
- Push 前 ZIP 必須來自最新 `origin/main`，不是目前本機修改版本。
- 本機 `backup` 只保留最近 10 個 `backup_*.zip`。
- 不得刪除不符合 `backup_*.zip` 的 ZIP、其他使用者檔案或 `backup` 資料夾本身。

## 完整修改流程

使用者要求修改
↓
閱讀必要的架構 / 需求文件
↓
`git status` / branch / remote 檢查
↓
確認 `main` 與 repository 正確
↓
修改本次任務相關檔案
↓
必要時同步 source、generator、generated files、analytics、SEO、Actions、架構文件
↓
相關測試 / 驗證
↓
完整 unit tests
↓
必要測試通過
↓
`git fetch origin main`
↓
確認 GitHub 沒有追蹤 `backup/`
↓
從最新 `origin/main` 建立 ZIP 備份
↓
驗證 ZIP 並只保留最近 10 份
↓
`git diff` / `git status`
↓
只 stage 本次任務檔案
↓
commit
↓
push `origin main`
↓
判斷最終效果是否依賴 GitHub Actions
↓
若否，執行一般 Push 後確認
↓
若是，執行 `gh auth status`
↓
執行直接相關的 `workflow_dispatch`
↓
取得 run ID 並等待 workflow 結束
↓
確認 `conclusion == success`
↓
`git fetch origin main` 並確認 Action 產物與 bot commit SHA
↓
若結果需要 GitHub Pages，等待並驗證 Pages build commit
↓
檢查正式網站 / 正式 JSON 與使用者實際看到的結果
↓
再次確認 GitHub 沒有 `backup/`
↓
回報完整結果

## 使用者當次指示優先

如果使用者明確說：
- 這次不要 push
- 只修改不要 commit
- 不要備份
- 不要上傳 GitHub
- 只分析不要修改

則以當次使用者指示為準。
