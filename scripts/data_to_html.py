#!/usr/bin/env python3
"""
data_to_html.py — 排行榜数据 → 可视化 HTML 页面

读取 daily/ 目录下的所有 CSV/JSON 数据，生成：
  1. docs/ranking_15day_data.js — JS 数据文件（供 HTML 页面加载）
  2. docs/index.html           — 可视化趋势页面

用法:
  python3 scripts/data_to_html.py              # 生成最新页面
  python3 scripts/data_to_html.py --open       # 生成后启动本地服务器

输出:
  /workspace/rank_data/docs/ranking_15day_data.js
  /workspace/rank_data/docs/index.html
"""

import os, sys, json, glob, re
from datetime import datetime, date
from collections import defaultdict

sys.path.insert(0, "/workspace/rank_data/scripts")
from data_standards import SINGLE_RANK_FIELDS, BRAND_RANK_FIELDS

DATA_DIR = "/workspace/rank_data"
DAILY_DIR = f"{DATA_DIR}/daily"
DOCS_DIR = f"{DATA_DIR}/docs"


def load_all_data() -> dict:
    """加载所有日期的数据"""
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


def parse_sales_number(sales_str: str) -> int:
    """解析销量字符串为数字，如 '300+件' -> 300, '1000+' -> 1000, '1万+' -> 10000"""
    if not sales_str:
        return 0
    s = sales_str.strip()
    # 提取数字部分
    m = re.match(r'([\d.]+)(万)?', s)
    if not m:
        return 0
    num = float(m.group(1))
    if m.group(2) == '万':
        num *= 10000
    return int(num)


def estimate_daily_sales(record: dict) -> dict:
    """
    推测日销量

    优先级：7天销量 > 30天销量 > 年销量
    返回: {
        "value": 42,
        "range": "35-50",
        "source": "s7",  # s7/s30/sy
        "confidence": "ch"  # ch(高)/cm(中)/cl(低)
    }
    """
    s7 = parse_sales_number(record.get("sales_7d", ""))
    s30 = parse_sales_number(record.get("sales_30d", ""))

    if s7 > 0:
        daily = round(s7 / 7)
        lo = max(1, round(s7 / 7 * 0.7))
        hi = round(s7 / 7 * 1.3)
        # 7天数据置信度较高
        conf = "ch" if s7 >= 100 else "cm"
        return {"value": daily, "range": f"{lo}-{hi}", "source": "s7", "confidence": conf}

    if s30 > 0:
        daily = round(s30 / 30)
        lo = max(1, round(s30 / 30 * 0.6))
        hi = round(s30 / 30 * 1.4)
        conf = "cm" if s30 >= 300 else "cl"
        return {"value": daily, "range": f"{lo}-{hi}", "source": "s30", "confidence": conf}

    return {"value": 0, "range": "-", "source": "", "confidence": "cl"}


