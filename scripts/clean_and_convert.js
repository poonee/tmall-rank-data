/**
 * 从原始用户数据生成完整的 RANKING_15DAY 和 BRAND_RANKING_15DAY 格式
 * 
 * 核心改进（vs 旧版 clean_and_convert.js）：
 * 1. 保留所有曾经上榜的产品/品牌（不只保留最新日期有排名的）
 * 2. 每天同品牌同型号出现多次时取最佳排名（如德龙EC9555M同一天4次）
 * 3. 合并同一品牌的不同中英文名（如 Aeomjk/艾摩客）
 * 4. 品牌映射更完整
 */

const fs = require('fs');

// ============ 品牌名映射（中文→英文统一） ============
const BRAND_MAP = {
  "格米莱": "GEMILAI", "柏翠": "Petrus", "百胜图": "Barsetto",
  "海氏": "Hauswirt", "佩罗奇": "Peiluoqi", "德龙": "Delonghi",
  "西屋": "Westinghouse", "温豆季": "Wendouji", "技诺": "Jino",
  "雪特朗": "Stelang", "咖博士": "Dr.coffee", "惠家": "Welhome",
  "连咖啡": "Liankafei", "飞利浦": "Philips", "咖乐美": "KALERM",
  "突尼": "Tuni", "迈拓": "Macap", "德颐": "Deyi",
  "火箭": "Rocket", "客浦": "Capresso", "艾尔菲德": "Alphafe",
  "施耐德": "Schneider", "小熊": "Bear", "wigomat": "wigomat",
  "奈斯派索": "NESPRESSO", "铂富": "Breville", "极萃师": "JICCSI",
  "露茉": "Lumos Bari", "咖啡自由": "KAxFREE", "赛普达": "SAPOUDR",
  "SMEG": "SMEG", "艾摩客": "Aeomjk", "WMF": "WMF",
  "凯度": "CASDON", "卡伦特": "Kalenter", "Aeomjk": "Aeomjk",
  "La Marzocco": "LA MARZOCCO", "Lelit": "LELIT", "膳魔师": "THERMOS",
  "Tim Hortons": "Tim Hortons",
  "Barsetto": "Barsetto", "Delonghi": "Delonghi", "Philips": "Philips",
};

// 中文品牌名（用于显示）
const BRAND_CN = {
  "Delonghi": "德龙", "GEMILAI": "格米莱", "Philips": "飞利浦",
  "Barsetto": "百胜图", "Petrus": "柏翠", "NESPRESSO": "奈斯派索",
  "Breville": "铂富", "Hauswirt": "海氏", "JICCSI": "极萃师",
  "Lumos Bari": "露茉", "KAxFREE": "咖啡自由", "Bear": "小熊",
  "SAPOUDR": "赛普达", "Stelang": "雪特朗", "SMEG": "SMEG",
  "wigomat": "wigomat", "Aeomjk": "Aeomjk", "WMF": "WMF",
  "CASDON": "凯度", "Dr.coffee": "咖博士", "Kalenter": "卡伦特",
  "LA MARZOCCO": "La Marzocco", "LELIT": "Lelit", "THERMOS": "膳魔师",
  "Tim Hortons": "Tim Hortons",
};

function normalizeBrand(name) {
  return BRAND_MAP[name] || name;
}

function parsePrice(priceStr) {
  if (!priceStr || priceStr === '-' || priceStr === '') return 0;
  const s = String(priceStr).replace(/[¥￥,]/g, '').trim();
  const n = parseFloat(s);
  return isNaN(n) ? 0 : Math.round(n);
}

// ============ 解析原始JS文件 ============
function parseJsFile(filepath) {
  const content = fs.readFileSync(filepath, 'utf8');
  // 提取 = 后面的 JSON 部分
  const match = content.match(/=\s*(\{[\s\S]*\})\s*;?\s*$/);
  if (!match) throw new Error(`Cannot parse JS file: ${filepath}`);
  let data;
  eval('data = ' + match[1]);
  return data;
}

