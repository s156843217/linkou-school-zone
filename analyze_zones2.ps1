$XmlPath = "price_data\extracted\f_lvr_land_a.xml"
$MapPath = "road_zone_map.csv"

$content = [System.IO.File]::ReadAllText((Resolve-Path $XmlPath), [System.Text.Encoding]::UTF8)
[xml]$xml = $content

$zoneMap = @{}
Import-Csv $MapPath -Encoding utf8 | ForEach-Object { $zoneMap[$_.路名] = $_.商圈 }

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
    # 先去掉縣市區前綴再抓路名
    $addrClean = $addr -replace "^新北市林口區", ""
    $roadMatch = [regex]::Match($addrClean, "([一-鿿]+(?:路|街|道|大道)(?:[一-鿿]*段)?)")
    $road = if ($roadMatch.Success) { $roadMatch.Value } else { "" }
    $zone = if ($road -ne "" -and $zoneMap.ContainsKey($road)) { $zoneMap[$road] } else { "其他" }

    $txYearNode = $item.SelectSingleNode("交易年月日")
    $bdYearNode = $item.SelectSingleNode("建築完成年月")
    $age = $null
    if ($txYearNode -and $bdYearNode -and $txYearNode.InnerText.Length -ge 5 -and $bdYearNode.InnerText.Length -ge 5) {
        $txY = [int]$txYearNode.InnerText.Substring(0, $txYearNode.InnerText.Length - 4)
        $bdY = [int]$bdYearNode.InnerText.Substring(0, $bdYearNode.InnerText.Length - 4)
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

$zoneOrder = @("三井Outlet","南勢","家樂福商圈","北側","林口舊市區","麗園國小")
Write-Host ("{0,-12} {1,5} {2,7} {3,7} {4,7} {5,5} {6,5}" -f "商圈","筆數","中位數","Q1","Q3","屋齡","房數")
Write-Host ("-" * 60)

$results = [ordered]@{}
foreach ($zoneName in $zoneOrder) {
    $grp = @($records | Where-Object { $_.商圈 -eq $zoneName })
    if ($grp.Count -eq 0) { Write-Host ("{0,-12} 無資料" -f $zoneName); continue }
    $prices = ($grp | ForEach-Object { $_.單價 }) | Sort-Object
    $n = $prices.Count
    $med = [Math]::Round($prices[[Math]::Floor($n/2)], 1)
    $q1  = [Math]::Round($prices[[Math]::Floor($n/4)], 1)
    $q3  = [Math]::Round($prices[[Math]::Floor($n*3/4)], 1)
    $ages = @($grp | Where-Object { $_.屋齡 -ne $null } | ForEach-Object { $_.屋齡 }) | Sort-Object
    $ageMed = if ($ages.Count -gt 0) { $ages[[Math]::Floor($ages.Count/2)] } else { "?" }
    $rmList = @($grp | Where-Object { $_.房數 -gt 0 } | ForEach-Object { $_.房數 }) | Sort-Object
    $rmMed = if ($rmList.Count -gt 0) { $rmList[[Math]::Floor($rmList.Count/2)] } else { "?" }
    Write-Host ("{0,-12} {1,5} {2,7:F1} {3,7:F1} {4,7:F1} {5,5} {6,5}" -f $zoneName,$n,$med,$q1,$q3,$ageMed,$rmMed)
    $results[$zoneName] = @{ n=$n; med=$med; q1=$q1; q3=$q3; ageMed=$ageMed; rmMed=$rmMed }
}

Write-Host ""
Write-Host "=== JS 輸出 ==="
Write-Host "const LINKOU_ZONES = ["
foreach ($zoneName in $zoneOrder) {
    if (-not $results.ContainsKey($zoneName)) { continue }
    $r = $results[$zoneName]
    Write-Host ("  { name: `"$zoneName`", medPrice: $($r.med), priceRange: [$($r.q1), $($r.q3)], count: $($r.n), ageMed: $($r.ageMed), roomMed: $($r.rmMed) },")
}
Write-Host "];"

$other = @($records | Where-Object { $_.商圈 -eq "其他" })
if ($other.Count -gt 0) {
    Write-Host "`n未分配 $($other.Count) 筆 → 路名清單："
    $other | Group-Object 路名 | Sort-Object Count -Desc | Select-Object -First 10 | ForEach-Object {
        Write-Host "  $($_.Name): $($_.Count) 筆"
    }
}
