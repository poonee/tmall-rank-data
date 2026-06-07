"""
data_standards.py — 排行榜数据字段定义 & 标准化工具

本模块定义所有数据字段标准、品牌/型号标准化映射，
以及CSV/JSON读写工具函数。

使用方式：
    from data_standards import RankDataWriter, normalize_brand
"""

import csv
import json
import os
from datetime import date
from typing import Optional

# ═══════════════════════════════════════════════════
# 字段定义
# ═══════════════════════════════════════════════════

SINGLE_RANK_FIELDS = [
    "date", "source", "rank", "brand", "model",
    "price", "coupon_price", "sales_7d", "sales_30d",
    "trend", "image_url", "raw_text",
]

BRAND_RANK_FIELDS = [
    "date", "source", "rank", "brand_cn", "brand_en",
    "description", "followers", "trend", "prices",
]

# ═══════════════════════════════════════════════════
# 品牌名标准化映射
# ═══════════════════════════════════════════════════

BRAND_NORMALIZE_MAP = {
    # 中文 → 标准英文名
    "唯咖美": "wigomat",
    "德龙": "Delonghi",
    "格米莱": "GEMILAI",
    "柏翠": "Petrus",
    "百胜图": "Barsetto",
    "海氏": "Hauswirt",
    "雪特朗": "Stelang",
    "铂富": "Breville",
    "惠家": "Welhome",
    "西屋": "Westinghouse",
    "奈斯派索": "NESPRESSO",
    # 原始英文 → 标准英文名
    "Delonghi德龙": "Delonghi",
    "GEMILAI格米莱": "GEMILAI",
    "Petrus柏翠": "Petrus",
    "Barsetto百胜图": "Barsetto",
    "Hauswirt海氏": "Hauswirt",
    "Stelang雪特朗": "Stelang",
    "Breville铂富": "Breville",
    "Welhome惠家": "Welhome",
    "Westinghouse西屋": "Westinghouse",
    "wigomat唯咖美": "wigomat",
    "NESPRESSO奈斯派索": "NESPRESSO",
    "LA MARZOCCO": "La Marzocco",
    "LELIT": "Lelit",
}

# ═══════════════════════════════════════════════════
# 品牌标准化函数
# ═══════════════════════════════════════════════════

def normalize_brand(raw: str) -> str:
    """标准化品牌名"""
    raw = raw.strip()
    # 精确匹配
    if raw in BRAND_NORMALIZE_MAP:
        return BRAND_NORMALIZE_MAP[raw]
    # 子串匹配
    for key, val in BRAND_NORMALIZE_MAP.items():
        if key in raw or raw in key:
            return val
    return raw  # 未匹配则原样返回


def normalize_model(brand: str, raw_text: str) -> str:
    """从原始文本中提取型号（去掉品牌名后剩余部分）
    
    示例: "wigomatW12" → "W12"
          "格米莱双瞳商用咖啡机" → "双瞳"
    """
    text = raw_text.strip()
    text = text.replace(brand, "").strip()
    return text


# ═══════════════════════════════════════════════════
# 数据读写工具
# ═══════════════════════════════════════════════════

class RankDataWriter:
    """排行榜数据双写工具：同时写入 CSV + JSON"""

    def __init__(self, base_dir: str = "/workspace/rank_data"):
        self.base_dir = base_dir
        self.daily_dir = f"{base_dir}/daily"
        self.output_dir = f"{base_dir}/output"
        os.makedirs(self.daily_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        self.today = date.today().isoformat()

    def write(self, records: list[dict], source: str, fields: Optional[list] = None):
        """
        双写数据

        参数:
            records: 记录列表（每行为一个字典）
            source: 数据来源标识，如 'pc', 'mobile', 'brand'
            fields: 字段列表，默认自动从第一条记录提取
        """
        if not records:
            print(f"⚠️  没有数据可写入 (source={source})")
            return

        fields = fields or list(records[0].keys())
        prefix = f"{self.today}_{source}"

        # --- 写 JSON ---
        json_path = f"{self.daily_dir}/{prefix}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON 写入: {json_path} ({len(records)} 条)")

        # --- 写 CSV (UTF-8 BOM, Excel友好) ---
        csv_path = f"{self.daily_dir}/{prefix}.csv"
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for rec in records:
                # 只保留定义的字段
                filtered = {k: rec.get(k, "") for k in fields}
                writer.writerow(filtered)
        print(f"✅ CSV 写入: {csv_path} ({len(records)} 条)")

        # --- 覆盖 latest ---
        latest_csv = f"{self.output_dir}/latest_{source}.csv"
        os.system(f"cp {csv_path} {latest_csv}")
        print(f"✅ Latest 更新: {latest_csv}")

        return json_path, csv_path


# ═══════════════════════════════════════════════════
# 快速查看工具
# ═══════════════════════════════════════════════════

def print_csv_preview(csv_path: str, rows: int = 5):
    """打印CSV前N行预览"""
    if not os.path.exists(csv_path):
        print(f"❌ 文件不存在: {csv_path}")
        return
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= rows:
                break
            print(f"#{i+1}: {json.dumps(row, ensure_ascii=False)}")
