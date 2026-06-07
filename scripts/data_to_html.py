#!/usr/bin/env python3
"""
data_to_html.py — 排行榜数据 → 可视化 HTML 页面

读取 daily/ 目录下的所有CSV数据，生成：
  1. output/ranking_data.js   — JS数据文件（供HTML页面加载）
  2. output/index.html        — 可视化趋势页面（独立HTML）

用法:
  python3 scripts/data_to_html.py              # 生成最新页面
  python3 scripts/data_to_html.py --open       # 生成后启动本地服务器

输出:
  /workspace/rank_data/output/ranking_data.js
  /workspace/rank_data/output/index.html
"""

import os, sys, json, glob
from datetime import datetime, date
from collections import defaultdict

sys.path.insert(0, "/workspace/rank_data/scripts")
from data_standards import SINGLE_RANK_FIELDS, BRAND_RANK_FIELDS

DATA_DIR = "/workspace/rank_data"
DAILY_DIR = f"{DATA_DIR}/daily"
OUTPUT_DIR = f"{DATA_DIR}/output"


def load_all_data() -> dict:
    """加载所有日期的数据"""
    # PC端数据
    pc_files = sorted(glob.glob(f"{DAILY_DIR}/*_pc.json"))
    mobile_files = sorted(glob.glob(f"{DAILY_DIR}/*_mobile.json"))
    brand_files = sorted(glob.glob(f"{DAILY_DIR}/*_brand.json"))

    data = {"pc": {}, "mobile": {}, "brand": {}}

    for f in pc_files:
        d = os.path.basename(f).split("_")[0]
        with open(f, "r", encoding="utf-8") as fh:
            data["pc"][d] = json.load(fh)

    for f in mobile_files:
        d = os.path.basename(f).split("_")[0]
        with open(f, "r", encoding="utf-8") as fh:
            data["mobile"][d] = json.load(fh)

    for f in brand_files:
        d = os.path.basename(f).split("_")[0]
        with open(f, "r", encoding="utf-8") as fh:
            data["brand"][d] = json.load(fh)

    return data


def build_ranking_trend(data: dict) -> list:
    """
    构建排名趋势数据：每个品牌每天的排名变化

    返回: [
        {
            "brand": "wigomat",
            "model": "W12",
            "trend": {"2026-06-02": 2, "2026-06-03": 1, ...}
        },
        ...
    ]
    """
    all_brands = {}
    
    for source in ["pc", "mobile"]:
        for date_str, records in data[source].items():
            for r in records:
                brand = r.get("brand", "")
                model = r.get("model", "")
                rank = r.get("rank", 0)
                price = r.get("price", 0)
                
                key = f"{brand}|{model}"
                if key not in all_brands:
                    all_brands[key] = {
                        "brand": brand,
                        "model": model,
                        "price": price,
                        "trend": {}
                    }
                all_brands[key]["trend"][date_str] = rank
                all_brands[key]["price"] = price

    result = []
    for key, info in all_brands.items():
        # 按日期排序
        sorted_dates = sorted(info["trend"].keys())
        sorted_ranks = [info["trend"][d] for d in sorted_dates]
        result.append({
            "brand": info["brand"],
            "model": info["model"],
            "price": info["price"],
            "dates": sorted_dates,
            "ranks": sorted_ranks,
        })
    
    return sorted(result, key=lambda x: min(x["ranks"]) if x["ranks"] else 99)


def build_brand_rankings(data: dict) -> list:
    """构建品牌榜趋势"""
    result = []
    for date_str, records in data["brand"].items():
        for r in records:
            result.append({
                "date": date_str,
                "rank": r["rank"],
                "brand_cn": r.get("brand_cn", ""),
                "brand_en": r.get("brand_en", ""),
                "description": r.get("description", ""),
                "prices": r.get("prices", ""),
            })
    return result