def build_15day_data(data: dict) -> dict:
    """
    构建用户 HTML 页面需要的 ranking_15day_data.js 格式

    数据结构：
    {
        dates: ["2026-06-01", ...],           // 最近15天日期
        latestDate: "2026-06-07",
        totalDays: 6,
        products: [                            // 产品列表（按最新日期排名排序）
            {
                brand: "GEMILAI",
                model: "双瞳商用咖啡机",
                image_url: "",
                price: 4599,
                coupon_price: "",
                est_daily: { value, range, source, confidence },
                rank_today: 1,
                rank_yesterday: 2,
                rank_change: -1,               // 负数=上升, 正数=下降
                best_rank: 1,
                avg_rank: 2.3,
                trend: [null, 2, 2, 1, 5, 5, 1],  // 15天排名，无数据为null
                sales_7d: "300+件",
                sales_30d: "",
            },
            ...
        ],
        stats: {
            total_products: 5,
            brand_count: 5,
            top1_brand: "GEMILAI",
            latest_date: "2026-06-07",
        }
    }
    """
    # 收集所有日期
    all_dates = set()
    for source in ["pc", "mobile"]:
        all_dates.update(data[source].keys())
    dates_sorted = sorted(all_dates)

    # 最近15天
    recent_15 = dates_sorted[-15:] if len(dates_sorted) > 15 else dates_sorted
    latest_date = dates_sorted[-1] if dates_sorted else ""

    # 构建品牌+型号维度的历史排名
    # key = "brand|model"，value = { date: rank }
    product_history = {}  # key -> { dates: {date: rank}, info: {brand, model, price, ...} }

    for source in ["pc", "mobile"]:
        for date_str in recent_15:
            if date_str not in data[source]:
                continue
            for r in data[source][date_str]:
                brand = r.get("brand", "")
                model = r.get("model", "")
                key = f"{brand}|{model}"

                if key not in product_history:
                    product_history[key] = {
                        "brand": brand,
                        "model": model,
                        "dates": {},
                        "latest_record": None,
                        "latest_date": "",
                    }

                product_history[key]["dates"][date_str] = r.get("rank", 0)

                # 保留最新日期的完整记录
                if date_str >= product_history[key]["latest_date"]:
                    product_history[key]["latest_date"] = date_str
                    product_history[key]["latest_record"] = r

    # 构建产品列表
    products = []
    for key, info in product_history.items():
        rec = info["latest_record"]
        if not rec:
            continue

        # 15天排名趋势
        trend = []
        for d in recent_15:
            trend.append(info["dates"].get(d, None))

        # 最新排名
        rank_today = rec.get("rank", 0)

        # 昨日排名（最近15天倒数第二天）
        yesterday = recent_15[-2] if len(recent_15) >= 2 else ""
        rank_yesterday = info["dates"].get(yesterday, None)

        # 排名变化（负数=上升，正数=下降）
        rank_change = 0
        if rank_yesterday is not None and rank_today > 0:
            rank_change = rank_today - rank_yesterday

        # 最佳排名
        valid_ranks = [r for r in info["dates"].values() if r > 0]
        best_rank = min(valid_ranks) if valid_ranks else 0

        # 平均排名（有数据取实际，无数据按35算）
        rank_sum = 0
        rank_count = 0
        for d in recent_15:
            r = info["dates"].get(d, None)
            if r is not None and r > 0:
                rank_sum += r
                rank_count += 1
            else:
                rank_sum += 35  # 无数据按35算
        rank_count = len(recent_15)
        avg_rank = round(rank_sum / rank_count, 1) if rank_count > 0 else 0

        # 推测日销量
        est = estimate_daily_sales(rec)

        products.append({
            "brand": rec.get("brand", ""),
            "model": rec.get("model", ""),
            "image_url": rec.get("image_url", ""),
            "price": rec.get("price", 0),
            "coupon_price": rec.get("coupon_price", ""),
            "est_daily": est,
            "rank_today": rank_today,
            "rank_yesterday": rank_yesterday,
            "rank_change": rank_change,
            "best_rank": best_rank,
            "avg_rank": avg_rank,
            "trend": trend,
            "sales_7d": rec.get("sales_7d", ""),
            "sales_30d": rec.get("sales_30d", ""),
            "trend_text": rec.get("trend", ""),
        })

    # 按最新排名排序
    products.sort(key=lambda x: x["rank_today"] if x["rank_today"] > 0 else 99)

    # 统计
    brands_seen = set(p["brand"] for p in products if p["brand"])
    top1_brand = products[0]["brand"] if products else ""

    stats = {
        "total_products": len(products),
        "brand_count": len(brands_seen),
        "top1_brand": top1_brand,
        "latest_date": latest_date,
    }

    return {
        "dates": recent_15,
        "latestDate": latest_date,
        "totalDays": len(dates_sorted),
        "products": products,
        "stats": stats,
    }


