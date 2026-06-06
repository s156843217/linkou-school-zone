# analyze_zones.ps1 — 依路名商圈對照表計算各商圈每坪單價統計
$XmlPath = "price_data\extracted\f_lvr_land_a.xml"
$MapPath = "road_zone_map.csv"

$content = [System.IO.File]::ReadAllText((Resolve-Path $XmlPath), [System.Text.Encoding]::UTF8)
[xml]$xml = $content

# 載入路名→商圈對照
$zoneMap = @{}
Import-Csv $MapPath -Encoding utf8 | ForEach-Object { $zoneMap[$_.路名] = $_.商圈 }
Write-Host "載入商圈對照：$($zoneMap.Count) 條路"

$PING_M2 = 3.305785
$records = @()

foreach ($item in $xml.lvr_land.ChildNodes) {
    $district = $item.SelectSingleNode("鄉鎮市區")
    if (-not $district -or $district.InnerText -ne "林口區") { continue }
    $target = $item.SelectSingleNode("交易標的")
    if (-not $target -or $target.InnerText -notmatch "建物") { continue }
    $usage = $item.SelectSingleNode("主要用途")
    $usageVal = if ($usage) { $usage.InnerText } else { "" }
    if ($usageVal -ne "" -and $usageVal -ne "住家用" -and $usageVal -ne "住商用") { continue }
    $note = $item.SelectSingleNode("備註")
    if ($note -and $note.InnerText -match "親友|急售|債務|拍賣|贈與|含裝潢|瑕疵") { continue }

    $tp = $ba = $pp = $pa = 0
    $n1 = $item.SelectSingleNode("總價元"); if ($n1) { try { $tp = [double]$n1.InnerText } catch {} }
    $n2 = $item.SelectSingleNode("建物移轉總面積平方公尺"); if ($n2) { try { $ba = [double]$n2.InnerText } catch {} }
    $n3 = $item.SelectSingleNode("車位總價元"); if ($n3) { try { $pp = [double]$n3.InnerText } catch {} }
    $n4 = $item.SelectSingleNode("車位移轉總面積平方公尺"); if ($n4) { try { $pa = [double]$n4.InnerText } catch {} }

    $netPing = ($ba - $pa) / $PING_M2
    if ($netPing -le 0) { continue }
    $unitPrice = (($tp - $pp) / 10000) / $netPing
    if ($unitPrice -le 3 -or $unitPrice -gt 300) { continue }

    $addrNode = $item.SelectSingleNode("土地位置建物門牌")
    $addr = if ($addrNode) { $addrNode.InnerText } else { "" }
    $roadMatch = [regex]::Match($addr, "([一-鿿]+(?:路|街|道|大道)(?:[一-鿿]*段)?)")
    $road = if ($roadMatch.Success) { "新北市林口區" + $roadMatch.Value } else { "" }
    $zone = if ($zoneMap.ContainsKey($road)) { $zoneMap[$road] } else { "其他" }

    # 屋齡
    $txYearNode = $item.SelectSingleNode("交易年月日")
    $bdYearNode = $item.SelectSingleNode("建築完成年月")
    $age = $null
    if ($txYearNode -and $bdYearNode) {
        $txY = if ($txYearNode.InnerText.Length -ge 5) { [int]$txYearNode.InnerText.Substring(0, $txYearNode.InnerText.Length - 4) } else { 0 }
        $bdY = if ($bdYearNode.InnerText.Length -ge 5) { [int]$bdYearNode.InnerText.Substring(0, $bdYearNode.InnerText.Length - 4) } else { 0 }
        if ($txY -gt 0 -and $bdY -gt 0 -and $txY -ge $bdY) { $age = $txY - $bdY }
    }

    $rooms = 0
    $rNode = $item.SelectSingleNode("建物現況格局-房"); if ($rNode) { try { $rooms = [int]$rNode.InnerText } catch {} }

    $records += [PSCustomObject]@{
        路名   = $road
        商圈   = $zone
        單價   = [Math]::Round($unitPrice, 2)
        面積坪 = [Math]::Round($netPing, 1)
        總價萬 = [Math]::Round($tp / 10000, 0)
        屋齡   = $age
        房數   = $rooms
    }
}

Write-Host "林口住宅清理後：$($records.Count) 筆"
Write-Host ""

# 各商圈統計
$zoneOrder = @("三井Outlet","南勢","家樂福商圈","北側","林口舊市區","麗園國小")
Write-Host ("=" * 70)
Write-Host ("{0,-12} {1,5} {2,7} {3,7} {4,7} {5,6} {6,6}" -f "商圈","筆數","單價中位","Q1","Q3","屋齡","房數")
Write-Host ("=" * 70)

$results = @{}
foreach ($zoneName in $zoneOrder) {
    $grp = $records | Where-Object { $_.商圈 -eq $zoneName }
    if (-not $grp -or $grp.Count -eq 0) {
        Write-Host ("{0,-12} 無資料" -f $zoneName)
        continue
    }
    $prices = ($grp | ForEach-Object { $_.單價 }) | Sort-Object
    $n = $prices.Count
    $med = $prices[[Math]::Floor($n/2)]
    $q1  = $prices[[Math]::Floor($n/4)]
    $q3  = $prices[[Math]::Floor($n*3/4)]
    $ages  = ($grp | Where-Object { $_.屋齡 -ne $null } | ForEach-Object { $_.屋齡 }) | Sort-Object
    $ageMed = if ($ages.Count -gt 0) { $ages[[Math]::Floor($ages.Count/2)] } else { "?" }
    $roomsSorted = ($grp | Where-Object { $_.房數 -gt 0 } | ForEach-Object { $_.房數 }) | Sort-Object
    $roomMed = if ($roomsSorted.Count -gt 0) { $roomsSorted[[Math]::Floor($roomsSorted.Count/2)] } else { "?" }
    Write-Host ("{0,-12} {1,5} {2,7:F1} {3,7:F1} {4,7:F1} {5,6} {6,6}" -f $zoneName,$n,$med,$q1,$q3,$ageMed,$roomMed)
    $results[$zoneName] = [PSCustomObject]@{ n=$n; med=$med; q1=$q1; q3=$q3; ageMed=$ageMed; roomMed=$roomMed }
}

Write-Host ""
Write-Host "=== 可貼入 mortgage-data.js 的 LINKOU_ZONES ==="
Write-Host ""
Write-Host "const LINKOU_ZONES = ["
foreach ($zoneName in $zoneOrder) {
    if (-not $results.ContainsKey($zoneName)) { continue }
    $r = $results[$zoneName]
    Write-Host ("  {{ name: `"{0}`", medPrice: {1}, priceRange: [{2}, {3}], count: {4} }}," -f $zoneName,$r.med,$r.q1,$r.q3,$r.n)
}
Write-Host "];"

# 其他（未分配）
$other = $records | Where-Object { $_.商圈 -eq "其他" }
Write-Host ""
Write-Host "未分配路名：$($other.Count) 筆"
if ($other.Count -gt 0) {
    $other | Group-Object 路名 | Sort-Object Count -Desc | Select-Object -First 10 | ForEach-Object {
        Write-Host "  $($_.Name): $($_.Count) 筆"
    }
}
