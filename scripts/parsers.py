"""
parsers.py — 排行榜原始文本解析器

支持解析三种数据源的文本格式：
  1. PC端单品榜（TOP格式）
  2. 手机端单品榜（手机版格式）
  3. 品牌榜（品牌格式）

用法:
    from parsers import parse_pc_rank, parse_mobile_rank, parse_brand_rank
    records = parse_pc_rank(raw_text)
"""

import re
from datetime import date
from typing import Optional

# ═══════════════════════════════════════════════════
# 品牌名标准化
# ═══════════════════════════════════════════════════

BRAND_NORMALIZE_MAP = {
    "wigomat唯咖美": "wigomat",
    "wigomat": "wigomat",
    "唯咖美": "wigomat",
    "Delonghi德龙": "Delonghi",
    "Delonghi": "Delonghi",
    "德龙": "Delonghi",
    "GEMILAI格米莱": "GEMILAI",
    "GEMILAI": "GEMILAI",
    "格米莱": "GEMILAI",
    "Petrus柏翠": "Petrus",
    "Petrus": "Petrus",
    "柏翠": "Petrus",
    "Barsetto百胜图": "Barsetto",
    "Barsetto": "Barsetto",
    "百胜图": "Barsetto",
    "Hauswirt海氏": "Hauswirt",
    "Hauswirt": "Hauswirt",
    "海氏": "Hauswirt",
    "Stelang雪特朗": "Stelang",
    "Stelang": "Stelang",
    "雪特朗": "Stelang",
    "Breville铂富": "Breville",
    "Breville": "Breville",
    "铂富": "Breville",
    "Welhome惠家": "Welhome",
    "Welhome": "Welhome",
    "惠家": "Welhome",
    "Westinghouse西屋": "Westinghouse",
    "Westinghouse": "Westinghouse",
    "西屋": "Westinghouse",
    "NESPRESSO奈斯派索": "NESPRESSO",
    "NESPRESSO": "NESPRESSO",
    "奈斯派索": "NESPRESSO",
    "LA MARZOCCO": "La Marzocco",
    "LELIT": "Lelit",
    "技诺": "技诺",
    "温豆季": "温豆季",
    "突尼": "突尼",
    "咖博士": "咖博士",
    "德颐": "德颐",
    "咖乐美": "咖乐美",
}

# 按长度降序排列，优先匹配复合名称（如 "Delonghi德龙" 先于 "德龙"）
_BRAND_KEYS = sorted(BRAND_NORMALIZE_MAP.keys(), key=len, reverse=True)


def extract_brand(text: str) -> tuple[str, str]:
    """从文本中提取品牌名，返回 (标准化品牌, 去除品牌后的剩余文本)"""
    for key in _BRAND_KEYS:
        if key in text:
            std = BRAND_NORMALIZE_MAP[key]
            remaining = text.replace(key, "", 1).strip()
            return std, remaining
    return "", text


def clean_model(text: str) -> str:
    """清理型号文本：去掉多余的标点和分期信息"""
    # 去掉末尾的 .。.… 和分期信息
    text = re.sub(r'[\.。…]+$', '', text)
    text = re.sub(r'\d+期免息.*$', '', text)
    text = re.sub(r'\s+', '', text)
    # 去掉末尾标点
    text = text.strip('.,;:。，；：、...…')
    return text.strip()


# ═══════════════════════════════════════════════════
# PC端解析器
# ═══════════════════════════════════════════════════
# 格式: TOP{rank}{趋势标签}值得买近7天销售{销量}+件{brand}{model}¥{price}{分期}
# 价格截断: 若 ¥数字 >20000, 逐位截断至 <20000（处理 "¥45996期免息"）
# ═══════════════════════════════════════════════════

def correct_price(raw_price: int) -> int:
    """价格截断：如果 >20000, 逐位截断"""
    s = str(raw_price)
    while raw_price > 20000 and len(s) > 3:
        s = s[:-1]
        if s:
            raw_price = int(s)
    return raw_price


