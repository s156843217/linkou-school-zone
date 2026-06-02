/* mortgage-data.js — 房貸試算頁資料
   資料來源：內政部實價登錄 115 年第一季（買賣成交，林口區住宅，561 筆）
   依路名對照商圈後統計，單價單位：萬元／坪（不含車位）
*/

// ── 林口各商圈每坪單價（115Q1 實價登錄） ──────────────────
// medPrice：中位數（萬/坪）
// priceRange：[Q1, Q3]（25%～75% 分位）
// ageMed：成交屋齡中位數（年）
// roomMed：成交房數中位數
const LINKOU_ZONES = [
  { name: "三井Outlet",  medPrice: 57.5, priceRange: [48.3, 70.1], count: 32,  ageMed: 13, roomMed: 3 },
  { name: "南勢",        medPrice: 54.2, priceRange: [46.5, 57.8], count: 31,  ageMed:  7, roomMed: 3 },
  { name: "家樂福商圈",  medPrice: 48.2, priceRange: [45.3, 54.8], count: 180, ageMed: 11, roomMed: 3 },
  { name: "北側",        medPrice: 57.0, priceRange: [54.1, 59.6], count: 14,  ageMed:  4, roomMed: 2 },
  { name: "林口舊市區",  medPrice: 65.5, priceRange: [57.3, 67.1], count: 135, ageMed: 11, roomMed: 2 },
  { name: "麗園國小",    medPrice: 44.0, priceRange: [42.4, 46.2], count: 169, ageMed: 25, roomMed: 3 },
];

// ── 林口各總價區間對應房產類型（供試算結果快速提示用） ───────
// 格式：{ min, max, label, summary }
const LINKOU_PRODUCTS = [
  {
    min: 0, max: 1000,
    label: "1,000 萬以下",
    summary: "老市區公寓或套房為主・屋齡約 36 年・約 22 坪・1 房",
  },
  {
    min: 1000, max: 1400,
    label: "1,000–1,400 萬",
    summary: "中古華廈或住宅大樓・屋齡約 15 年・約 27 坪・2 房",
  },
  {
    min: 1400, max: 1800,
    label: "1,400–1,800 萬",
    summary: "住宅大樓為主・屋齡約 11 年・約 31 坪・2 房",
  },
  {
    min: 1800, max: 2500,
    label: "1,800–2,500 萬",
    summary: "近年新成屋・屋齡約 8 年・約 38 坪・3 房",
  },
  {
    min: 2500, max: 3500,
    label: "2,500–3,500 萬",
    summary: "新成屋大坪數・屋齡約 8 年・約 57 坪・3 房",
  },
  {
    min: 3500, max: 99999,
    label: "3,500 萬以上",
    summary: "大坪數住宅大樓或透天厝・屋齡約 11 年・約 94 坪・3 房以上",
  },
];
