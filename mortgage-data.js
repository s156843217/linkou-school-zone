/* mortgage-data.js — 房貸試算頁資料
   資料來源：內政部實價登錄 近一年（114Q1～115Q1，買賣成交，林口區住宅）
   排除：土地、車位、親友／股東特殊交易、預售屋、海砂屋
   依路名對照商圈後統計，單價單位：萬元／坪（不含車位）
   ※ 北側商圈樣本數不足（近一年僅 11 筆），維持前期數字供參考
*/

// ── 林口各商圈每坪單價（近一年實價登錄） ──────────────────
// medPrice：中位數（萬/坪）
// priceRange：[Q1, Q3]（25%～75% 分位）
// ageMed：成交屋齡中位數（年）
// roomMed：成交房數中位數
// indoorPct：室內坪數佔登記坪數比例（中位數）
//   室內 = 主建物 + 附屬建物 + 陽台（即扣除「公設」與「車位」後的實際室內面積）
//   依各地段實價登錄分項面積（rps28 主建物 + rps29 附屬 + rps30 陽台）統計，樣本 1,451 筆
const LINKOU_ZONES = [
  { name: "三井Outlet",  medPrice: 56.2, priceRange: [50.1, 66.1], count: 127, ageMed: 11, roomMed: 3, indoorPct: 0.671 },
  { name: "南勢",        medPrice: 54.2, priceRange: [46.3, 57.3], count:  66, ageMed:  9, roomMed: 3, indoorPct: 0.668 },
  { name: "家樂福商圈",  medPrice: 47.2, priceRange: [41.0, 54.4], count: 196, ageMed: 15, roomMed: 3, indoorPct: 0.669 },
  { name: "北側",        medPrice: 57.0, priceRange: [54.1, 59.6], count:  14, ageMed:  4, roomMed: 2, indoorPct: 0.697 },
  { name: "林口舊市區",  medPrice: 50.2, priceRange: [41.6, 62.2], count: 123, ageMed:  8, roomMed: 3, indoorPct: 0.670 },
  { name: "麗園國小",    medPrice: 39.1, priceRange: [29.3, 47.9], count:  82, ageMed: 19, roomMed: 3, indoorPct: 0.658 },
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
