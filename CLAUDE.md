# CLAUDE.md — my-project（網站開發主場・過渡期）

> 通用守則（開工儀式、完成三級定義、紅線、commit 慣例）在全域 `~/.claude/CLAUDE.md`，先讀它。
> 跨 repo SOP 在 `C:\repo\linkou-toolbox\docs\`（DEPLOY／CHECKLIST／DATA-UPDATE／DECISIONS）。

## 1. 這個 repo 的身分（先搞清楚再動手）

- 這裡是「林口置產工具箱」整站的**開發主場**，但只到 **2026 年 7 月底收斂**為止；之後開發直接移到 `C:\repo\linkou-toolbox`，本 repo 退役為歷史檔庫。
- ⚠ **remote 名稱陷阱**：remote 叫 `linkou-school-zone`，但那只是歷史沿革。日常開發一律在 **`dev` 分支**。
- ⚠ **master 不是 dev 的上游**：`master` 是「學區獨立站」的單檔部署版（只有 3 個檔、CSS inline），與 dev 結構不同、歷史分叉。**不要自行 push master、不要自行 cherry-pick**——學區獨立站已停止內容更新（7 月底改跳轉頁）。
- 改動要上線 = 同步到 linkou-toolbox，照 `docs/DEPLOY.md` 第 2 節，用 `tools/sync-toolbox.ps1`。

## 2. 檔案結構

```
index.html          整合站首頁（工具卡＋導覽）
school/index.html   學區快查（邏輯）   ←資料→ linkou-data.js（根目錄）
mortgage/index.html 房貸試算           ←資料→ mortgage-data.js
rent/index.html     租約產生器         ←資料→ rent/rent-data.js
bus/index.html      公車路線           ←資料→ bus-data.js ＋ linkou-data.js
style.css           全站共用樣式（:root CSS 變數＝設計系統）
tools/              開發工具：selftest.html（資料自檢）、sync-toolbox.ps1（同步）、fetch-bus.ps1
HANDOFF.md          租約產生器的交接筆記（做租約相關工作先讀）
reference/ price_data/ rent/reference/ tdx-secret.json  ← 本機資料，已 gitignore，永不 commit
```

## 3. 路由表：做某類事之前，先讀什麼

| 任務 | 先讀 |
|---|---|
| 新增/修改社區、學校、幼兒園等資料 | `linkou-toolbox/docs/DATA-UPDATE.md`（含物件對照與格式範例） |
| 改完要驗證 | `linkou-toolbox/docs/CHECKLIST.md` ＋ 開 `tools/selftest.html` |
| 要上線／同步到整合站 | `linkou-toolbox/docs/DEPLOY.md` 第 2 節 |
| 改租約產生器 | 本 repo `HANDOFF.md`（分批待辦與踩雷都在裡面） |
| 改房貸試算 | `mortgage-data.js` 地段數字是自動更新流入的，先讀 DEPLOY.md 第 3 節 |
| 115 學年學區切換 | `DATA-UPDATE.md` 第 4 節＋memory `linkou-115-switch-plan`（鐵則：沒有里鄰對照表不准動） |
| 關獨立站／收斂搬家 | `DEPLOY.md` 第 4 節 runbook |
| 不確定某事是否已有定論 | `linkou-toolbox/docs/DECISIONS.md` |

## 4. 核心原則

1. **資料與邏輯分離**：改資料只動 `*-data.js`，不碰各頁 `index.html`；能在資料檔解決的就不要改邏輯。
2. **純前端、零建置、無框架**：瀏覽器直接開 `file://` 即可執行，這是驗證的唯一方式（本機無 Node/Python）。不引入需要編譯打包的東西。
3. **設計系統**：沿用 `style.css` `:root` 變數（主色陶土橘 `--clay`、輔色墨綠 `--teal`、背景米色 `--bg`；標題 `--serif`＝Noto Serif TC、內文 `--sans`＝Noto Sans TC）與既有 class（`.panel` 卡片、`.btn` 按鈕、`.site-nav` 導覽）。不硬寫色碼、不另寫一套樣式。
4. **註解用繁體中文**，密度比照既有程式；新程式以可讀性優先，不刻意壓單行。慣用 `const $ = s => document.querySelector(s);`。
5. 核心演算法動前先讀懂：地址解析 `parseHouse`／`houseLookup`、里界判定 `liAtPoint`（點在多邊形內）。改壞這些＝整個學區工具查錯。

## 5. 本 repo 專屬紅線（全域紅線之外）

- `rent/reference/`（真實租約個資）、`reference/`（官方原始檔）、`price_data/`（430MB 實價原始檔）、`tdx-secret.json`（TDX 金鑰）、根目錄 `*.xlsx`（門牌原始檔）：**已 gitignore，永不 commit、內容不貼進會公開的檔案**。
- 頁尾營業員資訊、學區免責提醒（`.disc`）、租約法定條文：不刪、不改、不亂填。
- Nominatim 呼叫必須保留 350–900ms 節流。
- 學區資料改完必跑 `tools/selftest.html`；別忘了資料有三份複本要傳播（toolbox、LINE bot），見 `DATA-UPDATE.md` 第 2 節第 5 步。

## 6. 擴充新工具時

1. 沿用設計系統與導覽列；資料獨立成自己的 `xxx-data.js`。
2. 核心計算寫成**不碰畫面的純函式**（未來可能接 LINE bot 重用，比照 `school-logic.js` 的做法）。
3. 試算類工具把公式寫清楚＋中文註解＋標註資料/稅率的年度與來源。
4. 每完成一個階段就 commit（commit 即存檔，小事不必另寫 md；多步驟計畫與踩雷才寫 HANDOFF）。
