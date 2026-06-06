# extract_roads2.ps1 — 以 ChildNodes 走訪 XML，列出林口各路名單價統計（extract_roads.ps1 的精簡版）
$XmlPath = "price_data\extracted\f_lvr_land_a.xml"
Write-Host "讀取 $XmlPath ..."
$content = [System.IO.File]::ReadAllText((Resolve-Path $XmlPath), [System.Text.Encoding]::UTF8)
[xml]$xml = $content
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
    $road = if ($roadMatch.Success) { $roadMatch.Value } else { if ($addr.Length -gt 12) { $addr.Substring(0,12) } else { $addr } }
    $records += [PSCustomObject]@{ 門牌=$addr; 路名=$road; 單價=[Math]::Round($unitPrice,2); 面積坪=[Math]::Round($netPing,1); 總價萬=[Math]::Round($tp/10000,0) }
}
Write-Host "林口住宅清理後：$($records.Count) 筆"
$grouped = $records | Group-Object 路名 | Sort-Object Count -Descending
Write-Host ("{0,-22} {1,5} {2,7} {3,7} {4,7}" -f "路名","筆數","中位數","Q1","Q3")
Write-Host ("-" * 55)
foreach ($g in $grouped) {
    $prices = ($g.Group | ForEach-Object { $_.單價 }) | Sort-Object
    $n = $prices.Count
    $med = $prices[[Math]::Floor($n/2)]
    $q1  = $prices[[Math]::Floor($n/4)]
    $q3  = $prices[[Math]::Floor($n*3/4)]
    Write-Host ("{0,-22} {1,5} {2,7:F1} {3,7:F1} {4,7:F1}" -f $g.Name,$n,$med,$q1,$q3)
}
Write-Host "共 $($grouped.Count) 條路名"
Write-Host "`n=== 各路代表門牌 ==="
foreach ($g in $grouped) { Write-Host ("  {0,-20}: {1}" -f $g.Name, $g.Group[0].門牌) }