// ============ 重建单品榜 ============
function rebuildProductData(rawPath) {
  const RAW = parseJsFile(rawPath);
  const dates = RAW.dates || RAW.metadata?.dates || [];
  const products = RAW.products || {};

  console.log(`单品榜原始数据: ${Object.keys(products).length} 个产品条目, ${dates.length} 天`);

  // 每天收集TOP30产品，合并同品牌同型号
  const dailyRankings = {};  // date -> { pkey: {rank, price, sales, brand, model, img} }
  for (const date of dates) {
    const dayMap = {};
    for (const [key, prod] of Object.entries(products)) {
      const hist = prod.history || {};
      if (!hist[date]) continue;
      const h = hist[date];
      const rank = h.rank;
      if (rank == null || rank > 30) continue;

      const brandCN = prod.brand || '';
      const brandEN = normalizeBrand(brandCN);
      const model = (prod.model || '').trim();
      const img = prod.img || '';
      const price = parsePrice(h.price);
      const sales = h.sales || '';

      // 产品唯一键: 品牌英文|型号（型号为空时用特殊标识）
      const pkey = model ? `${brandEN}|${model}` : `${brandEN}|__EMPTY__`;

      // 同一天同一产品出现多次，取排名最好的
      if (pkey in dayMap) {
        if (rank < dayMap[pkey].rank) {
          dayMap[pkey] = { rank, price, sales, brand: brandEN, model, img };
        }
      } else {
        dayMap[pkey] = { rank, price, sales, brand: brandEN, model, img };
      }
    }
    dailyRankings[date] = dayMap;
  }

  // 合并所有产品
  const allProducts = {};  // pkey -> {brand, model, img, dailyData: {date: {rank, price, sales}}}
  for (const [date, dayMap] of Object.entries(dailyRankings)) {
    for (const [pkey, info] of Object.entries(dayMap)) {
      if (!allProducts[pkey]) {
        allProducts[pkey] = {
          brand: info.brand,
          model: info.model,
          img: info.img,
          dailyData: {}
        };
      }
      allProducts[pkey].dailyData[date] = {
        rank: info.rank,
        price: info.price,
        sales: info.sales
      };
    }
  }

  // 构建输出
  const productsOutput = [];
  for (const [pkey, pdata] of Object.entries(allProducts)) {
    // 构建trend数组
    const trend = dates.map(d => {
      const dd = pdata.dailyData[d];
      return dd ? dd.rank : null;
    });

    // 计算最新排名（最后一个有排名的日期）
    let rankToday = null, rankYesterday = null, latestIdx = null;
    for (let i = dates.length - 1; i >= 0; i--) {
      if (trend[i] !== null) {
        if (latestIdx === null) {
          latestIdx = i;
          rankToday = trend[i];
        } else {
          rankYesterday = trend[i];
          break;
        }
      }
    }

    if (rankToday === null) continue;  // 从未上榜，跳过

    // 排名变化
    const rankChange = (rankToday != null && rankYesterday != null) ? rankYesterday - rankToday : null;

    // 最佳/平均排名
    const validRanks = trend.filter(v => v !== null);
    const bestRank = validRanks.length > 0 ? Math.min(...validRanks) : null;
    const avgRank = validRanks.length > 0
      ? Math.round(validRanks.reduce((a, b) => a + b, 0) / validRanks.length * 10) / 10
      : null;

    // 最新非零价格
    let price = 0;
    for (let i = dates.length - 1; i >= 0; i--) {
      const dd = pdata.dailyData[dates[i]];
      if (dd && dd.price > 0) { price = dd.price; break; }
    }

    productsOutput.push({
      brand: pdata.brand,
      model: pdata.model,
      image_url: pdata.img,
      price,
      est_daily: null,
      rank_today: rankToday,
      rank_yesterday: rankYesterday,
      rank_change: rankChange,
      best_rank: bestRank,
      avg_rank: avgRank,
      trend,
      sales_7d: '',
      sales_30d: '',
      trend_text: '',
    });
  }

  // 按最新排名排序
  productsOutput.sort((a, b) => (a.rank_today ?? 999) - (b.rank_today ?? 999));

  const brandSet = new Set(productsOutput.map(p => p.brand));

  return {
    dates,
    latestDate: dates[dates.length - 1],
    totalDays: dates.length,
    products: productsOutput,
    stats: {
      total_products: productsOutput.length,
      brand_count: brandSet.size,
      latest_date: dates[dates.length - 1]
    }
  };
}