def build_brand_15day_data(data: dict) -> dict:
    """
    构建品牌榜15天动态数据，供 brand_ranking_15day.html 使用

    数据结构：
    {
        dates: ["2026-06-01", ...],
        latestDate: "2026-06-07",
        totalDays: 6,
        brands: [
            {
                brand: "Delonghi",
                rank_today: 1,
                rank_yesterday: 2,
                rank_change: -1,
                best_rank: 1,
                avg_rank: 2.3,
                trend: [null, null, null, null, null, 1],
                followers: "1万+人",
                trend_text: "热卖商品1万+件，1万+人购买",
                prices: "2990,4190,2940"
            },
            ...
        ],
        stats: { total_brands: 3, latest_date: "2026-06-07" }
    }
    """
    all_dates = sorted(data["brand"].keys())
    recent_15 = all_dates[-15:] if len(all_dates) > 15 else all_dates
    latest_date = all_dates[-1] if all_dates else ""

    # 构建品牌历史排名
    brand_history = {}
    for date_str in recent_15:
        if date_str not in data["brand"]:
            continue
        for r in data["brand"][date_str]:
            brand_en = r.get("brand_en", "")
            if not brand_en:
                continue
            key = brand_en
            if key not in brand_history:
                brand_history[key] = {
                    "brand": brand_en,
                    "brand_cn": r.get("brand_cn", ""),
                    "dates": {},
                    "latest_record": None,
                    "latest_date": "",
                }
            brand_history[key]["dates"][date_str] = r.get("rank", 0)
            if date_str >= brand_history[key]["latest_date"]:
                brand_history[key]["latest_date"] = date_str
                brand_history[key]["latest_record"] = r

    # 构建品牌列表
    brands = []
    for key, info in brand_history.items():
        rec = info["latest_record"]
        if not rec:
            continue

        # 15天趋势
        trend = [info["dates"].get(d, None) for d in recent_15]

        rank_today = rec.get("rank", 0)
        yesterday = recent_15[-2] if len(recent_15) >= 2 else ""
        rank_yesterday = info["dates"].get(yesterday, None)

        rank_change = 0
        if rank_yesterday is not None and rank_today > 0:
            rank_change = rank_today - rank_yesterday

        valid_ranks = [r for r in info["dates"].values() if r > 0]
        best_rank = min(valid_ranks) if valid_ranks else 0

        rank_sum = 0
        for d in recent_15:
            r = info["dates"].get(d, None)
            rank_sum += r if (r is not None and r > 0) else 25
        avg_rank = round(rank_sum / len(recent_15), 1)

        # 趋势文字和关注人数解析
        trend_text = rec.get("description", "")
        followers = rec.get("followers", "")
        if not followers and trend_text:
            # 从描述中提取关注人数信息
            import re
            m = re.search(r'([\d万+]+人)', trend_text)
            if m:
                followers = m.group(1)

        brands.append({
            "brand": rec.get("brand_en", ""),
            "brand_cn": rec.get("brand_cn", ""),
            "rank_today": rank_today,
            "rank_yesterday": rank_yesterday,
            "rank_change": rank_change,
            "best_rank": best_rank,
            "avg_rank": avg_rank,
            "trend": trend,
            "followers": followers,
            "trend_text": trend_text,
            "prices": rec.get("prices", ""),
        })

    brands.sort(key=lambda x: x["rank_today"] if x["rank_today"] > 0 else 99)

    stats = {
        "total_brands": len(brands),
        "latest_date": latest_date,
    }

    return {
        "dates": recent_15,
        "latestDate": latest_date,
        "totalDays": len(all_dates),
        "brands": brands,
        "stats": stats,
    }


