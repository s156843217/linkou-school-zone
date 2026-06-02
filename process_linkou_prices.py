# -*- coding: utf-8 -*-
"""
process_linkou_prices.py
========================
一鍵完成：
  1. 讀取 f_lvr_land_a.xml（115Q1 新北市實價登錄）
  2. 過濾林口區住宅買賣
  3. 清理資料（扣車位、算屋齡、去極端值）
  4. 取各路名代表地址，呼叫 NLSC 地理編碼 API 取經緯度
  5. 用射線法判斷每筆交易屬於哪個商圈（林口價格地圖.geojson）
  6. 計算各商圈「每坪單價」中位數、區間、樣本數
  7. 輸出可貼入 mortgage-data.js 的 JS 資料

執行方式：
  python process_linkou_prices.py

需要套件：pandas、requests
  pip install pandas requests
"""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import requests

# ── 路徑設定 ──────────────────────────────────────────────
XML_PATH = Path("price_data/extracted/f_lvr_land_a.xml")
GEOJSON_PATH = Path("price_data/林口價格地圖.geojson")

# ── 常數 ──────────────────────────────────────────────────
PING_M2 = 3.305785
TARGET_DISTRICT = "林口區"
RESIDENTIAL_USES = {"住家用", "住商用"}
SPECIAL_DEAL_KEYWORDS = [
    "親友", "二親等", "特殊關係", "急售", "債務", "拍賣", "法拍",
    "贈與", "含增建", "毛胚", "含裝潢", "含傢俱", "含家具", "瑕疵",
]

# ── 1. 讀取 XML ───────────────────────────────────────────

def load_xml(path: Path) -> pd.DataFrame:
    """把 XML 每個 <買賣> 節點轉成一列，欄名就是子標籤名稱。"""
    print(f"讀取 {path} ...")
    tree = ET.parse(path)
    root = tree.getroot()
    rows = []
    for record in root.findall("買賣"):
        row = {child.tag: (child.text or "").strip() for child in record}
        rows.append(row)
    df = pd.DataFrame(rows)
    print(f"  共 {len(df)} 筆（全新北市）")
    return df


# ── 2. 清理 ───────────────────────────────────────────────

def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def _roc_year(s: pd.Series) -> pd.Series:
    v = s.astype(str).str.strip()
    return pd.to_numeric(v.where(v.str.len() >= 5).str[:-4], errors="coerce")

def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 只留林口
    df = df[df.get("鄉鎮市區", pd.Series(dtype=str)).astype(str).str.contains(TARGET_DISTRICT, na=False)]
    # 只留含建物的房地
    df = df[df.get("交易標的", pd.Series(dtype=str)).astype(str).str.contains("建物", na=False)]
    # 只留住宅
    df = df[df.get("主要用途", pd.Series(dtype=str)).astype(str).isin(RESIDENTIAL_USES) |
            df.get("主要用途", pd.Series(dtype=str)).isna()]

    if len(df) == 0:
        print("  ⚠️  過濾後無資料！")
        return df

    # 數值轉型
    for c in ["總價元", "建物移轉總面積平方公尺", "車位總價元", "車位移轉總面積平方公尺",
              "主建物面積", "建物現況格局-房", "建築完成年月", "交易年月日"]:
        if c in df.columns:
            df[c] = _to_num(df[c])

    # 屋齡
    df["交易民國年"] = _roc_year(df["交易年月日"].astype(str))
    df["建築民國年"] = _roc_year(df.get("建築完成年月", pd.Series(dtype=str)).astype(str))
    df["屋齡"] = df["交易民國年"] - df["建築民國年"]
    df.loc[df["屋齡"] < 0, "屋齡"] = pd.NA

    # 不含車位單價（萬/坪）
    車位價 = df.get("車位總價元", pd.Series(0, index=df.index)).fillna(0)
    車位面積 = df.get("車位移轉總面積平方公尺", pd.Series(0, index=df.index)).fillna(0)
    房屋總價 = _to_num(df["總價元"]) - 車位價
    房屋面積_坪 = (_to_num(df["建物移轉總面積平方公尺"]) - 車位面積) / PING_M2
    df["房屋面積_坪"] = 房屋面積_坪
    df["不含車位單價_萬每坪"] = (房屋總價 / 10000) / 房屋面積_坪
    df.loc[房屋面積_坪 <= 0, "不含車位單價_萬每坪"] = pd.NA
    df = df[df["不含車位單價_萬每坪"].notna()]

    # 備註特殊交易
    if "備註" in df.columns:
        pat = "|".join(SPECIAL_DEAL_KEYWORDS)
        df = df[~df["備註"].astype(str).str.contains(pat, na=False)]

    # 去極端值
    if len(df) > 20:
        lo = df["不含車位單價_萬每坪"].quantile(0.01)
        hi = df["不含車位單價_萬每坪"].quantile(0.99)
        df = df[df["不含車位單價_萬每坪"].between(lo, hi)]

    df = df.reset_index(drop=True)
    print(f"  林口住宅清理後：{len(df)} 筆")
    return df


# ── 3. 地理編碼（NLSC 國土測繪中心） ─────────────────────

def geocode_nlsc(address: str, retries: int = 3) -> tuple[float, float] | None:
    """
    呼叫國土測繪中心地理編碼 API。
    回傳 (lng, lat) 或 None（查無結果）。
    API 文件：https://geocode.nlsc.gov.tw/
    """
    url = "https://geocode.nlsc.gov.tw/query"
    params = {"number": address, "type": "", "format": "1", "lang": "zh"}
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            # 回傳格式：{"status":"0","suggest":[{"x":"121.38...","y":"25.07..."},...]}
            suggest = data.get("suggest") or []
            if suggest:
                x = float(suggest[0]["x"])
                y = float(suggest[0]["y"])
                return (x, y)   # (lng, lat)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                print(f"    geocode 失敗({address}): {e}")
    return None


