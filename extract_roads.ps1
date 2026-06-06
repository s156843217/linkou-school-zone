# extract_roads.ps1 — 從 XML 提取林口買賣記錄並列出路名統計

param(
    [string]$XmlPath = "price_data\extracted\f_lvr_land_a.xml"
)

Write-Host "讀取 $XmlPath ..."

[xml]$xml = Get-Content $XmlPath -Encoding UTF8

$PING_M2 = 3.305785
$TARGET = "林口區"
$SPECIAL_KW = "親友|二親等|特殊關係|急售|債務|拍賣|法拍|贈與|含增建|毛胚|含裝潢|含傢俱|含家具|瑕疵"

$records = @()

foreach ($item in $xml.lvr_land.買賣) {
    # 只留林口
    if ($item.鄉鎮市區 -ne $TARGET) { continue }

    # 只留含建物的交易
    if ($item.交易標的 -notmatch "建物") { continue }

    # 只留住宅
    $usage = $item.主要用途
    if ($usage -and $usage -ne "" -and $usage -ne "住家用" -and $usage -ne "住商用") { continue }

    # 剔除特殊交易
    if ($item.備註 -match $SPECIAL_KW) { continue }

    # 數值
    $totalPrice = [double]($item.總價元 -replace "[^0-9.]","")
    $buildArea  = [double]($item.建物移轉總面積平方公尺 -replace "[^0-9.]","")
    $parkPrice  = if ($item.車位總價元 -match "^\d") { [double]$item.車位總價元 } else { 0 }
    $parkArea   = if ($item.車位移轉總面積平方公尺 -match "^\d") { [double]$item.車位移轉總面積平方公尺 } else { 0 }

    $netArea_ping = ($buildArea - $parkArea) / $PING_M2
    if ($netArea_ping -le 0) { continue }

    $unitPrice = (($totalPrice - $parkPrice) / 10000) / $netArea_ping
    if ($unitPrice -le 0 -or $unitPrice -gt 300) { continue }  # 去極端

    # 門牌 → 路名（取到路/街/段）
    $addr = $item.土地位置建物門牌
    $roadMatch = [regex]::Match($addr, "([一-鿿]+(?:路|街|道|大道)(?:[一-鿿]*段)?)")
    $road = if ($roadMatch.Success) { $roadMatch.Value } else { $addr.Substring(0, [Math]::Min(10, $addr.Length)) }

    $records += [PSCustomObject]@{
        門牌    = $addr
        路名    = $road
        總價萬  = [Math]::Round($totalPrice / 10000, 0)
        單價萬坪 = [Math]::Round($unitPrice, 2)
        面積坪  = [Math]::Round($netArea_ping, 1)
    }
}

Write-Host "林口住宅清理後：$($records.Count) 筆`n"

# 各路名統計
$grouped = $records | Group-Object 路名 | Sort-Object Count -Descending

Write-Host ("=" * 65)
Write-Host ("{0,-20} {1,5} {2,8} {3,8} {4,8}" -f "路名","筆數","單價中位","單價Q1","單價Q3")
Write-Host ("=" * 65)

foreach ($g in $grouped) {
    $prices = $g.Group | ForEach-Object { $_.單價萬坪 } | Sort-Object
    $n = $prices.Count
    $med = $prices[[Math]::Floor($n / 2)]
    $q1  = $prices[[Math]::Floor($n / 4)]
    $q3  = $prices[[Math]::Floor($n * 3 / 4)]
    Write-Host ("{0,-20} {1,5} {2,8:F1} {3,8:F1} {4,8:F1}" -f $g.Name, $n, $med, $q1, $q3)
}

Write-Host "`n共 $($grouped.Count) 條路名"

# 同時輸出代表門牌（供手動核對地段）
Write-Host "`n=== 各路名代表門牌 ==="
foreach ($g in $grouped) {
    $sample = $g.Group[0].門牌
    Write-Host "  $($g.Name): $sample"
}