def generate_js_file(data):
    """生成 ranking_15day_data.js + brand_ranking_15day_data.js"""
    result_15day = build_15day_data(data)
    brand_15day = build_brand_15day_data(data)

    # 单页JS数据
    all_dates = set()
    for source in ["pc", "mobile", "brand"]:
        all_dates.update(data[source].keys())
    dates_sorted = sorted(all_dates)
    brands_seen = set()
    for source in ["pc", "mobile"]:
        for date_str, records in data[source].items():
            for r in records:
                brands_seen.add(r.get("brand", ""))

    summary = {
        "latest_date": result_15day["latestDate"],
        "total_records": sum(len(p["trend"]) for p in result_15day["products"]),
        "brand_count": len(brands_seen),
        "top5": result_15day["products"][:5],
    }

    js_content = f"""// 排行榜数据 — 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}
// 请勿手动修改，运行 python3 scripts/data_to_html.py 更新

const RANKING_15DAY = {json.dumps(result_15day, ensure_ascii=False, indent=2)};

// 兼容旧格式
const RANK_DATA = {{
    summary: {json.dumps(summary, ensure_ascii=False, indent=2)},
    dates: {json.dumps(dates_sorted, ensure_ascii=False)},
    rawData: {json.dumps(data, ensure_ascii=False, indent=2)},
}};
"""

    brand_js_content = f"""// 品牌榜数据 — 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}
// 请勿手动修改，运行 python3 scripts/data_to_html.py 更新

const BRAND_RANKING_15DAY = {json.dumps(brand_15day, ensure_ascii=False, indent=2)};
"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    
    js_path = f"{DOCS_DIR}/ranking_15day_data.js"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content.strip())
    print(f"✅ JS 数据: {js_path} ({os.path.getsize(js_path)} bytes)")

    brand_js_path = f"{DOCS_DIR}/brand_ranking_15day_data.js"
    with open(brand_js_path, "w", encoding="utf-8") as f:
        f.write(brand_js_content.strip())
    print(f"✅ 品牌JS数据: {brand_js_path} ({os.path.getsize(brand_js_path)} bytes)")

    return js_path


def generate_html():
    """生成可视化 HTML 页面（使用用户设计的页面）"""

    html_path = f"{DOCS_DIR}/index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(_get_index_html())
    print(f"✅ HTML 页面: {html_path} ({os.path.getsize(html_path)} bytes)")
    return html_path


def _get_index_html() -> str:
    """返回完整的 index.html 内容"""
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>天猫商用咖啡机热销榜 - 15天动态追踪</title>
<script src="ranking_15day_data.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5;color:#333}
.header{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:20px;text-align:center;position:relative}
.header .back-link{position:absolute;left:20px;top:20px;color:#90caf9;text-decoration:none;font-size:.85em}
.header .back-link:hover{text-decoration:underline}
.header h1{font-size:1.3em;margin-bottom:4px}
.header .sub{font-size:.82em;opacity:.7}
.container{max-width:1400px;margin:0 auto;padding:12px}
.stats-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:15px 0}
.stat-card{background:#fff;border-radius:10px;padding:14px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.stat-card .stat-value{font-size:1.5em;font-weight:700;color:#1a1a2e}
.stat-card .stat-label{font-size:.75em;color:#888;margin-top:2px}
.stat-card.wigomat{border:2px solid #4caf50}
.stat-card.wigomat .stat-value{color:#2e7d32}

/* 顶部前三名展示区 */
.top3-showcase{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:20px 0}
.top3-card{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);text-align:center;padding-bottom:18px;position:relative;transition:transform .2s,box-shadow .2s}
.top3-card:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.12)}
.top3-card .rank-num{position:absolute;top:12px;left:12px;width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;font-size:1em;z-index:2;box-shadow:0 2px 6px rgba(0,0,0,.2)}
.top3-card.rank1 .rank-num{background:linear-gradient(135deg,#e65100,#ff8f00)}
.top3-card.rank2 .rank-num{background:linear-gradient(135deg,#bf360c,#e65100)}
.top3-card.rank3 .rank-num{background:linear-gradient(135deg,#4e342e,#8d6e63)}
.top3-card .top3-img-wrap{padding:28px 16px;background:#fafafa;min-height:230px;display:flex;align-items:center;justify-content:center}
.top3-card .top3-img{width:100%;max-width:200px;height:200px;object-fit:contain;display:block}
.top3-card .top3-brand{font-size:.82em;color:#888;margin-top:14px}
.top3-card .top3-brand strong{color:#555}
.top3-card .top3-model{font-weight:600;color:#1a1a2e;margin-top:4px;font-size:.92em}
.top3-card.wigomat-card .top3-brand strong,.top3-card.wigomat-card .top3-model{color:#2e7d32}
.top3-card .top3-price{color:#c62828;font-weight:600;margin-top:6px;font-size:1em}
.top3-card .top3-sales{font-size:.78em;color:#e65100;margin-top:5px;display:inline-block;background:#fff3e0;padding:2px 10px;border-radius:10px;font-weight:600}

.data-section{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);margin-bottom:20px}
.data-section .section-title{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:14px 16px;font-size:1em;font-weight:600}
.table-wrap{overflow-x:auto}
.data-table{width:100%;border-collapse:collapse;font-size:.94em}
.data-table th{background:#f0f2f5;padding:10px 8px;text-align:left;font-weight:600;color:#555;border-bottom:2px solid #ddd;white-space:nowrap;font-size:1.02em;position:relative}
.data-table td{padding:8px;border-bottom:1px solid #eee;vertical-align:middle}
.data-table tr:nth-child(even){background:#fafafa}
.data-table tr:hover{background:#f0f7ff}
.data-table .wigomat-row{background:#e8f5e9!important}
.data-table .wigomat-row:hover{background:#c8e6c9!important}
.rank-badge{display:inline-block;width:28px;height:28px;line-height:28px;border-radius:50%;text-align:center;font-size:.78em;font-weight:700;color:#fff}
.rank-badge.top3{width:36px;height:36px;line-height:36px;font-size:.9em}
.rank-badge.r1{background:linear-gradient(135deg,#e65100,#ff8f00)}
.rank-badge.r2{background:linear-gradient(135deg,#bf360c,#e65100)}
.rank-badge.r3{background:linear-gradient(135deg,#4e342e,#8d6e63)}
.rank-badge.rn{background:#9e9e9e}

/* 图片：1-3名用大图120x120，4-30用中图104x104 */
.img-top3{width:120px;height:120px;object-fit:contain;border-radius:8px;background:#f5f5f5;border:2px solid #e65100;vertical-align:middle;margin-right:6px}
.img-medium{width:104px;height:104px;object-fit:contain;border-radius:8px;background:#f5f5f5;border:1px solid #eee;vertical-align:middle;margin-right:6px}

.up{color:#2e7d32;font-weight:700}
.down{color:#c62828;font-weight:700}
.same{color:#888}
.price-cell{color:#c62828;font-weight:600;white-space:nowrap}
.best-cell{font-weight:600;color:#1a1a2e}
.avg-cell{font-weight:500;color:#555}

/* 初始列宽 */
.data-table th:nth-child(1),.data-table td:nth-child(1){text-align:center}
.data-table th:nth-child(2),.data-table td:nth-child(2){text-align:center}
.data-table th:nth-child(6),.data-table td:nth-child(6){text-align:center}
.data-table th:nth-child(7),.data-table td:nth-child(7){text-align:center}
.data-table th:nth-child(8),.data-table td:nth-child(8){text-align:center}
.data-table th:nth-child(9),.data-table td:nth-child(9){text-align:center}
.data-table th:nth-child(5){text-align:center}
.data-table th:nth-child(4){white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.data-table td:nth-child(4){white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

.sparkline-cell svg{display:inline-block}
.tooltip{position:relative;cursor:pointer;display:inline-block}
.tooltip .tip-text{visibility:hidden;position:absolute;background:#333;color:#fff;padding:4px 8px;border-radius:4px;font-size:.75em;white-space:nowrap;z-index:10;bottom:100%;left:50%;transform:translateX(-50%);opacity:0;transition:opacity .2s}
.tooltip:hover .tip-text{visibility:visible;opacity:1}

/* 拖拽手柄 */
.resize-handle{position:absolute;top:0;right:-3px;width:8px;height:100%;cursor:col-resize;z-index:10}
.resize-handle:after{content:'';position:absolute;top:25%;left:3px;width:2px;height:50%;background:transparent;border-radius:1px;transition:background .15s}
.resize-handle:hover:after,.resizing .resize-handle:after{background:#999}
.resizing{user-select:none!important}

.footer{background:#1a1a2e;color:#aaa;text-align:center;padding:20px;margin-top:20px;font-size:.8em}
.footer a{color:#90caf9;text-decoration:none;margin:0 6px}
.footer a:hover{text-decoration:underline}
.footer .footer-title{color:#ccc;font-weight:600;margin-bottom:8px}
.footer .footer-note{font-size:.75em;color:#666;margin-top:6px}
.filter-bar{display:flex;flex-wrap:wrap;gap:8px;padding:12px 16px;background:#fff;border-bottom:1px solid #eee;align-items:center}
.filter-bar label{font-size:.82em;color:#555;margin-right:4px}
.filter-bar select,.filter-bar input{padding:4px 10px;border:1px solid #ddd;border-radius:6px;font-size:.82em;background:#fff;cursor:pointer}
.filter-bar select{min-width:120px}
.filter-bar input{cursor:text}
.filter-bar .refresh-btn{padding:4px 14px;background:#1a1a2e;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:.8em}
.filter-bar .refresh-btn:hover{background:#2a2a4e}
.empty-cell{color:#ccc;font-size:.75em}
.wigomat-badge{display:inline-block;background:#4caf50;color:#fff;font-size:.68em;padding:1px 6px;border-radius:8px;margin-left:4px}

/* 推测日销列 */
.est-daily{text-align:center;white-space:nowrap;font-weight:600}
.est-daily .est-value{font-size:.92em}
.est-daily .est-range{display:block;font-size:.65em;font-weight:400;color:#888;margin-top:1px}
.est-badge{display:inline-block;padding:1px 5px;border-radius:4px;font-size:.65em;font-weight:400;color:#fff;margin-left:2px;vertical-align:middle}
.est-badge.ch{background:#2e7d32}
.est-badge.cm{background:#e65100}
.est-badge.cl{background:#c62828}
.est-badge.s7{background:#e65100}
.est-badge.s30{background:#1565c0}
.est-badge.sy{background:#7b1fa2}
.est-tip{position:relative;cursor:help}
.est-tip .tip-text{visibility:hidden;position:absolute;background:#333;color:#fff;padding:6px 10px;border-radius:6px;font-size:.72em;white-space:normal;z-index:20;bottom:110%;left:50%;transform:translateX(-50%);opacity:0;transition:opacity .2s;width:220px;text-align:left;line-height:1.5}
.est-tip:hover .tip-text{visibility:visible;opacity:1}

.list-subtitle{display:flex;align-items:center;gap:8px;padding:10px 16px;background:#fff;border-bottom:1px solid #f0f0f0;font-size:.88em;color:#555;font-weight:600}
.list-subtitle .trophy{color:#e65100;font-size:1.1em}
.list-subtitle .top-label{color:#888;font-weight:400;font-size:.85em}

@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.top3-card{animation:fadeIn .4s ease-out}
.top3-card:nth-child(2){animation-delay:.1s}
.top3-card:nth-child(3){animation-delay:.2s}

@media(max-width:768px){
 .top3-showcase{grid-template-columns:1fr}
 .top3-card .top3-img{max-width:160px;height:160px}
 .img-top3{width:80px;height:80px}
 .img-medium{width:64px;height:64px}
 .data-table{font-size:.87em}
 .data-table td,.data-table th{padding:4px 2px}
}
</style>
</head>
<body>
<div class="header">
<a href="index.html" class="back-link">← 返回主页</a>
<h1>☕ 天猫商用咖啡机热销榜 - 15天动态追踪</h1>
<div class="sub">数据来源：天猫热销榜TOP30 | 每日自动采集 | PC+手机双端数据整合 | 品牌维度型号标准化 | 仅更新数据文件不变页面</div>
</div>
<div class="container">
<div id="statsRow" class="stats-row"></div>
<div id="top3Showcase" class="top3-showcase"></div>
<div class="data-section">
<div class="section-title">📊 品牌排名动态表（TOP30 · <span id="dayCount">15</span>天趋势）</div>
<div class="filter-bar">
<label for="dateFilter">显示日期:</label>
<select id="dateFilter"></select>
<span style="margin:0 8px;color:#ddd">|</span>
<label for="brandFilter">品牌筛选:</label>
<input type="text" id="brandFilter" placeholder="输入品牌名..." style="width:130px">
<button class="refresh-btn" id="refreshBtn">🔍 刷新</button>
</div>
<div class="list-subtitle"><span class="trophy">🏆</span> 全部榜单 <span class="top-label">TOP 30</span></div>
<div class="table-wrap">
<table class="data-table" id="mainTable">
<thead>
<tr>
<th>排名</th>
<th>商品图</th>
<th>品牌</th>
<th>型号</th>
<th>价格</th>
<th class="est-daily"><span class="tooltip">推测日销<span class="tip-text">基于7天/30天销量数据推算，数据越多越准确</span></span></th>
<th>较昨日</th>
<th>最佳排名</th>
<th><span class="tooltip">平均排名<span class="tip-text">有数据的取实际排名，无数据的按35计算</span></span></th>
<th class="sparkline-cell">15天日变动曲线</th>
</tr>
</thead>
<tbody id="tableBody"></tbody>
</table>
</div>
</div>
</div>
<div class="footer">
<div class="footer-title">🔗 关联文档</div>
<a href="index.html">首页</a> |
<a href="https://github.com/poonee/tmall-rank-data">GitHub 数据仓库</a>
<br><br>
数据文件：<code style="color:#aaa;font-size:.85em">ranking_15day_data.js</code> |
抓取新数据后更新此文件即可，页面结构不变
<br>
<span id="footerInfo" style="font-size:.85em"></span>
</div>

<script>
(function() {
    'use strict';

    const D = RANKING_15DAY;
    if (!D || !D.products) {
        document.getElementById('tableBody').innerHTML =
            '<tr><td colspan="10" style="text-align:center;padding:40px;color:#999">暂无数据</td></tr>';
        return;
    }

    // ── 统计卡片 ──
    function renderStats() {
        const stats = D.stats;
        const top1 = D.products.find(p => p.rank_today === 1);
        const html = `
            <div class="stat-card${top1 && top1.brand === 'wigomat' ? ' wigomat' : ''}">
                <div class="stat-value">${stats.total_products}</div><div class="stat-label">在榜产品</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.brand_count}</div><div class="stat-label">品牌数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.latest_date || '-'}</div><div class="stat-label">最新日期</div>
            </div>
            <div class="stat-card${top1 && top1.brand === 'wigomat' ? ' wigomat' : ''}">
                <div class="stat-value">${top1 ? top1.brand : '-'}</div><div class="stat-label">当前榜首</div>
            </div>
        `;
        document.getElementById('statsRow').innerHTML = html;
    }

    // ── Top3 展示区 ──
    function renderTop3() {
        const top3 = D.products.slice(0, 3);
        if (!top3.length) return;
        let html = '';
        top3.forEach((p, i) => {
            const rankClass = 'rank' + (i + 1);
            const isWigomat = p.brand === 'wigomat';
            const imgHtml = p.image_url
                ? '<img class="top3-img" src="' + p.image_url + '" alt="' + p.brand + '">'
                : '<div style="width:200px;height:200px;display:flex;align-items:center;justify-content:center;color:#ccc;font-size:3em">☕</div>';
            html += '<div class="top3-card ' + rankClass + (isWigomat ? ' wigomat-card' : '') + '">' +
                '<div class="rank-num">' + p.rank_today + '</div>' +
                '<div class="top3-img-wrap">' + imgHtml + '</div>' +
                '<div class="top3-brand"><strong>' + p.brand + '</strong>' + (isWigomat ? '<span class="wigomat-badge">⭐</span>' : '') + '</div>' +
                '<div class="top3-model">' + p.model + '</div>' +
                '<div class="top3-price">¥' + p.price.toLocaleString() + '</div>' +
                (p.sales_7d ? '<div class="top3-sales">7天 ' + p.sales_7d + '</div>' : '') +
                '</div>';
        });
        document.getElementById('top3Showcase').innerHTML = html;
    }

    // ── 日期筛选器 ──
    function renderDateFilter() {
        const sel = document.getElementById('dateFilter');
        const dates = D.dates || [];
        // 从最新到最旧
        for (let i = dates.length - 1; i >= 0; i--) {
            const opt = document.createElement('option');
            opt.value = dates[i];
            opt.textContent = dates[i];
            if (dates[i] === D.latestDate) opt.selected = true;
            sel.appendChild(opt);
        }
    }

    // ── Sparkline SVG 生成 ──
    function makeSparkline(trend, w, h) {
        w = w || 120; h = h || 32;
        const valid = trend.filter(v => v !== null && v !== undefined);
        if (valid.length < 2) return '<span class="empty-cell">数据不足</span>';

        const maxR = Math.max(...valid);
        const minR = Math.min(...valid);
        const range = maxR - minR || 1;
        const pad = 3;

        const points = [];
        const step = (w - 2 * pad) / Math.max(trend.length - 1, 1);
        trend.forEach((v, i) => {
            if (v === null || v === undefined) {
                points.push(null);
            } else {
                const x = pad + i * step;
                const y = pad + ((v - minR) / range) * (h - 2 * pad);
                points.push(x + ',' + y.toFixed(1));
            }
        });

        // 连线（跳过 null）
        let pathD = '';
        let lastValid = null;
        points.forEach((p, i) => {
            if (p === null) return;
            if (lastValid === null) {
                pathD += 'M' + p;
            } else {
                pathD += 'L' + p;
            }
            lastValid = i;
        });

        // 最后一个有效点加圆点
        let dot = '';
        for (let i = points.length - 1; i >= 0; i--) {
            if (points[i] !== null) {
                dot = '<circle cx="' + points[i].split(',')[0] + '" cy="' + points[i].split(',')[1] + '" r="2.5" fill="#e65100"/>';
                break;
            }
        }

        return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '">' +
            '<path d="' + pathD + '" fill="none" stroke="#e65100" stroke-width="1.5"/>' +
            dot + '</svg>';
    }

    // ── 排名变化显示 ──
    function renderRankChange(change) {
        if (change === 0 || change === null || change === undefined) return '<span class="same">-</span>';
        if (change < 0) return '<span class="up">↑' + Math.abs(change) + '</span>';
        return '<span class="down">↓' + change + '</span>';
    }

    // ── 推测日销显示 ──
    function renderEstDaily(est) {
        if (!est || est.value === 0) return '<span class="empty-cell">-</span>';
        const srcBadge = est.source ? '<span class="est-badge ' + est.source + '">' +
            ({s7:'7天',s30:'30天',sy:'年'}[est.source] || est.source) + '</span>' : '';
        const confBadge = est.confidence ? '<span class="est-badge ' + est.confidence + '">' +
            ({ch:'高',cm:'中',cl:'低'}[est.confidence] || est.confidence) + '</span>' : '';
        return '<span class="est-value">' + est.value + '</span>' +
               '<span class="est-range">' + est.range + '/日</span>' +
               srcBadge + confBadge;
    }

    // ── 主表格 ──
    function renderTable() {
        const selectedDate = document.getElementById('dateFilter').value || D.latestDate;
        const brandFilter = (document.getElementById('brandFilter').value || '').toLowerCase();

        let products = D.products;
        if (brandFilter) {
            products = products.filter(p =>
                p.brand.toLowerCase().includes(brandFilter) ||
                p.model.toLowerCase().includes(brandFilter)
            );
        }

        let html = '';
        products.forEach((p, idx) => {
            const isWigomat = p.brand === 'wigomat';
            const rowClass = isWigomat ? 'wigomat-row' : '';
            const rankClass = p.rank_today <= 3 ? 'r' + p.rank_today : 'rn';
            const badgeExtra = p.rank_today <= 3 ? ' top3' : '';

            // 商品图
            const imgClass = p.rank_today <= 3 ? 'img-top3' : 'img-medium';
            const imgHtml = p.image_url
                ? '<img class="' + imgClass + '" src="' + p.image_url + '" alt="' + p.brand + '">'
                : '<span style="color:#ccc;font-size:1.5em">☕</span>';

            html += '<tr class="' + rowClass + '">' +
                '<td><span class="rank-badge' + badgeExtra + ' ' + rankClass + '">' + p.rank_today + '</span></td>' +
                '<td>' + imgHtml + '</td>' +
                '<td><strong>' + p.brand + '</strong>' + (isWigomat ? '<span class="wigomat-badge">⭐</span>' : '') + '</td>' +
                '<td title="' + p.model + '">' + p.model + '</td>' +
                '<td class="price-cell">¥' + p.price.toLocaleString() + '</td>' +
                '<td class="est-daily">' + renderEstDaily(p.est_daily) + '</td>' +
                '<td>' + renderRankChange(p.rank_change) + '</td>' +
                '<td class="best-cell">' + p.best_rank + '</td>' +
                '<td class="avg-cell">' + p.avg_rank + '</td>' +
                '<td class="sparkline-cell">' + makeSparkline(p.trend) + '</td>' +
                '</tr>';
        });

        if (!html) {
            html = '<tr><td colspan="10" style="text-align:center;padding:30px;color:#999">无匹配数据</td></tr>';
        }

        document.getElementById('tableBody').innerHTML = html;
        document.getElementById('dayCount').textContent = D.dates.length;
    }

    // ── 列宽拖拽 ──
    function initColumnResize() {
        const table = document.getElementById('mainTable');
        const ths = table.querySelectorAll('thead th');
        ths.forEach((th, colIdx) => {
            const handle = document.createElement('div');
            handle.className = 'resize-handle';
            th.appendChild(handle);

            let startX, startW;
            handle.addEventListener('mousedown', e => {
                startX = e.pageX;
                startW = th.offsetWidth;
                document.body.classList.add('resizing');

                const onMove = ev => {
                    const diff = ev.pageX - startX;
                    th.style.width = Math.max(40, startW + diff) + 'px';
                    th.style.minWidth = th.style.width;
                };
                const onUp = () => {
                    document.body.classList.remove('resizing');
                    document.removeEventListener('mousemove', onMove);
                    document.removeEventListener('mouseup', onUp);
                };
                document.addEventListener('mousemove', onMove);
                document.addEventListener('mouseup', onUp);
                e.preventDefault();
            });
        });
    }

    // ── 页脚信息 ──
    function renderFooter() {
        const el = document.getElementById('footerInfo');
        if (el && D.stats) {
            el.textContent = '数据更新至 ' + (D.stats.latest_date || '-') +
                ' | 共 ' + D.stats.total_products + ' 个产品在榜' +
                ' | 累计采集 ' + D.totalDays + ' 天';
        }
    }

    // ── 初始化 ──
    renderStats();
    renderTop3();
    renderDateFilter();
    renderTable();
    initColumnResize();
    renderFooter();

    // 事件绑定
    document.getElementById('refreshBtn').addEventListener('click', renderTable);
    document.getElementById('brandFilter').addEventListener('input', renderTable);
    document.getElementById('dateFilter').addEventListener('change', function() {
        // 切换日期时可以重新排序（暂只筛选品牌）
        renderTable();
    });

})();
</script>
</body>
</html>'''


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
    print(f"\n🌐 页面:")
    print(f"   📄 单品排名: https://poonee.github.io/tmall-rank-data/")
    print(f"   📄 品牌排行: https://poonee.github.io/tmall-rank-data/brand_ranking_15day.html")
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