def extract_street(addr: str) -> str:
    """從門牌字串取出「路/街/段」層級（用於聚合代表地址）。"""
    import re
    # 取出「XX路N段」或「XX街」，捨棄門號
    m = re.search(r"([一-鿿]+(?:路|街|道|大道)(?:[一-鿿]*段)?)", addr)
    if m:
        return m.group(1)
    return addr[:10]  # 兜底


def geocode_all_streets(df: pd.DataFrame) -> dict[str, tuple[float, float] | None]:
    """
    取每條路名的第一筆門牌，呼叫地理編碼 API 取座標。
    回傳 {路名: (lng, lat)}。
    """
    addr_col = "土地位置建物門牌"
    if addr_col not in df.columns:
        print(f"  ⚠️  找不到欄位 {addr_col}")
        return {}

    df = df.copy()
    df["路名"] = df[addr_col].astype(str).apply(extract_street)

    # 每條路取第一筆完整門牌
    first_addrs = (
        df.groupby("路名")[addr_col]
        .first()
        .reset_index()
        .rename(columns={addr_col: "代表門牌"})
    )

    coords: dict[str, tuple[float, float] | None] = {}
    total = len(first_addrs)
    print(f"\n地理編碼 {total} 條路名（每條間隔 1.2 秒）...")
    for i, row in first_addrs.iterrows():
        road = row["路名"]
        addr = row["代表門牌"]
        # 確保地址包含完整縣市
        if "新北市" not in addr:
            addr = "新北市林口區" + addr
        result = geocode_nlsc(addr)
        coords[road] = result
        status = f"({result[0]:.5f}, {result[1]:.5f})" if result else "查無結果"
        print(f"  [{i+1}/{total}] {road}  {status}")
        time.sleep(1.2)

    return coords


# ── 4. 商圈分配（點在多邊形） ─────────────────────────────

def load_zones(geojson_path: Path) -> list[dict]:
    """載入 GeoJSON，回傳有 Polygon 的 Feature 清單（排除 Point）。"""
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    zones = []
    for feat in gj.get("features", []):
        if feat["geometry"]["type"] == "Polygon":
            zones.append({
                "name": feat["properties"].get("name", "未命名"),
                "coords": feat["geometry"]["coordinates"][0],  # 外環
            })
    return zones


def point_in_polygon(lng: float, lat: float, polygon: list) -> bool:
    """射線法：判斷點 (lng, lat) 是否在多邊形內。"""
    x, y = lng, lat
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def assign_zone(lng: float, lat: float, zones: list[dict]) -> str:
    """回傳點所在的商圈名稱；找不到則回傳 '其他'。"""
    for zone in zones:
        if point_in_polygon(lng, lat, zone["coords"]):
            return zone["name"]
    return "其他"


# ── 5. 主流程 ─────────────────────────────────────────────

def main():
    # 1. 讀取並清理
    df_raw = load_xml(XML_PATH)
    df = clean(df_raw)
    if len(df) == 0:
        print("無資料可分析。")
        return

    # 2. 地理編碼
    road_coords = geocode_all_streets(df)

    # 把路名和座標加回 df
    df["路名"] = df["土地位置建物門牌"].astype(str).apply(extract_street)
    df["lng"] = df["路名"].map(lambda r: road_coords.get(r, (None, None))[0]
                               if road_coords.get(r) else None)
    df["lat"] = df["路名"].map(lambda r: road_coords.get(r, (None, None))[1]
                               if road_coords.get(r) else None)

    # 3. 商圈分配
    zones = load_zones(GEOJSON_PATH)
    print(f"\n載入 {len(zones)} 個商圈：{[z['name'] for z in zones]}")

    def _assign(row):
        if pd.isna(row["lng"]) or pd.isna(row["lat"]):
            return "其他"
        return assign_zone(row["lng"], row["lat"], zones)

    df["商圈"] = df.apply(_assign, axis=1)
    print(f"\n商圈分配結果：\n{df['商圈'].value_counts().to_string()}")

    # 4. 各商圈統計
    print("\n=== 各商圈每坪單價統計 ===")
    stats = {}
    for zone_name, group in df[df["商圈"] != "其他"].groupby("商圈"):
        prices = group["不含車位單價_萬每坪"].dropna()
        if len(prices) < 3:
            continue
        med = round(float(prices.median()), 1)
        lo = round(float(prices.quantile(0.25)), 1)
        hi = round(float(prices.quantile(0.75)), 1)
        stats[zone_name] = {
            "中位數": med,
            "Q1": lo,
            "Q3": hi,
            "樣本數": len(prices),
        }
        print(f"  {zone_name:10s}  中位數={med:5.1f}  IQR=[{lo},{hi}]  n={len(prices)}")

    # 5. 輸出 JS 片段
    print("\n=== 可貼入 mortgage-data.js 的 LINKOU_ZONES ===\n")
    print("const LINKOU_ZONES = [")
    zone_order = ["三井Outlet", "麗園國小", "家樂福商圈", "南勢", "北側", "林口舊市區"]
    for name in zone_order:
        if name not in stats:
            continue
        s = stats[name]
        line = (
            f'  {{ name: "{name}", '
            f'medPrice: {s["中位數"]}, '
            f'priceRange: [{s["Q1"]}, {s["Q3"]}], '
            f'count: {s["樣本數"]} }},'
        )
        print(line)
    print("];")

    # 額外：儲存完整 CSV 供核對
    out_csv = Path("price_data/linkou_clean.csv")
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\n完整清理後資料已存至 {out_csv}")


if __name__ == "__main__":
    main()
