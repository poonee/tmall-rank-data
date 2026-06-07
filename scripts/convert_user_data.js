// 将用户提供的 RANKING_15DAY_DATA / BRAND_RANKING_15DAY_DATA
// 转换为 HTML 页面所需的 RANKING_15DAY / BRAND_RANKING_15DAY 格式

const fs = require('fs');

// ── 品牌名标准化映射 ──
const BRAND_MAP = {
  "格米莱": "GEMILAI",
  "海氏": "Hauswirt",
  "百胜图": "Barsetto",
  "柏翠": "Petrus",
  "西屋": "Westinghouse",
  "火箭": "Rocket",
  "惠家": "Welhome",
  "温豆季": "Wendouji",
  "技诺": "Jino",
  "雪特朗": "Stelang",
  "突尼": "Tuni",
  "迈拓": "MaiTuo",
  "德颐": "DEYI",
  "客浦": "Kepu",
  "艾尔菲德": "ErFeide",
  "佩罗奇": "Peiluoqi",
  "飞利浦": "Philips",
  "施耐德": "Schneider",
  "咖博士": "Dr.coffee",
  "德龙": "Delonghi",
  "咖乐美": "KALERM",
  "连咖啡": "Liankafei",
  "wigomat": "wigomat"
};

// ── 工具函数 ──
function getLatestDate(dates) {
  return dates[dates.length - 1];
}

function getPrevDate(dates) {
  return dates.length >= 2 ? dates[dates.length - 2] : null;
}

function parsePrice(priceStr) {
  if (!priceStr) return 0;
  // Remove ¥ and commas
  const num = parseFloat(priceStr.replace(/[¥,]/g, ''));
  return isNaN(num) ? 0 : num;
}

function parseSalesCount(salesStr) {
  if (!salesStr) return 0;
  // e.g., "400+件", "近30天内销量1000+", "1000+"
  const m = salesStr.match(/(\d+)\+/);
  if (m) return parseInt(m[1]);
  return 0;
}

function getRankOnDate(product, date) {
  if (product.history && product.history[date]) {
    return product.history[date].rank;
  }
  return null;
}

function getSalesOnDate(product, date) {
  if (product.history && product.history[date]) {
    return product.history[date].sales || '';
  }
  return '';
}

function getSales30dOnDate(product, date) {
  if (product.history && product.history[date]) {
    return product.history[date].sales_30d || '';
  }
  return '';
}

function getEstOnDate(product, date) {
  if (product.history && product.history[date] && product.history[date].est) {
    return product.history[date].est;
  }
  return null;
}

function getPriceOnDate(product, date) {
  if (product.history && product.history[date]) {
    return parsePrice(product.history[date].price);
  }
  return 0;
}

function calcAvgRank(trend) {
  const valid = trend.filter(v => v !== null && v !== undefined);
  if (valid.length === 0) return 0;
  const sum = valid.reduce((a, b) => a + b, 0);
  return Math.round(sum / valid.length * 10) / 10;
}

function calcRankChange(currRank, prevRank) {
  if (prevRank === null || prevRank === undefined) return null;
  return prevRank - currRank; // positive = up, negative = down
}

// ── 加载用户数据 ──
function loadUserData(filepath, varName) {
  const content = fs.readFileSync(filepath, 'utf8');
  eval(content);
  // After eval, the variable varName is in scope
  return eval(varName);
}

// ═══════════════════════════════════════════
// 转换产品排行榜数据
// ═══════════════════════════════════════════
function convertProductData(userData) {
  const dates = userData.dates;
  const latestDate = getLatestDate(dates);
  const prevDate = getPrevDate(dates);
  const products = [];

  const productKeys = Object.keys(userData.products);
  const allBrands = new Set();

  productKeys.forEach(key => {
    const p = userData.products[key];
    const brandCN = p.brand;
    const brandEN = BRAND_MAP[brandCN] || brandCN;
    allBrands.add(brandEN);

    // Build trend array
    const trend = dates.map(d => getRankOnDate(p, d));

    // Latest date info
    const latestRank = getRankOnDate(p, latestDate);
    const prevRank = prevDate ? getRankOnDate(p, prevDate) : null;
    const latestPrice = getPriceOnDate(p, latestDate);
    const latestEst = getEstOnDate(p, latestDate);
    const latestSales = getSalesOnDate(p, latestDate);
    const latestSales30d = getSales30dOnDate(p, latestDate);

    // Est daily conversion
    let estDaily = null;
    if (latestEst) {
      estDaily = {
        value: latestEst.v,
        range: latestEst.lo + '-' + latestEst.hi,
        source: latestEst.s && latestEst.s[0] ? latestEst.s[0].replace('7d', 's7').replace('30d', 's30').replace('year', 'sy') : 's7',
        confidence: latestEst.c === 'l' ? 'cl' : latestEst.c === 'm' ? 'cm' : latestEst.c === 'h' ? 'ch' : 'cl'
      };
    }

    // Sales 7d
    let sales7d = '';
    if (latestSales) {
      sales7d = latestSales;
    }

    // Trend text
    let trendText = '';
    if (latestEst && latestEst.m) {
      trendText = latestEst.m;
    } else if (latestSales30d) {
      trendText = latestSales30d;
    } else if (latestSales) {
      trendText = latestSales;
    }

    // Rank change
    const rankChange = calcRankChange(latestRank, prevRank);

    // Avg rank
    const avgRank = calcAvgRank(trend);

    products.push({
      brand: brandEN,
      model: p.model,
      image_url: p.img || '',
      price: latestPrice,
      est_daily: estDaily,
      rank_today: latestRank,
      rank_yesterday: prevRank,
      rank_change: rankChange,
      best_rank: p.bestRank || Math.min(...trend.filter(v => v !== null)),
      avg_rank: avgRank,
      trend: trend,
      sales_7d: sales7d,
      sales_30d: latestSales30d,
      trend_text: trendText
    });
  });

  // Sort by current rank
  products.sort((a, b) => (a.rank_today || 999) - (b.rank_today || 999));

  const result = {
    dates: dates,
    latestDate: latestDate,
    totalDays: dates.length,
    stats: {
      total_products: products.length,
      brand_count: allBrands.size,
      latest_date: latestDate
    },
    products: products
  };

  return result;
}

