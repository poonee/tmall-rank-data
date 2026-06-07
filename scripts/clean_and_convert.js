/**
 * 重新从原始用户数据生成干净的 RANKING_15DAY 格式
 * 
 * 修复问题：
 * 1. 去重：品牌|型号 相同（去掉 _# 后缀）的合并
 * 2. 过滤：只保留最新日期有排名数据的产品（TOP 30）
 * 3. 按最新日期排名排序
 */

const fs = require('fs');

const BRAND_MAP = {
  "格米莱": "GEMILAI", "海氏": "Hauswirt", "百胜图": "Barsetto",
  "柏翠": "Petrus", "西屋": "Westinghouse", "火箭": "Rocket",
  "惠家": "Welhome", "温豆季": "Wendouji", "技诺": "Jino",
  "雪特朗": "Stelang", "突尼": "Tuni", "迈拓": "MaiTuo",
  "德颐": "DEYI", "客浦": "Kepu", "艾尔菲德": "ErFeide",
  "佩罗奇": "Peiluoqi", "飞利浦": "Philips", "施耐德": "Schneider",
  "咖博士": "Dr.coffee", "德龙": "Delonghi", "咖乐美": "KALERM",
  "连咖啡": "Liankafei", "wigomat": "wigomat", "Barsetto": "Barsetto",
  "Delonghi": "Delonghi", "Philips": "Philips", "飞利浦(PHILIPS)": "Philips"
};

