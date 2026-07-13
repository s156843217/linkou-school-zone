/* 591-parse.js — 591 出售清單「貼上內容」解析器（純函式，不碰畫面）
   用途：競品比較工具的核心解析。輸入剪貼簿的 HTML 字串（貼上事件的 text/html），
        輸出結構化的物件清單。
   設計原則：靠「物件詳情連結＋文字樣式」解析，刻意不依賴 591 的 class 名稱，
            這樣 591 改版時比較不容易整組壞掉。
   狀態：v1 草稿，欄位樣式（樓層/屋齡寫法）要等真實貼上樣本進來再校正。 */

/* 解析一整份貼上的 HTML。
   回傳 { items: [{id,url,title,price,unitPrice,size,layout,floor,floorTotal,age,raw}], skipped: [...] }
   price=總價(萬)、unitPrice=單價(萬/坪)、size=坪數；抓不到的欄位為 null。 */
function parse591(htmlString){
  const doc = new DOMParser().parseFromString(htmlString || '', 'text/html');
  const anchors = Array.from(doc.querySelectorAll('a[href*="house/detail/"]'));
  const byId = new Map();   // 同一張卡片常有多個連結（圖片＋標題），用物件編號去重
  const skipped = [];

  for (const a of anchors){
    const href = a.getAttribute('href') || '';
    const m = href.match(/house\/detail\/(\d+)\/(\d+)/);
    if (!m) continue;
    const id = m[2];

    const card = card591Root(a);
    const text = (card.textContent || '').replace(/\s+/g, ' ').trim();
    if (!/萬/.test(text)){
      skipped.push({ id, why: '卡片文字裡沒有價格（可能是廣告或圖片連結）', text: text.slice(0, 120) });
      continue;
    }

    const item = parse591CardText(text);
    item.id = id;
    item.url = 'https://sale.591.com.tw/home/house/detail/' + m[1] + '/' + id + '.html';
    item.raw = text.slice(0, 250);

    /* 社區名：卡片上的社區標籤是連到 591 社區專頁（market.591）的連結 */
    const ca = card.querySelector('a[href*="market.591.com.tw"]');
    const cname = ca ? (ca.textContent || '').replace(/\s+/g, ' ').trim() : '';
    item.community = (cname && cname.length <= 20) ? cname : null;

    /* 連結本身的文字通常是標題（若含價格代表整張卡都是連結，不能當標題） */
    const at = (a.textContent || '').replace(/\s+/g, ' ').trim();
    if (at.length >= 6 && at.length <= 60 && !/萬/.test(at)) item.title = at;

    /* 沒有乾淨標題時，從卡片文字推一個：去掉開頭的「N分鐘前更新／曝光」雜訊，
       切在第一個規格數字（房/坪/萬）之前 */
    if (!item.title){
      let g = text.replace(/^.*?次曝光\s*/, '').replace(/^\d+\s*(分鐘|小時|天)前更新\s*/, '');
      const cut = g.search(/\d+\s*房|[\d,.]+\s*坪|[\d,]+\s*萬/);
      if (cut > 0) g = g.slice(0, cut);
      item.title = g.trim().slice(0, 40) || null;
    }

    const old = byId.get(id);
    if (!old || fieldCount591(item) > fieldCount591(old)){
      if (old && old.title && !item.title) item.title = old.title;  // 合併時別把標題弄丟
      byId.set(id, item);
    } else if (old && !old.title && item.title){
      old.title = item.title;
    }
  }
  return { items: Array.from(byId.values()), skipped };
}

/* 卡片邊界：從連結往上爬，爬到「還只包含這一個物件連結」的最上層。
   一旦某層出現別的物件編號，代表爬到整個清單容器了，就停在前一層。 */
function card591Root(a){
  let card = a, node = a.parentElement;
  for (let i = 0; i < 12 && node; i++){
    const ids = new Set();
    for (const x of node.querySelectorAll('a[href*="house/detail/"]')){
      const mm = (x.getAttribute('href') || '').match(/house\/detail\/\d+\/(\d+)/);
      if (mm) ids.add(mm[1]);
    }
    if (ids.size > 1) break;
    card = node;
    node = node.parentElement;
  }
  return card;
}

/* 從一張卡片的純文字抽欄位 */
function parse591CardText(text){
  /* 先把「萬/坪」改寫成「萬每坪」，免得單價跟總價、坪數的樣式互相咬到 */
  const t = text.replace(/萬\s*\/\s*坪/g, '萬每坪');
  const num = s => parseFloat(String(s).replace(/,/g, ''));

  /* 單價（萬/坪） */
  const um = t.match(/([\d,.]+)\s*萬每坪/);

  /* 總價：卡片裡所有「N萬」取最大值（最大的金額幾乎一定是總價）；
     100 萬以下視為雜訊（例如廣告文案「10萬人領取」） */
  let price = null;
  for (const mm of t.matchAll(/([\d,]+(?:\.\d+)?)\s*萬(?!每坪)/g)){
    const v = num(mm[1]);
    if (v >= 100 && (price === null || v > price)) price = v;
  }

  /* 坪數：清單卡常寫「權狀30.31坪 主建18.14坪」，權狀優先當主坪數；
     沒寫權狀的（如廣告卡「44.1坪」）就抓一般坪數，但要避開主建與車位 */
  const km = t.match(/權狀\s*([\d,.]+)\s*坪/);
  const mainm = t.match(/主建\s*([\d,.]+)\s*坪/);
  const t2 = t.replace(/(主建|車位)\s*[\d,.]+\s*坪/g, ' ');
  const sm = km || t2.match(/([\d,]+(?:\.\d+)?)\s*坪/);

  /* 格局：標題常出現「2房車」之類的字眼，所以不能抓第一個，
     要在整張卡裡挑「房廳衛寫得最完整」的那一組 */
  let lm = null, lmScore = -1;
  for (const g of t.matchAll(/(\d+)\s*房(?:\s*(\d+)\s*廳)?(?:\s*(\d+)\s*衛)?/g)){
    const score = (g[2] ? 1 : 0) + (g[3] ? 1 : 0);
    if (score > lmScore){ lm = g; lmScore = score; }
  }

  /* 樓層：常見「12F/21F」「12樓/21樓」「12/21F」幾種寫法都試 */
  const fm = t.match(/(\d+)\s*[F樓]\s*[\/~]\s*(\d+)\s*[F樓]/i)
          || t.match(/(\d+)\s*\/\s*(\d+)\s*[F樓]/i);

  /* 屋齡：「屋齡12.5年」優先；退而求其次抓「N年」但擋掉年份（>80 不採信） */
  const am = t.match(/屋齡\s*([\d.]+)\s*年/) || t.match(/([\d.]+)\s*年(?!前)/);
  let age = am ? parseFloat(am[1]) : null;
  if (age !== null && !(age > 0 && age < 80)) age = null;

  return {
    title: null,
    price,
    unitPrice: um ? num(um[1]) : null,
    size: sm ? num(sm[1]) : null,
    sizeMain: mainm ? num(mainm[1]) : null,
    layout: lm ? lm[0].replace(/\s+/g, '') : null,
    floor: fm ? fm[1] + 'F' : null,
    floorTotal: fm ? fm[2] + 'F' : null,
    age
  };
}

/* 有幾個欄位有抓到值（用來在重複連結之間挑資訊最齊的那筆） */
function fieldCount591(it){
  return ['title','price','unitPrice','size','sizeMain','layout','floor','age','community']
    .reduce((n, k) => n + (it[k] !== null && it[k] !== undefined ? 1 : 0), 0);
}