def get_latest_summary(data: dict) -> dict:
    """获取最新汇总"""
    all_dates = set()
    for source in ["pc", "mobile", "brand"]:
        all_dates.update(data[source].keys())
    
    if not all_dates:
        return {"latest_date": "", "total_records": 0, "brand_count": 0, "top5": []}
    
    latest = max(all_dates)
    total = 0
    brands_seen = set()
    top5 = []
    
    for source in ["pc", "mobile"]:
        if latest in data[source]:
            records = data[source][latest]
            total += len(records)
            for r in records[:5]:
                brand = r.get("brand", "")
                if brand and brand not in brands_seen:
                    brands_seen.add(brand)
                    top5.append({
                        "rank": r["rank"],
                        "brand": brand,
                        "model": r.get("model", ""),
                        "price": r.get("price", 0),
                    })
    
    return {
        "latest_date": latest,
        "total_records": total,
        "brand_count": len(brands_seen),
        "top5": top5[:5],
    }


def generate_js_file(data):
    """生成 ranking_data.js"""
    trend_data = build_ranking_trend(data)
    brand_data = build_brand_rankings(data)
    summary = get_latest_summary(data)
    
    all_dates = set()
    for source in ["pc", "mobile", "brand"]:
        all_dates.update(data[source].keys())
    dates_sorted = sorted(all_dates)
    
    js_content = f"""
// 排行榜数据 — 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}
// 请勿手动修改，运行 python3 scripts/data_to_html.py 更新

const RANK_DATA = {{
    // 汇总信息
    summary: {json.dumps(summary, ensure_ascii=False, indent=2)},

    // 所有数据日期（升序）
    dates: {json.dumps(dates_sorted, ensure_ascii=False)},

    // 品牌排名趋势
    rankingTrend: {json.dumps(trend_data, ensure_ascii=False, indent=2)},

    // 品牌榜数据
    brandRankings: {json.dumps(brand_data, ensure_ascii=False, indent=2)},

    // 原始数据（按日期和来源）
    rawData: {json.dumps(data, ensure_ascii=False, indent=2)},
}};
"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    js_path = f"{OUTPUT_DIR}/ranking_data.js"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content.strip())
    print(f"✅ JS 数据: {js_path} ({os.path.getsize(js_path)} bytes)")
    return js_path


def generate_html():
    """生成可视化HTML页面"""
    
    html = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>商用咖啡机排行榜 — 数据看板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="ranking_data.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
       background: #f5f6fa; color: #2c3e50; padding: 20px; }
.header { background: linear-gradient(135deg, #667eea, #764ba2);
          color: #fff; padding: 30px; border-radius: 16px; margin-bottom: 24px; }
.header h1 { font-size: 24px; margin-bottom: 8px; }
.header .meta { font-size: 14px; opacity: 0.9; }
.header .meta span { margin-right: 20px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr));
         gap: 16px; margin-bottom: 24px; }
.card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.card .value { font-size: 28px; font-weight: 700; color: #667eea; }
.card .label { font-size: 13px; color: #999; margin-top: 4px; }
.section { background: #fff; border-radius: 12px; padding: 24px;
           margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.section h2 { font-size: 18px; margin-bottom: 16px; color: #333; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { background: #f8f9fa; padding: 10px 12px; text-align: left;
     font-weight: 600; color: #666; border-bottom: 2px solid #eee; }
td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; }
tr:hover td { background: #f8f9ff; }
.rank-badge { display: inline-block; width: 28px; height: 28px; line-height: 28px;
              text-align: center; border-radius: 50%; font-weight: 700; font-size: 13px; }
.rank-1 { background: #ffd700; color: #333; }
.rank-2 { background: #e8e8e8; color: #333; }
.rank-3 { background: #ffc0b0; color: #333; }
.rank-other { background: #f0f0f0; color: #999; }
.trend-up { color: #e74c3c; }
.trend-down { color: #27ae60; }
.trend-flat { color: #999; }
.price { font-weight: 600; color: #e74c3c; }
.chart-container { position: relative; height: 400px; }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tab { padding: 8px 20px; border-radius: 20px; cursor: pointer;
       font-size: 14px; border: 1px solid #ddd; background: #fff; }
.tab.active { background: #667eea; color: #fff; border-color: #667eea; }
.footer { text-align: center; padding: 20px; font-size: 12px; color: #999; }
@media (max-width: 768px) {
  .header { padding: 20px; }
  .cards { grid-template-columns: repeat(2, 1fr); }
}
</style>
</head>
<body>

<div class="header">
  <h1>☕ 商用咖啡机排行榜 · 数据看板</h1>
  <div class="meta">
    <span id="meta-date">📅 加载中...</span>
    <span id="meta-records">📊 加载中...</span>
    <span id="meta-brands">🏷️ 加载中...</span>
  </div>
</div>

<!-- 汇总卡片 -->
<div class="cards" id="cards">
  <div class="card"><div class="value" id="card-total">-</div><div class="label">累计记录数</div></div>
  <div class="card"><div class="value" id="card-days">-</div><div class="label">采集天数</div></div>
  <div class="card"><div class="value" id="card-brands">-</div><div class="label">监控品牌</div></div>
  <div class="card"><div class="value" id="card-latest">-</div><div class="label">最新数据</div></div>
</div>

<!-- 排名趋势图 -->
<div class="section">
  <h2>📈 品牌排名趋势（15天）</h2>
  <div class="tabs">
    <span class="tab active" onclick="switchChart('pc')">PC端</span>
    <span class="tab" onclick="switchChart('mobile')">手机端</span>
  </div>
  <div class="chart-container">
    <canvas id="trendChart"></canvas>
  </div>
</div>

<!-- 最新排行 -->
<div class="section">
  <h2>🏆 最新排名 TOP10</h2>
  <table>
    <thead><tr><th>#</th><th>品牌</th><th>型号</th><th>价格</th><th>排名趋势</th><th>近7天销量</th></tr></thead>
    <tbody id="latest-table"></tbody>
  </table>
</div>

<!-- 品牌榜 -->
<div class="section">
  <h2>🏅 品牌榜 TOP10</h2>
  <table>
    <thead><tr><th>#</th><th>品牌</th><th>描述</th><th>价格(¥)</th></tr></thead>
    <tbody id="brand-table"></tbody>
  </table>
</div>

<div class="footer">
  数据每日更新 · 自动采集于天猫排行榜 · Powered by Rank Data System
</div>

<script>
// ── 初始化数据 ──
const data = RANK_DATA;

// ── 更新头部 ──
document.getElementById('meta-date').textContent = '📅 数据至: ' + (data.summary.latest_date || '暂无');
document.getElementById('meta-records').textContent = '📊 总记录: ' + data.summary.total_records;
document.getElementById('meta-brands').textContent = '🏷️ 品牌: ' + data.summary.brand_count;

document.getElementById('card-total').textContent = data.summary.total_records;
document.getElementById('card-days').textContent = data.dates.length + '天';
document.getElementById('card-brands').textContent = data.summary.brand_count;
document.getElementById('card-latest').textContent = data.summary.latest_date || '-';

// ── 排名趋势图 ──
let trendChart = null;
const COLORS = ['#667eea','#e74c3c','#27ae60','#f39c12','#9b59b6',
                '#1abc9c','#e67e22','#3498db','#2ecc71','#e91e63'];

function renderTrendChart(source) {
  const ctx = document.getElementById('trendChart').getContext('2d');
  if (trendChart) trendChart.destroy();

  const labels = data.dates;
  const datasets = [];

  data.rankingTrend.forEach((item, i) => {
    const color = COLORS[i % COLORS.length];
    const label = item.brand + ' ' + item.model;
    // 从 rawData 中取每天的排名
    const ranks = labels.map(d => {
      const dayData = data.rawData[source] && data.rawData[source][d];
      if (!dayData) return null;
      const found = dayData.find(r => r.brand === item.brand);
      return found ? found.rank : null;
    });
    // 检查是否有有效数据
    if (ranks.some(r => r !== null)) {
      datasets.push({
        label: label,
        data: ranks,
        borderColor: color,
        backgroundColor: color + '20',
        tension: 0.3,
        pointRadius: 4,
        spanGaps: true,
      });
    }
  });

  trendChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { reverse: true, min: 0.5, max: 10.5,
             ticks: { stepSize: 1 },
             title: { display: true, text: '排名' } },
        x: { title: { display: true, text: '日期' } }
      },
      plugins: {
        legend: { position: 'bottom', labels: { padding: 20, usePointStyle: true } },
        tooltip: {
          callbacks: {
            label: ctx => ctx.raw ? `${ctx.dataset.label}: 第${ctx.raw}名` : '暂无数据'
          }
        }
      }
    }
  });
}

function switchChart(source) {
  document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  renderTrendChart(source);
}

// ── 最新排名表 ──
function renderLatestTable() {
  const latest = data.summary.latest_date;
  if (!latest || !data.rawData.pc[latest]) {
    document.getElementById('latest-table').innerHTML =
      '<tr><td colspan="6" style="text-align:center;color:#999;">暂无数据</td></tr>';
    return;
  }

  const rows = data.rawData.pc[latest]
    .sort((a,b) => a.rank - b.rank)
    .slice(0, 10);

  let html = '';
  rows.forEach(r => {
    const rankClass = r.rank <= 3 ? `rank-${r.rank}` : 'rank-other';
    const trendIcon = r.trend ? (r.trend.includes('上升') ? '📈' : r.trend.includes('降') ? '📉' : '🏆') : '➖';
    html += `<tr>
      <td><span class="rank-badge ${rankClass}">${r.rank}</span></td>
      <td><strong>${r.brand}</strong></td>
      <td>${r.model}</td>
      <td class="price">¥${r.price.toLocaleString()}</td>
      <td>${trendIcon} ${r.trend || ''}</td>
      <td>${r.sales_7d || '-'}</td>
    </tr>`;
  });
  document.getElementById('latest-table').innerHTML = html;
}

// ── 品牌榜 ──
function renderBrandTable() {
  const brands = data.brandRankings.slice(-10).reverse();
  if (brands.length === 0) {
    document.getElementById('brand-table').innerHTML =
      '<tr><td colspan="4" style="text-align:center;color:#999;">暂无数据</td></tr>';
    return;
  }
  let html = '';
  brands.forEach(r => {
    const rankClass = r.rank <= 3 ? `rank-${r.rank}` : 'rank-other';
    html += `<tr>
      <td><span class="rank-badge ${rankClass}">${r.rank}</span></td>
      <td><strong>${r.brand_cn}</strong> <small style="color:#999">${r.brand_en}</small></td>
      <td>${r.description || '-'}</td>
      <td class="price">${r.prices || '-'}</td>
    </tr>`;
  });
  document.getElementById('brand-table').innerHTML = html;
}

// ── 初始化 ──
renderTrendChart('pc');
renderLatestTable();
renderBrandTable();
</script>
</body>
</html>"""

    html_path = f"{OUTPUT_DIR}/index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html.strip())
    print(f"✅ HTML 页面: {html_path} ({os.path.getsize(html_path)} bytes)")
    return html_path


