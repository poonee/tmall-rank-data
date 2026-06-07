# 每日排行榜数据仓库

## 📂 目录结构

```
/workspace/rank_data/
│
├── README.md              ← 本文件：项目说明 & 数据标准
│
├── daily/                 ← 每日原始数据（按日期归档）
│   ├── 2026-06-07_pc.csv      PC端单品榜TOP30
│   ├── 2026-06-07_pc.json
│   ├── 2026-06-07_mobile.csv  手机端单品榜TOP30
│   ├── 2026-06-07_mobile.json
│   ├── 2026-06-07_brand.csv   品牌榜TOP20
│   └── 2026-06-07_brand.json
│
├── archive/               ← 历史备份（按月打包）
│
├── scripts/               ← 采集 & 处理脚本
│   ├── daily_collector.py      主采集脚本（调用各技能）
│   ├── data_standards.py       数据字段定义 & 标准化
│   ├── csv_viewer.py           快速查看CSV工具
│   └── requirements.txt        依赖
│
└── output/                ← 衍生产出（可视化数据等）
    └── latest_pc.csv           PC端最新数据（方便外部读取）
    └── latest_mobile.csv       手机端最新数据
```

---

## 📊 数据字段标准

### 单品排行榜（PC端 & 手机端统一）

| 字段名 | 类型 | 必填 | 说明 | PC端 | 手机端 |
|--------|:----:|:----:|------|:----:|:-----:|
| `date` | str | ✅ | 采集日期 YYYY-MM-DD | ✅ | ✅ |
| `source` | str | ✅ | 数据来源: `pc` / `mobile` | ✅ | ✅ |
| `rank` | int | ✅ | 排名 (1-30) | ✅ | ✅ |
| `brand` | str | ✅ | 品牌名（标准化后） | ✅ | ✅ |
| `model` | str | ✅ | 型号 | ✅ | ✅ |
| `price` | int | ✅ | 标价（元） | ✅ | ✅ |
| `coupon_price` | int | | 券后价（元，手机端特有） | | ✅ |
| `sales_7d` | str | ✅ | 近7天销量 | ✅ | ✅ |
| `sales_30d` | str | | 近30天销量 | | ✅ |
| `trend` | str | | 趋势标签（蝉联榜首/排名上升等） | ✅ | ✅ |
| `image_url` | str | | 商品图片URL | ✅ | ✅ |
| `raw_text` | str | | 原始采集文本（留底） | ✅ | ✅ |

### 品牌排行榜

| 字段名 | 类型 | 必填 | 说明 |
|--------|:----:|:----:|------|
| `date` | str | ✅ | 采集日期 |
| `source` | str | ✅ | 固定为 `brand` |
| `rank` | int | ✅ | 排名 (1-20) |
| `brand_cn` | str | ✅ | 品牌中文名 |
| `brand_en` | str | ✅ | 品牌英文名（标准化后） |
| `description` | str | | 描述文本（热卖X件/关注X人） |
| `followers` | str | | 关注人数 |
| `trend` | str | | 趋势 |
| `prices` | str | | 3个热销商品价格，逗号分隔 |

---

## 📋 CSV 文件规范

| 规则 | 说明 |
|------|------|
| **编码** | UTF-8 with BOM（Excel可直接打开） |
| **分隔符** | 逗号 `,` |
| **文本引号** | 含逗号/换行的字段用双引号包裹 |
| **空值** | 留空，不填 `null`/`None` |
| **小数** | 价格取整，无小数 |
| **日期格式** | YYYY-MM-DD |

---

## 🔄 双写流程

```
Step 1: 采集（调用爬虫技能）
    ↓
Step 2: 解析 → 结构化（按上方字段标准）
    ↓
Step 3: 双写
    ├── → daily/YYYY-MM-DD_source.csv  （CSV格式，Excel可直接打开）
    ├── → daily/YYYY-MM-DD_source.json （JSON格式，程序读取）
    └── → output/latest_source.csv      （覆盖，始终保持最新）
    ↓
Step 4: 版本管理
    └── git add && git commit -m "data: YYYY-MM-DD ranking"
```

---

## 🚀 快速使用

```bash
# 1. 查看最新数据
cat output/latest_pc.csv

# 2. 查看某日数据
cat daily/2026-06-07_pc.csv

# 3. 运行采集脚本
cd scripts && python3 daily_collector.py
```
