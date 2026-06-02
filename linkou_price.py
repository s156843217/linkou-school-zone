# -*- coding: utf-8 -*-
"""
林口不動產實價登錄分析模組
================================================================

用途
----
讀取「不動產實價登錄(買賣案件)」資料,清理後做兩件事:
  1. build_price_table() : 算出各「建物型態 × 屋齡級距」的單價中位數,
                           產生一張可餵給反推邏輯的「單價表」。
  2. summarize_by_budget(): 反過來看「某個總價區間,實際成交的房型/屋齡/坪數分布」。
  3. what_can_i_buy()     : 用單價表反推「某預算大概能買到多大、幾房」。

資料來源(兩種,擇一)
----------------------
A. 新北市資料開放平臺(當前滾動快照,欄位已是中文,可直接抓林口子集)
   https://data.ntpc.gov.tw/datasets/ACCE802D-58CC-4DFF-9E7A-9ECC517F78BE
   在頁面點「CSV」或「JSON」鈕即可取得實際 API 連結;或去 OpenAPI 頁拿端點。
   優點:省事、欄位中文、可單獨抓林口區。缺點:不保證留長期歷史。

B. 內政部不動產成交案件季度檔(全國定版歷史,可回溯多年)
   https://plvr.land.moi.gov.tw/DownloadSeason?season=113S3&type=zip&fileName=lvr_landxml.zip
   解壓後挑新北買賣檔(類似 f_lvr_land_a.csv),注意有「雙表頭」(第一列中文、
   第二列英文),本模組的 load_csv() 會自動偵測並丟掉英文那列。

兩個來源的欄位名稱一致,皆為下方 COLUMNS 所列的中文欄名。

欄位對照(實價登錄原始中文欄名 → 意義)
----------------------------------------
鄉鎮市區、交易標的、土地區段位置建物區段門牌、土地移轉總面積平方公尺、
交易年月日(民國 YYYMMDD)、移轉層次、總樓層數、建物型態、主要用途、主要建材、
建築完成年月(民國 YYYMMDD)、建物移轉總面積平方公尺、
建物現況格局-房 / -廳 / -衛(直接就是房數,不必從坪數猜)、
總價元、單價元平方公尺、車位類別、車位移轉總面積平方公尺、車位總價元、備註、
主建物面積、附屬建物面積、陽台面積、電梯。

實價登錄三個一定要處理的坑(都在 clean() 裡)
------------------------------------------------
  1. 車位混在總價/面積裡會稀釋單價 → 先扣掉車位再算單價。
  2. 日期是民國年(如 1130315)→ 轉成年份才能算屋齡。
  3. 特殊交易(親友、急售、含裝潢…)是極端值 → 依備註關鍵字過濾;單價取中位數。

需要套件: pandas、requests(只有用 API 來源時才需要 requests)
執行方式: python linkou_price.py  (會跑最底下的範例)
"""

from __future__ import annotations

import pandas as pd

# ============================================================
# 設定 (CONFIG) — 要調整邏輯時改這裡就好
# ============================================================

PING_M2 = 3.305785  # 1 坪 = 3.305785 平方公尺

TARGET_DISTRICT = "林口區"          # 只分析這一區
RESIDENTIAL_USES = ["住家用", "住商用"]  # 只看住宅,排除純商辦/工業

# 屋齡級距:(下限含, 上限不含, 標籤)。要切更細就改這裡。
AGE_BINS = [
    (0, 5, "5年內"),
    (5, 15, "5-15年"),
    (15, 30, "15-30年"),
    (30, 1000, "30年以上"),
]

# 備註裡出現這些字,視為「非正常交易」剔除(會稀釋或灌水單價)。
# 偏保守,想更嚴格自行增減。
SPECIAL_DEAL_KEYWORDS = [
    "親友", "二親等", "特殊關係", "急售", "債務", "拍賣", "法拍",
    "贈與", "含增建", "毛胚", "含裝潢", "含傢俱", "含家具", "瑕疵",
]

# 坪數 → 房數 的模糊對照(僅供「預測」用;有實際格局欄位時請直接用格局)
def ping_to_rooms(ping: float) -> str:
    """依坪數粗估房數。注意這是模糊對照、會重疊,只在沒有格局資料時使用。"""
    if pd.isna(ping):
        return "未知"
    if ping < 18:
        return "套房/1房"
    if ping < 25:
        return "2房"
    if ping < 35:
        return "3房"
    return "4房以上"


# ============================================================
# 1. 讀取
# ============================================================

def load_csv(path: str) -> pd.DataFrame:
    """
    從 CSV 讀進實價登錄資料,自動處理「雙表頭」。

    內政部季度檔的 CSV 第一列是中文欄名、第二列是英文欄名;
    新北 open data 的 CSV 通常只有中文單表頭。本函式都能處理:
    讀進來後若第一筆資料的「交易年月日」不是數字(代表那是英文表頭),就丟掉它。
    """
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    if len(df) > 0 and "交易年月日" in df.columns:
        first = str(df.iloc[0]["交易年月日"]).strip()
        if not first.replace(".", "").isdigit():
            df = df.iloc[1:].reset_index(drop=True)
    return df