PC_TREND_PATTERNS = [
    r"蝉联榜首\d+周", r"蝉联榜首", r"霸榜前三", r"霸榜",
    r"排名上升\d+位", r"排名上升", r"排名下降\d+位",
    r"销量飙升", r"新品上榜", r"热度飙升", r"榜单新秀",
]


def _parse_pc_line(line: str, today: str) -> Optional[dict]:
    """解析单行PC端排行榜文本"""
    line = line.strip()
    if not line or "TOP" not in line:
        return None

    # --- 排名 ---
    rank_match = re.search(r"TOP(\d+)", line)
    if not rank_match:
        return None
    rank = int(rank_match.group(1))

    # --- 趋势 ---
    trend = ""
    for pat in PC_TREND_PATTERNS:
        m = re.search(pat, line)
        if m:
            trend = m.group(0)
            break

    # --- 近7天销量 ---
    sales_7d = ""
    sales_match = re.search(r"近7天销售([\d+~]+件)", line)
    if sales_match:
        sales_7d = sales_match.group(1)

    # --- 价格 ---
    price = 0
    price_match = re.search(r"¥(\d+)", line)
    if price_match:
        raw_price = int(price_match.group(1))
        price = correct_price(raw_price)

    # --- 品牌 & 型号 ---
    # 去掉已解析的前缀部分，保留产品名部分
    clean = line
    clean = re.sub(r"TOP\d+", "", clean)
    for pat in PC_TREND_PATTERNS:
        clean = re.sub(pat, "", clean)
    clean = re.sub(r"值得买", "", clean)
    clean = re.sub(r"近7天销售[\d+~]+件", "", clean)
    clean = re.sub(r"¥\d+.*$", "", clean).strip()

    brand, model_text = extract_brand(clean)
    model = clean_model(model_text)

    return {
        "date": today,
        "source": "pc",
        "rank": rank,
        "brand": brand,
        "model": model,
        "price": price,
        "coupon_price": "",
        "sales_7d": sales_7d,
        "sales_30d": "",
        "trend": trend,
        "image_url": "",
        "raw_text": line[:200],
    }


def parse_pc_rank(raw_text: str) -> list[dict]:
    """解析PC端排行榜完整文本"""
    today = date.today().isoformat()
    records = []
    for line in raw_text.split("\n"):
        if "TOP" in line:
            rec = _parse_pc_line(line, today)
            if rec:
                records.append(rec)
    return records


# ═══════════════════════════════════════════════════
# 手机端解析器
# ═══════════════════════════════════════════════════
# 排名1-3: 趋势标签 + 产品名 + ¥price券后¥coupon
# 排名4-30: 数字行 + 产品名行 + 销量行
# ═══════════════════════════════════════════════════

MOBILE_TREND_PATTERNS = [
    r"蝉联榜首\d+周", r"蝉联榜首", r"霸榜前三", r"霸榜",
    r"排名上升\d+位", r"排名上升", r"销量飙升", r"新品上榜",
    r"火爆热卖",
]

# 手机端趋势标签（用于识别排名1-3）
MOBILE_TREND_KEYWORDS = ["蝉联", "霸榜", "排名上升", "销量飙升", "新品上榜", "火爆热卖"]


def _is_trend_line(line: str) -> bool:
    """判断一行是否包含趋势标签"""
    for kw in MOBILE_TREND_KEYWORDS:
        if kw in line:
            return True
    return False


def _has_price(line: str) -> bool:
    """判断一行是否包含价格信息"""
    return "¥" in line


def _is_rank_number(line: str) -> bool:
    """判断一行是否为纯数字排名行"""
    line = line.strip()
    return bool(re.match(r"^\d{1,2}$", line)) and 4 <= int(line) <= 99