function cleanModel(model) {
  // 去掉 _# 后缀，如 "BAE02S_#3228" -> "BAE02S"
  return model.replace(/_[a-zA-Z0-9#]+$/, '');
}

function makeKey(brand, model) {
  return (brand || '') + '|' + cleanModel(model || '');
}

// ── 加载原始数据 ──
const rawContent = fs.readFileSync('/tmp/ranking_15day_data.js', 'utf8');
let RAW;
eval('RAW = ' + rawContent.replace('var RANKING_15DAY_DATA =', ''));

const dates = RAW.dates;
const latestDate = dates[dates.length - 1];
const prevDate = dates.length >= 2 ? dates[dates.length - 2] : null;

console.log(`原始数据: ${Object.keys(RAW.products).length} 个产品, ${dates.length} 天`);
console.log(`最新日期: ${latestDate}`);

// ── 按清理后的 brand|model 分组 ──
const groups = {};
Object.entries(RAW.products).forEach(([key, p]) => {
  const brandCN = p.brand;
  const brandEN = BRAND_MAP[brandCN] || brandCN;
  const groupKey = makeKey(brandEN, p.model);

  if (!groups[groupKey]) {
    groups[groupKey] = { brand: brandEN, model: cleanModel(p.model), entries: [] };
  }
  groups[groupKey].entries.push(p);
});

console.log(`去重后: ${Object.keys(groups).length} 个唯一产品\n`);

// ── 统计每个产品的最新日期排名 ──
const ranked = [];
Object.entries(groups).forEach(([groupKey, g]) => {
  const entries = g.entries;
  
  // 找出最新日期有排名的条目
  let bestEntry = null;
  let latestRank = null;
  let combinedTrend = null;
  
  // 优先找有最新日期排名的条目
  const withLatest = entries.filter(e => e.history && e.history[latestDate]);
  if (withLatest.length > 0) {
    // 有多个同型号产品都有最新日期，取排名最高的
    withLatest.sort((a, b) => a.history[latestDate].rank - b.history[latestDate].rank);
    bestEntry = withLatest[0];
    latestRank = bestEntry.history[latestDate].rank;
  } else {
    // 没有最新日期数据 → 跳过（不在榜）
    return;
  }

  // ── 合并历史趋势 ──
  // 对于每个日期，从所有条目中取最佳的排名数据
  const trend = dates.map(d => {
    const dayEntries = entries.filter(e => e.history && e.history[d]);
    if (dayEntries.length === 0) return null;
    // 取该日期排名最高的（排名数字最小）
    dayEntries.sort((a, b) => a.history[d].rank - b.history[d].rank);
    return dayEntries[0].history[d].rank;
  });

  // ── 最新日期详情 ──
  const latestHist = bestEntry.history[latestDate];
  const prevHist = prevDate && bestEntry.history[prevDate] ? bestEntry.history[prevDate] : null;
  
  // 昨日排名
  const prevRank = prevHist ? prevHist.rank : null;
  
  // 排名变化（正=上升，负=下降）
  const rankChange = prevRank !== null ? prevRank - latestRank : null;
  
  // 最佳排名
  const validRanks = trend.filter(v => v !== null);
  const bestRank = validRanks.length > 0 ? Math.min(...validRanks) : 999;

  // 平均排名（无数据按35算）
  let rankSum = 0;
  for (let i = 0; i < dates.length; i++) {
    rankSum += trend[i] !== null ? trend[i] : 35;
  }
  const avgRank = Math.round(rankSum / dates.length * 10) / 10;

  // 价格
  const price = latestHist.price ? parseFloat(String(latestHist.price).replace(/[¥,]/g, '')) : 0;

  // 销量
  const sales7d = latestHist.sales || '';
  const sales30d = latestHist.sales_30d || '';

  // est_daily
  let estDaily = null;
  if (latestHist.est) {
    estDaily = {
      value: latestHist.est.v || 0,
      range: (latestHist.est.lo || '-') + '-' + (latestHist.est.hi || '-'),
      source: latestHist.est.s && latestHist.est.s[0] ? latestHist.est.s[0].replace('7d', 's7').replace('30d', 's30').replace('year', 'sy') : 's7',
      confidence: latestHist.est.c === 'l' ? 'cl' : latestHist.est.c === 'm' ? 'cm' : latestHist.est.c === 'h' ? 'ch' : 'cl'
    };
  }

  // 趋势文字
  let trendText = '';
  if (latestHist.est && latestHist.est.m) trendText = latestHist.est.m;
  else if (sales30d) trendText = sales30d;
  else if (sales7d) trendText = sales7d;

  ranked.push({
    brand: g.brand,
    model: g.model,
    image_url: bestEntry.img || '',
    price: isNaN(price) ? 0 : price,
    est_daily: estDaily,
    rank_today: latestRank,
    rank_yesterday: prevRank,
    rank_change: rankChange,
    best_rank: bestRank,
    avg_rank: avgRank,
    trend: trend,
    sales_7d: sales7d,
    sales_30d: sales30d,
    trend_text: trendText
  });
});

// ── 按最新排名排序 ──
ranked.sort((a, b) => (a.rank_today || 999) - (b.rank_today || 999));

// ── 统计 ──
const brandsSet = new Set(ranked.map(p => p.brand));

const result = {
  dates: dates,
  latestDate: latestDate,
  totalDays: dates.length,
  products: ranked,
  stats: {
    total_products: ranked.length,
    brand_count: brandsSet.size,
    latest_date: latestDate
  }
};

// ── 输出 ──
const output = 'const RANKING_15DAY = ' + JSON.stringify(result, null, 2) + ';\n';
fs.writeFileSync('/tmp/clean_ranking_15day_data.js', output);

console.log('=== 清理完成 ===');
console.log(`产品数: ${ranked.length} (去重+过滤后)`);
console.log(`品牌数: ${brandsSet.size}`);
console.log(`有最新日期排名: ${ranked.filter(p => p.rank_today !== null).length}`);
console.log(`文件大小: ${fs.statSync('/tmp/clean_ranking_15day_data.js').size} bytes`);
console.log(`\nTOP 5:`);
ranked.slice(0, 5).forEach(p => {
  console.log(`  #${p.rank_today} ${p.brand} ${p.model} ¥${p.price}`);
});
console.log(`\n底部 3 个:`);
ranked.slice(-3).forEach(p => {
  console.log(`  #${p.rank_today} ${p.brand} ${p.model} ¥${p.price} (排名变化:${p.rank_change})`);
});
