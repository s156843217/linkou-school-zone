# ============================================================
# sync-toolbox.ps1 — my-project(dev) → linkou-toolbox 同步工具
# ------------------------------------------------------------
# 用法：
#   powershell -NoProfile -File tools\sync-toolbox.ps1          ← 只看差異報告（安全，不改任何檔）
#   powershell -NoProfile -File tools\sync-toolbox.ps1 -Apply   ← 把差異檔複製到 toolbox（之後仍要自己 git commit/push）
#
# 原則：
#   * 白名單制——只碰下面列出的「網站檔」。CLAUDE.md、docs/、tools/、README、
#     個資資料夾（reference/ 等）永遠不會被同步。
#   * 只複製、不刪除。toolbox 端多出來的檔案只會被列出提醒，不會被動。
#   * 收斂（2026/7 底）後本腳本功成身退，開發直接在 toolbox 進行。
# ============================================================
param([switch]$Apply)

$src = "C:\repo\my-project"
$dst = "C:\repo\linkou-toolbox"

if (-not (Test-Path $src) -or -not (Test-Path $dst)) {
    Write-Host "找不到 $src 或 $dst，中止。" -ForegroundColor Red
    exit 1
}

# ---- 同步白名單（相對路徑；新網站檔上線時記得加進來）----
$files = @(
    "index.html",
    "style.css",
    "linkou-data.js",
    # mortgage-data.js 不在白名單：2026-07-03 起真相來源在 toolbox（每月 Actions 自動更新地段/三類行情），
    # 從 dev 蓋過去會弄丟新數字。要手改它請直接改 toolbox 那份，再複製回 dev。
    "bus-data.js",
    "school/index.html",
    "mortgage/index.html",
    "rent/index.html",
    "rent/rent-data.js",
    "bus/index.html",
    "report/index.html",
    "report/qrcode.js",
    "share/index.html",
    "report-logic.js",
    "internal-nav.js",
    "about/index.html"
)
# img/ 底下的圖片也同步，但排除開發用的 crop-tool.html
$imgFiles = Get-ChildItem -Path (Join-Path $src "img") -Recurse -File |
    Where-Object { $_.Name -ne "crop-tool.html" } |
    ForEach-Object { "img/" + $_.FullName.Substring((Join-Path $src "img").Length + 1).Replace("\", "/") }
$files = $files + $imgFiles

$diff = @(); $missing = @(); $sameCount = 0

foreach ($f in $files) {
    $a = Join-Path $src $f
    $b = Join-Path $dst $f
    if (-not (Test-Path $a)) { Write-Host "[白名單失效] dev 端沒有 $f（檔案改名了？請更新本腳本白名單）" -ForegroundColor Yellow; continue }
    if (-not (Test-Path $b)) { $missing += $f; continue }
    $ha = (Get-FileHash $a -Algorithm SHA256).Hash
    $hb = (Get-FileHash $b -Algorithm SHA256).Hash
    if ($ha -eq $hb) { $sameCount++ } else { $diff += $f }
}

Write-Host ""
Write-Host "===== 同步差異報告（dev → toolbox）====="
Write-Host ("相同：{0} 檔" -f $sameCount) -ForegroundColor Green
foreach ($f in $diff)    { Write-Host ("內容不同：{0}" -f $f) -ForegroundColor Yellow }
foreach ($f in $missing) { Write-Host ("toolbox 缺少：{0}" -f $f) -ForegroundColor Yellow }
if (($diff.Count + $missing.Count) -eq 0) {
    Write-Host ""; Write-Host "兩邊一致，不需要同步。" -ForegroundColor Green
    exit 0
}

if (-not $Apply) {
    Write-Host ""
    Write-Host "以上僅為報告。每筆差異都應該能對上 dev 的某個 commit；"
    Write-Host "確認無誤後加 -Apply 執行複製。"
    exit 0
}

# ---- 套用 ----
Write-Host ""; Write-Host "===== 開始複製 ====="
foreach ($f in ($diff + $missing)) {
    $a = Join-Path $src $f
    $b = Join-Path $dst $f
    $bdir = Split-Path $b -Parent
    if (-not (Test-Path $bdir)) { New-Item -ItemType Directory -Force $bdir | Out-Null }
    Copy-Item $a $b -Force
    Write-Host ("已複製 {0}" -f $f)
}
Write-Host ""
Write-Host "複製完成。接下來（照 docs/DEPLOY.md 第 2 節）：" -ForegroundColor Cyan
Write-Host "  1. cd C:\repo\linkou-toolbox"
Write-Host "  2. git diff        ← 肉眼再確認一次"
Write-Host "  3. git add -A ; git commit -m ""(沿用 dev 的 commit 訊息)"" ; git push"
Write-Host "  4. 一分鐘後開 https://swcasa.com/ 驗證"