def _extract_mobile_item(text: str) -> dict:
    """从手机端产品行提取信息"""
    price = 0
    coupon_price = ""
    sales_7d = ""
    sales_30d = ""
    trend = ""

    # 趋势
    for pat in MOBILE_TREND_PATTERNS:
        m = re.search(pat, text)
        if m:
            trend = m.group(0)
            break

    # 价格
    price_match = re.search(r"¥(\d+)", text)
    if price_match:
        price = int(price_match.group(1))

    # 券后价
    coupon_match = re.search(r"券后¥(\d+)", text)
    if coupon_match:
        coupon_price = coupon_match.group(1)

    # 销量
    s7 = re.search(r"近7天销售([\d+~]+件)", text)
    if s7:
        sales_7d = s7.group(1)
    s30 = re.search(r"近30天内销量([\d+~]+)", text)
    if s30:
        sales_30d = s30.group(1)

    # 品牌型号
    clean = text
    for pat in MOBILE_TREND_PATTERNS:
        clean = re.sub(pat, "", clean)
    clean = re.sub(r"¥\d+.*$", "", clean).strip()

    brand, model_text = extract_brand(clean)
    model = clean_model(model_text)

    return {
        "price": price,
        "coupon_price": coupon_price,
        "sales_7d": sales_7d,
        "sales_30d": sales_30d,
        "trend": trend,
        "brand": brand,
        "model": model,
        "raw_text": text[:200],
    }


def parse_mobile_rank(raw_text: str) -> list[dict]:
    """解析手机端排行榜完整文本"""
    today = date.today().isoformat()
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    records = []
    rank = 1
    i = 0

    while i < len(lines) and rank <= 30:
        line = lines[i]

        # ── 排名1-3：趋势行或直接产品行 ──
        if rank <= 3:
            # 检查是否是排名数字行（非1-3区域出现数字行则跳到后面的逻辑）
            if _is_rank_number(line):
                rank = int(line)
                i += 1
                continue

            # 这行是产品信息
            if _has_price(line):
                info = _extract_mobile_item(line)
                records.append({
                    "date": today, "source": "mobile",
                    "rank": rank,
                    **info
                })
                # 检查下几行是否有销量数据
                for j in range(i+1, min(i+3, len(lines))):
                    s7 = re.search(r"近7天销售([\d+~]+件)", lines[j])
                    s30 = re.search(r"近30天内销量([\d+~]+)", lines[j])
                    if s7:
                        records[-1]["sales_7d"] = s7.group(1)
                    if s30:
                        records[-1]["sales_30d"] = s30.group(1)
                rank += 1
            i += 1
            continue

        # ── 排名4-30：数字行 + 产品行 ──
        if _is_rank_number(line):
            rank = int(line)
            i += 1
            # 下一行应该是产品行
            if i < len(lines) and _has_price(lines[i]):
                info = _extract_mobile_item(lines[i])
                records.append({
                    "date": today, "source": "mobile",
                    "rank": rank,
                    **info
                })
                # 再下一行可能有销量
                if i + 1 < len(lines):
                    s7 = re.search(r"近7天销售([\d+~]+件)", lines[i+1])
                    s30 = re.search(r"近30天内销量([\d+~]+)", lines[i+1])
                    if s7:
                        records[-1]["sales_7d"] = s7.group(1)
                    if s30:
                        records[-1]["sales_30d"] = s30.group(1)
                rank += 1
        i += 1

    return records


# ═══════════════════════════════════════════════════
# 品牌榜解析器
# ═══════════════════════════════════════════════════
# 格式: 品牌块之间有空行分隔
# 品牌块:
#   行1: 品牌名 (中英文混合，如 "Delonghi德龙")
#   行2: 描述 (包含 件/人/购买/关注/加购 等)
#   行3: 品牌英文名
#   行4-6: 价格行 (包含 ¥)
# ═══════════════════════════════════════════════════