def load_from_api(url: str, timeout: int = 30) -> pd.DataFrame:
    """
    從新北 open data 的 JSON API 讀資料。

    url 請從資料集頁面的「JSON」鈕複製(或 OpenAPI 頁)。
    回應格式各平台略有差異:這裡假設回傳的是 list[dict],
    若平台有分頁(page/size),請依實際回應在外層自行迴圈累加。
    """
    import requests  # 只有走 API 才需要

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):  # 有些平台包一層,例如 {"result": [...]}
        for key in ("result", "data", "records", "items"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
    return pd.DataFrame(data)


# ============================================================
# 2. 清理
# ============================================================

def _to_number(series: pd.Series) -> pd.Series:
    """把字串欄位轉成數字,轉不動的變 NaN(不會炸)。"""
    return pd.to_numeric(series, errors="coerce")


def _roc_year(series: pd.Series) -> pd.Series:
    """
    從民國 YYYMMDD 取出『民國年』。
    例: '1130315' → 113;'0901201' → 90。空值或格式怪的回 NaN。
    (算屋齡只需要年,民國年相減 = 西元年相減,所以不用換算西元。)
    """
    s = series.astype(str).str.strip()
    # 取掉最後 4 碼(月日),剩下的就是民國年
    year = s.where(s.str.len() >= 5).str[:-4]
    return pd.to_numeric(year, errors="coerce")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    完整清理流程,回傳新增了下列欄位的 DataFrame:
      屋齡、不含車位單價_萬每坪、主建物坪、房數
    並已過濾掉:非林口、非住宅、非房地交易、特殊交易、單價異常值。
    """
    df = df.copy()

    # --- 數值欄位轉型 ---
    num_cols = [
        "總價元", "單價元平方公尺", "建物移轉總面積平方公尺",
        "車位總價元", "車位移轉總面積平方公尺",
        "主建物面積", "建物現況格局-房",
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = _to_number(df[c])

    # --- 民國年 → 屋齡 ---
    df["交易民國年"] = _roc_year(df["交易年月日"])
    df["建築民國年"] = _roc_year(df["建築完成年月"])
    df["屋齡"] = df["交易民國年"] - df["建築民國年"]
    df.loc[df["屋齡"] < 0, "屋齡"] = pd.NA  # 資料怪的(交易早於完工)剔除

    # --- 扣掉車位,算「不含車位單價」(萬/坪) ---
    車位價 = df.get("車位總價元", 0).fillna(0) if "車位總價元" in df.columns else 0
    車位面積 = df.get("車位移轉總面積平方公尺", 0).fillna(0) if "車位移轉總面積平方公尺" in df.columns else 0
    房屋總價 = df["總價元"] - 車位價
    房屋面積_坪 = (df["建物移轉總面積平方公尺"] - 車位面積) / PING_M2
    df["房屋面積_坪"] = 房屋面積_坪
    df["不含車位單價_萬每坪"] = (房屋總價 / 10000) / 房屋面積_坪
    df.loc[房屋面積_坪 <= 0, "不含車位單價_萬每坪"] = pd.NA

    # --- 主建物(室內)坪數,給「室內單價」討論用 ---
    if "主建物面積" in df.columns:
        df["主建物坪"] = df["主建物面積"] / PING_M2

    # --- 房數:直接讀格局欄位,不用從坪數猜 ---
    if "建物現況格局-房" in df.columns:
        df["房數"] = df["建物現況格局-房"]

    # --- 正規化建物型態(方便分群) ---
    df["型態"] = df["建物型態"].apply(_normalize_building_type)

    # --- 屋齡級距標籤 ---
    df["屋齡級距"] = df["屋齡"].apply(_age_label)

    # --- 過濾 ---
    mask = pd.Series(True, index=df.index)
    if "鄉鎮市區" in df.columns:                       # 只留林口
        mask &= df["鄉鎮市區"].astype(str).str.contains(TARGET_DISTRICT, na=False)
    if "交易標的" in df.columns:                        # 只留含建物的房地交易
        mask &= df["交易標的"].astype(str).str.contains("建物", na=False)
    if "主要用途" in df.columns:                        # 只留住宅
        mask &= df["主要用途"].astype(str).isin(RESIDENTIAL_USES) | df["主要用途"].isna()
    if "備註" in df.columns:                            # 剔除特殊交易
        pattern = "|".join(SPECIAL_DEAL_KEYWORDS)
        mask &= ~df["備註"].astype(str).str.contains(pattern, na=False)
    mask &= df["不含車位單價_萬每坪"].notna()           # 單價算得出來才留

    df = df[mask].reset_index(drop=True)

    # --- 去極端值:單價落在 1%~99% 分位之外的剔除 ---
    if len(df) > 20:
        lo = df["不含車位單價_萬每坪"].quantile(0.01)
        hi = df["不含車位單價_萬每坪"].quantile(0.99)
        df = df[df["不含車位單價_萬每坪"].between(lo, hi)].reset_index(drop=True)

    return df


def _normalize_building_type(s) -> str:
    """把冗長的建物型態字串歸成幾大類。"""
    if pd.isna(s):
        return "其他"
    s = str(s)
    for key, label in [
        ("大樓", "住宅大樓"), ("華廈", "華廈"), ("公寓", "公寓"),
        ("套房", "套房"), ("透天", "透天厝"), ("店", "店面"),
    ]:
        if key in s:
            return label
    return "其他"


def _age_label(age) -> str:
    """把屋齡數字對到 AGE_BINS 的級距標籤。"""
    if pd.isna(age):
        return "未知"
    for lo, hi, label in AGE_BINS:
        if lo <= age < hi:
            return label
    return "未知"


# ============================================================
# 3. 分析
# ============================================================

def build_price_table(df: pd.DataFrame, min_count: int = 5) -> pd.DataFrame:
    """
    產生「單價表」:各(型態 × 屋齡級距)的單價中位數與樣本數。
    樣本數 < min_count 的組合會被標記(不夠可信),但仍保留供參考。

    回傳欄位: 型態、屋齡級距、單價中位數_萬每坪、樣本數、可信。
    """
    g = (
        df.groupby(["型態", "屋齡級距"])["不含車位單價_萬每坪"]
        .agg(["median", "count"])
        .reset_index()
        .rename(columns={"median": "單價中位數_萬每坪", "count": "樣本數"})
    )
    g["單價中位數_萬每坪"] = g["單價中位數_萬每坪"].round(2)
    g["可信"] = g["樣本數"] >= min_count
    return g.sort_values(["型態", "屋齡級距"]).reset_index(drop=True)


def price_table_to_dict(price_table: pd.DataFrame) -> dict:
    """
    把單價表轉成 {(型態, 屋齡級距): 單價} 的 dict,
    方便餵給 what_can_i_buy()。只收『可信』的組合。
    """
    out = {}
    for _, row in price_table.iterrows():
        if row["可信"]:
            out[(row["型態"], row["屋齡級距"])] = row["單價中位數_萬每坪"]
    return out


def summarize_by_budget(df: pd.DataFrame, low_wan: float, high_wan: float) -> dict:
    """
    反查:在 [low_wan, high_wan] 萬的總價區間,實際成交的房子長怎樣。
    回傳:筆數、屋齡中位數、坪數中位數、最常見房數、單價中位數。
    (總價欄位是「元」,所以乘以 10000 換成萬比較。)
    """
    total_wan = df["總價元"] / 10000
    sub = df[total_wan.between(low_wan, high_wan)]
    if len(sub) == 0:
        return {"預算區間": (low_wan, high_wan), "筆數": 0}

    rooms_mode = sub["房數"].mode()
    return {
        "預算區間": (low_wan, high_wan),
        "筆數": int(len(sub)),
        "屋齡中位數": round(float(sub["屋齡"].median()), 1),
        "坪數中位數": round(float(sub["房屋面積_坪"].median()), 1),
        "最常見房數": (int(rooms_mode.iloc[0]) if len(rooms_mode) else None),
        "單價中位數_萬每坪": round(float(sub["不含車位單價_萬每坪"].median()), 2),
    }


# ============================================================
# 4. 反推 (接你前面那套「預算 → 坪數 → 房型」)
# ============================================================

def what_can_i_buy(price_table: dict, budget_low: float, budget_high: float) -> list[dict]:
    """
    用單價表反推:這個預算(萬)在各型態/屋齡下大概能買多大、幾房。
    price_table: price_table_to_dict() 產生的 {(型態,屋齡): 單價}。
    """
    results = []
    for (型態, 屋齡), 單價 in price_table.items():
        坪_下 = budget_low / 單價
        坪_上 = budget_high / 單價
        results.append({
            "型態": 型態,
            "屋齡": 屋齡,
            "單價_萬每坪": 單價,
            "坪數範圍": (round(坪_下, 1), round(坪_上, 1)),
            "房型範圍": (ping_to_rooms(坪_下), ping_to_rooms(坪_上)),
        })
    return results


# ============================================================
# 範例 (直接 python linkou_price.py 會跑這段)
# ============================================================

def main():
    # 來源 A(新北 API):把下面網址換成你從資料集頁「JSON」鈕複製的連結
    # df = load_from_api("https://data.ntpc.gov.tw/api/.../json")
    #
    # 來源 B(內政部季度檔解壓後的 CSV):
    # df = load_csv("f_lvr_land_a.csv")

    df = load_csv("林口實價登錄.csv")   # ← 換成你的檔
    df = clean(df)
    print(f"清理後可用筆數:{len(df)}\n")

    print("=== 單價表(型態 × 屋齡級距)===")
    table = build_price_table(df)
    print(table.to_string(index=False))

    print("\n=== 1000 萬以下實際成交分布 ===")
    print(summarize_by_budget(df, 0, 1000))

    print("\n=== 1000~1500 萬實際成交分布 ===")
    print(summarize_by_budget(df, 1000, 1500))

    print("\n=== 用單價表反推:1000~1500 萬買得到什麼 ===")
    for row in what_can_i_buy(price_table_to_dict(table), 1000, 1500):
        print(row)


if __name__ == "__main__":
    main()