def main():
    print("╔════════════════════════════════════════╗")
    print("║   排行榜数据 → 可视化页面              ║")
    print(f"║   运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}      ║")
    print("╚════════════════════════════════════════╝")

    data = load_all_data()
    
    pc_days = len(data["pc"])
    mobile_days = len(data["mobile"])
    brand_days = len(data["brand"])
    print(f"📂 数据统计:")
    print(f"   PC端:   {sum(len(v) for v in data['pc'].values())} 条 / {pc_days} 天")
    print(f"   手机端: {sum(len(v) for v in data['mobile'].values())} 条 / {mobile_days} 天")
    print(f"   品牌榜: {sum(len(v) for v in data['brand'].values())} 条 / {brand_days} 天")

    js_path = generate_js_file(data)
    html_path = generate_html()
    
    print(f"\n✅ 生成完成！")
    print(f"   📄 {js_path}")
    print(f"   📄 {html_path}")
    print(f"\n🌐 在浏览器中打开 output/index.html 即可查看")
    print(f"   或在项目目录下运行: python3 -m http.server 8080")
    
    # Git commit after generation
    import subprocess
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=DATA_DIR
    )
    if result.stdout.strip():
        subprocess.run(["git", "add", "-A"], cwd=DATA_DIR)
        subprocess.run(["git", "commit", "-m", f"viz: 更新可视化页面 {datetime.now().strftime('%Y-%m-%d %H:%M')}", "--quiet"], cwd=DATA_DIR)
        print(f"\n📦 Git commit: 可视化页面已更新")


if __name__ == "__main__":
    main()