def _looks_like_brand_line(line: str) -> bool:
    """判断一行是否可能是品牌名行（不是描述/价格行）"""
    if not line:
        return False
    # 排除明显不是品牌名的行
    if re.search(r"(件|人购买|关注|加购|¥|飙升|种草|好评|热卖)", line):
        return False
    # 不能是纯数字
    if re.match(r"^\d+$", line):
        return False
    # 必须有字母或常见品牌中文名
    if re.search(r"[A-Za-z]", line):
        return True
    # 匹配已知中文品牌名
    for key in BRAND_NORMALIZE_MAP:
        if key in line:
            return True
    # 2-6个中文字符可能为品牌名
    if re.match(r"^[\u4e00-\u9fff]{2,6}$", line):
        return True
    # 中英文混合
    if re.search(r"[\u4e00-\u9fff].*[A-Za-z]|[A-Za-z].*[\u4e00-\u9fff]", line):
        return True
    return False


def _looks_like_description(line: str) -> bool:
    """判断一行是否为描述行"""
    keywords = ["件", "人购买", "正在关注", "加购", "人种草", "人好评",
                "热卖商品", "火爆热卖", "好评如潮", "种草好物"]
    return any(kw in line for kw in keywords)


def _looks_like_price_line(line: str) -> bool:
    """判断一行是否为价格行"""
    return "¥" in line


def _extract_brand_name_en(line: str) -> str:
    """从品牌行提取英文名"""
    m = re.search(r"^([A-Za-z\s/]+)", line)
    if m:
        return m.group(1).strip()
    # 如果没有英文字母，尝试从品牌映射获取
    for key in _BRAND_KEYS:
        if key in line:
            return BRAND_NORMALIZE_MAP[key]
    return line


def _is_brand_english_only(line: str) -> bool:
    """判断一行是否只有英文字母（品牌英文名行）"""
    return bool(re.match(r"^[A-Za-z\s/]+$", line.strip())) and len(line.strip()) >= 2


def parse_brand_rank(raw_text: str) -> list[dict]:
    """解析品牌排行榜完整文本"""
    today = date.today().isoformat()
    lines = [l.strip() for l in raw_text.split("\n")]
    records = []
    rank = 1
    i = 0

    while i < len(lines):
        line = lines[i]
        if not line:
            i += 1
            continue

        # 跳过纯英文行（品牌英文名，不是品牌块开头）
        if _is_brand_english_only(line):
            i += 1
            continue

        # 跳过描述行和价格行
        if _looks_like_description(line) or _looks_like_price_line(line):
            i += 1
            continue

        # 找品牌名行
        if not _looks_like_brand_line(line):
            i += 1
            continue

        brand_name = line
        brand_en = _extract_brand_name_en(brand_name)
        # 标准化
        std_brand, _ = extract_brand(brand_name)
        brand_cn = std_brand if std_brand else brand_name
        brand_en_simple = brand_en if brand_en else brand_cn

        # 找描述行（品牌块内往下找）
        description = ""
        for j in range(i+1, min(i+4, len(lines))):
            if lines[j] and _looks_like_description(lines[j]):
                description = lines[j]
                break

        # 找价格行
        prices = []
        for j in range(i+1, min(i+6, len(lines))):
            if lines[j] and _looks_like_price_line(lines[j]):
                pm = re.search(r"¥(\d+)", lines[j])
                if pm:
                    prices.append(pm.group(1))

        # 提取关注人数/趋势
        followers = ""
        trend = ""
        if description:
            fm = re.search(r"(\d+万\+?\d*人?)正在关注", description)
            if fm:
                followers = fm.group(1)
            tm = re.search(r"(飙升\d+%|热度上升)", description)
            if tm:
                trend = tm.group(1)

        records.append({
            "date": today,
            "source": "brand",
            "rank": rank,
            "brand_cn": brand_cn,
            "brand_en": brand_en_simple,
            "description": description,
            "followers": followers,
            "trend": trend,
            "prices": ",".join(prices[:3]),  # 最多3个价格
        })

        rank += 1
        # 跳过整个品牌块（约4-6行）
        i += 4

    return records