// ============ 重建品牌榜 ============
function rebuildBrandData(rawPath) {
  const RAW = parseJsFile(rawPath);
  const dates = RAW.dates || RAW.metadata?.dates || [];
  const brands = RAW.brands || {};

  console.log(`品牌榜原始数据: ${Object.keys(brands).length} 个品牌条目, ${dates.length} 天`);

  // 每天收集品牌排名，合并同品牌不同条目
  const dailyRankings = {};  // date -> { brandEN: {rank, desc, followers, trend, brandCN} }
  for (const date of dates) {
    const dayMap = {};
    for (const [key, bdata] of Object.entries(brands)) {
      const hist = bdata.history || {};
      if (!hist[date]) continue;
      const h = hist[date];
      const rank = h.rank;
      if (rank == null) continue;

      const brandCN = bdata.brand_cn || key;
      const brandEN = normalizeBrand(key);
      const brandCNDisplay = BRAND_CN[brandEN] || brandCN;

      // 同一品牌合并，取排名最好的
      if (brandEN in dayMap) {
        if (rank < dayMap[brandEN].rank) {
          dayMap[brandEN] = {
            rank,
            desc: h.desc || '',
            followers: h.followers || '',
            trend: h.trend || '',
            brandCN: brandCNDisplay,
          };
        }
      } else {
        dayMap[brandEN] = {
          rank,
          desc: h.desc || '',
          followers: h.followers || '',
          trend: h.trend || '',
          brandCN: brandCNDisplay,
        };
      }
    }
    dailyRankings[date] = dayMap;
  }

  // 合并所有品牌
  const allBrands = {};  // brandEN -> {brandCN, dailyData: {date: {rank, desc, followers, trend}}}
  for (const [date, dayMap] of Object.entries(dailyRankings)) {
    for (const [brandEN, info] of Object.entries(dayMap)) {
      if (!allBrands[brandEN]) {
        allBrands[brandEN] = {
          brandCN: info.brandCN,
          dailyData: {}
        };
      }
      allBrands[brandEN].dailyData[date] = {
        rank: info.rank,
        desc: info.desc,
        followers: info.followers,
        trend: info.trend,
      };
    }
  }

  // 构建输出
  const brandsOutput = [];
  for (const [brandEN, bdata] of Object.entries(allBrands)) {
    const trend = dates.map(d => {
      const dd = bdata.dailyData[d];
      return dd ? dd.rank : null;
    });

    // 最新排名
    let rankToday = null, rankYesterday = null, latestIdx = null;
    for (let i = dates.length - 1; i >= 0; i--) {
      if (trend[i] !== null) {
        if (latestIdx === null) {
          latestIdx = i;
          rankToday = trend[i];
        } else {
          rankYesterday = trend[i];
          break;
        }
      }
    }

    if (rankToday === null) continue;

    const rankChange = (rankToday != null && rankYesterday != null) ? rankYesterday - rankToday : null;

    const validRanks = trend.filter(v => v !== null);
    const bestRank = validRanks.length > 0 ? Math.min(...validRanks) : null;
    const avgRank = validRanks.length > 0
      ? Math.round(validRanks.reduce((a, b) => a + b, 0) / validRanks.length * 10) / 10
      : null;

    // 最新日期的followers和trend_text
    const latestDate = latestIdx !== null ? dates[latestIdx] : null;
    const latestInfo = latestDate ? bdata.dailyData[latestDate] : {};
    const followers = latestInfo.followers || '';
    let trendText = latestInfo.trend || '';
    if (!trendText && latestInfo.desc) trendText = latestInfo.desc;

    brandsOutput.push({
      brand: brandEN,
      brand_cn: bdata.brandCN,
      rank_today: rankToday,
      rank_yesterday: rankYesterday,
      rank_change: rankChange,
      best_rank: bestRank,
      avg_rank: avgRank,
      trend,
      followers,
      trend_text: trendText,
      prices: '',
    });
  }

  brandsOutput.sort((a, b) => (a.rank_today ?? 999) - (b.rank_today ?? 999));

  return {
    dates,
    latestDate: dates[dates.length - 1],
    totalDays: dates.length,
    brands: brandsOutput,
    stats: {
      total_brands: brandsOutput.length,
      latest_date: dates[dates.length - 1]
    }
  };
}

// ============ 主程序 ============
const rawProductPath = '/tmp/ranking_15day_data.js';
const rawBrandPath = '/tmp/brand_ranking_15day_data.js';

// 重建单品榜
const productData = rebuildProductData(rawProductPath);
const productJs = 'const RANKING_15DAY = ' + JSON.stringify(productData, null, 2) + ';\n';
fs.writeFileSync('/tmp/clean_ranking_15day_data.js', productJs);

console.log(`\n单品榜输出: ${productData.products.length} 个产品, ${productData.stats.brand_count} 个品牌`);

// 每天在榜数
productData.dates.forEach((date, i) => {
  const count = productData.products.filter(p => p.trend[i] !== null).length;
  console.log(`  ${date}: ${count} 个产品在榜`);
});

// 重建品牌榜
const brandData = rebuildBrandData(rawBrandPath);
const brandJs = 'const BRAND_RANKING_15DAY = ' + JSON.stringify(brandData, null, 2) + ';\n';
fs.writeFileSync('/tmp/clean_brand_ranking_15day_data.js', brandJs);

console.log(`\n品牌榜输出: ${brandData.brands.length} 个品牌`);

// 每天在榜数
brandData.dates.forEach((date, i) => {
  const count = brandData.brands.filter(b => b.trend[i] !== null).length;
  console.log(`  ${date}: ${count} 个品牌在榜`);
});

console.log('\n=== 数据重建完成 ===');