// ═══════════════════════════════════════════
// 转换品牌排行榜数据
// ═══════════════════════════════════════════
function convertBrandData(userData) {
  const dates = userData.dates;
  const latestDate = getLatestDate(dates);
  const prevDate = getPrevDate(dates);
  const brands = [];

  const brandKeys = Object.keys(userData.brands);

  brandKeys.forEach(key => {
    const b = userData.brands[key];
    const brandEN = b.brand_en || b.brand_cn;

    // Build trend array
    const trend = dates.map(d => {
      if (b.history && b.history[d]) {
        return b.history[d].rank;
      }
      return null;
    });

    // Latest date info
    const latestRank = trend[trend.length - 1];
    const prevRank = prevDate ? (b.history && b.history[prevDate] ? b.history[prevDate].rank : null) : null;
    const latestHistory = b.history && b.history[latestDate] ? b.history[latestDate] : null;
    const prevHistory = prevDate && b.history && b.history[prevDate] ? b.history[prevDate] : null;

    const rankChange = calcRankChange(latestRank, prevRank);
    const avgRank = calcAvgRank(trend);

    // Followers
    let followers = '';
    if (latestHistory && latestHistory.followers) {
      followers = latestHistory.followers;
    } else if (latestHistory && latestHistory.desc) {
      const fm = latestHistory.desc.match(/([\d万+]+人正在关注)/);
      if (fm) followers = fm[1];
    }

    // Trend text
    let trendText = '';
    if (latestHistory && latestHistory.trend) {
      trendText = latestHistory.trend;
    } else if (latestHistory && latestHistory.desc) {
      trendText = latestHistory.desc;
    }

    brands.push({
      brand: brandEN,
      brand_cn: b.brand_cn || brandEN,
      rank_today: latestRank,
      rank_yesterday: prevRank,
      rank_change: rankChange,
      best_rank: b.bestRank || Math.min(...trend.filter(v => v !== null)),
      avg_rank: avgRank,
      trend: trend,
      followers: followers,
      trend_text: trendText,
      prices: ''
    });
  });

  // Sort by current rank
  brands.sort((a, b) => (a.rank_today || 999) - (b.rank_today || 999));

  const result = {
    dates: dates,
    latestDate: latestDate,
    totalDays: dates.length,
    stats: {
      total_brands: brands.length,
      latest_date: latestDate
    },
    brands: brands
  };

  return result;
}

// ═══════════════════════════════════════════
// 主流程
// ═══════════════════════════════════════════

// Load user data
const userProductData = loadUserData('/tmp/ranking_15day_data.js', 'RANKING_15DAY_DATA');
const userBrandData = loadUserData('/tmp/brand_ranking_15day_data.js', 'BRAND_RANKING_15DAY_DATA');

// Convert
const convertedProducts = convertProductData(userProductData);
const convertedBrands = convertBrandData(userBrandData);

// Write output files
const productOutput = 'const RANKING_15DAY = ' + JSON.stringify(convertedProducts, null, 2) + ';\n';
const brandOutput = 'const BRAND_RANKING_15DAY = ' + JSON.stringify(convertedBrands, null, 2) + ';\n';

fs.writeFileSync('/tmp/converted_ranking_15day_data.js', productOutput);
fs.writeFileSync('/tmp/converted_brand_ranking_15day_data.js', brandOutput);

// Print summary
console.log('=== 产品数据转换完成 ===');
console.log('产品数:', convertedProducts.products.length);
console.log('品牌数:', convertedProducts.stats.brand_count);
console.log('日期:', convertedProducts.dates[0], '~', convertedProducts.dates[convertedProducts.dates.length - 1], `(${convertedProducts.dates.length}天)`);

console.log('\n=== 品牌数据转换完成 ===');
console.log('品牌数:', convertedBrands.brands.length);
console.log('日期:', convertedBrands.dates[0], '~', convertedBrands.dates[convertedBrands.dates.length - 1], `(${convertedBrands.dates.length}天)`);

// Verify a few entries
console.log('\n产品 TOP3:');
convertedProducts.products.slice(0, 3).forEach(p => {
  console.log(`  #${p.rank_today} ${p.brand} ${p.model} ¥${p.price} 趋势:[${p.trend.join(',')}]`);
});

console.log('\n品牌 TOP3:');
convertedBrands.brands.slice(0, 3).forEach(b => {
  console.log(`  #${b.rank_today} ${b.brand} 趋势:[${b.trend.join(',')}] 关注:${b.followers}`);
});

// File sizes
console.log('\n文件大小:');
console.log('  ranking_15day_data.js:', fs.statSync('/tmp/converted_ranking_15day_data.js').size, 'bytes');
console.log('  brand_ranking_15day_data.js:', fs.statSync('/tmp/converted_brand_ranking_15day_data.js').size, 'bytes');
