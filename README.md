# 每日排行榜数据仓库

天猫商用咖啡机排行榜：Python 采集与解析、按日 CSV/JSON 归档，以及 `docs/` 下的 GitHub Pages 仪表盘。

脚本按自身文件位置定位仓库根目录，克隆后在任意工作目录执行即可。

## 📂 目录结构

```
tmall-rank-data/
│
├── README.md
│
├── daily/                         每日归档（已有数据，不自动补历史）
│   ├── 2026-06-02_pc.csv/.json … 2026-06-07_pc.csv/.json
│   ├── 2026-06-07_mobile.csv/.json
│   └── 2026-06-07_brand.csv/.json
│
├── docs/                          GitHub Pages 仪表盘 + 最新快照
│   ├── index.html                      单品榜页面
│   ├── brand_ranking_15day.html        品牌榜页面
│   ├── ranking_15day_data.js           单品 15 日数据（data_to_html.py 更新）
│   ├── brand_ranking_15day_data.js     品牌 15 日数据
│   ├── latest_pc.csv                   PC 端最新快照
│   ├── latest_mobile.csv               手机端最新快照
│   ├── latest_brand.csv                品牌榜最新快照
│   └── knowledge_share_data_storage.md
│
└── scripts/
    ├── daily_collector.py         采集入口（--dry-run / --file / --live）
    ├── parsers.py                 PC、手机、品牌原始文本解析
    ├── data_standards.py          字段标准与 CSV/JSON 双写
    ├── data_to_html.py            把 daily/ 合并进 docs/*.js
    ├── csv_viewer.py              查看 daily/ 与 docs/latest_*.csv
    ├── clean_and_convert.js       一次性清洗，读写 /tmp 下的 JS（不参与每日采集）
    ├── convert_user_data.js       一次性格式转换，同样读写 /tmp
    ├── git_after_collect.sh       采集后的 git commit / push
    ├── netdrive_sync.sh           把 docs/ 列到 netdrive（需单独认证）
    └── requirements.txt           第三方依赖说明（当前仅标准库）
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
    └── → docs/latest_source.csv        （覆盖，始终保持最新）
    ↓
Step 4: 版本管理
    └── git add && git commit -m "data: YYYY-MM-DD ranking"
```

---

## 🚀 快速使用

需要 Python 3.9+。采集、解析和可视化脚本只使用标准库，`scripts/requirements.txt` 没有第三方包：

```bash
pip install -r scripts/requirements.txt
```

在仓库根目录执行。数据路径由脚本文件所在位置决定，用绝对路径调用脚本时当前目录可以是别处。`--file` 等相对路径按仓库根目录解析。本地预览请在仓库根目录启动静态服务。

```bash
# 1. 查看最新快照与某一天的归档
python3 scripts/csv_viewer.py --latest pc
python3 scripts/csv_viewer.py --file daily/2026-06-07_pc.csv
python3 scripts/csv_viewer.py --summary

# 2. 模拟采集（示例文本，不访问网络；会写入当天的 daily/ 和 docs/latest_*.csv）
python3 scripts/daily_collector.py --dry-run

# 3. 从本地原始文本解析。路径相对仓库根目录，也可以传绝对路径
python3 scripts/daily_collector.py --file raw_pc.txt --source pc

# 4. 真实采集（需要本机已安装 agent-browser，并具备页面里用到的浏览器环境）
python3 scripts/daily_collector.py --live --source pc

# 5. 采集后提交 Git，并刷新 docs/ 下的 15 日数据文件
python3 scripts/daily_collector.py --source all --git --viz

# 6. 只根据 daily/ 增量更新可视化数据（不改 HTML 页面）
python3 scripts/data_to_html.py
# 忽略 docs/ 里已有基线、仅从 daily/ 重建：
python3 scripts/data_to_html.py --full

# 7. 本地预览仪表盘（在仓库根目录启动静态服务）
python3 -m http.server 8080
# 单品榜 http://localhost:8080/docs/index.html
# 品牌榜 http://localhost:8080/docs/brand_ranking_15day.html
```

已发布页面：

- https://poonee.github.io/tmall-rank-data/
- https://poonee.github.io/tmall-rank-data/brand_ranking_15day.html

`data_to_html.py` 在发现工作区有改动时会自己执行 `git add` 和 `git commit`。`--git` 只影响 `daily_collector.py` 自己的提交。

---

## 🏗️ 数据存储方案对比

项目中涉及多种数据存储方式，各有定位，互不替代。

### 核心对比

| 维度 | GitHub | 乐享知识库 | 云盘（netdrive） | 腾讯文档 |
|------|:--:|:--:|:--:|:--:|
| **本质** | 代码/数据版本管理平台 | 企业知识管理平台 | 文件存储平台 | 在线文档协作平台 |
| **核心能力** | Git版本控制、分支、PR | 文档编辑、全文搜索 | 文件上传下载、共享 | 多人实时编辑表格/文档 |
| **擅长存什么** | 代码、数据文件、配置 | 文档、方案、规范 | 任意文件 | 在线表格、在线文档 |
| **版本追踪** | ✅ 每次变更完整记录 | ❌ 基本无 | ❌ 无 | ✅ 编辑历史可回溯 |
| **实时协作** | ❌ 需PR合并 | ⚠️ 有但非强项 | ❌ | ✅ **最强** |
| **网页展示** | ✅ GitHub Pages | ✅ 自带阅读器 | ❌ | ✅ 分享链接查看 |
| **程序自动写入** | ✅ git push | ✅ API写入 | ✅ API上传 | ❌ **无公开API** |
| **表格能力** | ❌ 无 | ⚠️ 基础 | ❌ | ✅ **最强，类Excel** |
| **费用** | 私有仓库免费 | 企业版付费 | 按容量付费 | **企业微信内免费** |

### 一句话定位

> **GitHub** = 给**程序和数据**用的，擅长追踪变化
> **乐享知识库** = 给**人**用的，擅长沉淀知识
> **云盘** = 给**文件**用的，擅长存储共享
> **腾讯文档** = 给**团队**用的，擅长实时协作编辑

### 场景匹配

| 你要做的事 | 最合适的选择 | 原因 |
|-----------|:--:|------|
| 每日排行榜数据归档 | **GitHub** | 每天commit有历史，可回溯 |
| 可视化趋势页面展示 | **GitHub Pages** | 免费托管网页，链接即看 |
| 写竞品分析报告 | **乐享知识库** | 在线编辑、全文搜索、知识沉淀 |
| 存采集的原始截图/视频 | **云盘** | 大文件、非结构化数据 |
| 品牌策略方案 | **乐享知识库** | 评论、@人、知识沉淀 |
| 团队多人填销售数据 | **腾讯文档** | 实时协作，类Excel |
| 排行榜数据做图表分析 | **腾讯文档** | 在线表格+图表 |
| 采集结果自动入库 | **GitHub** | 程序自动写入，腾讯文档做不到 |

### 分层架构

```
📊 数据层（GitHub）          ← 每日CSV/JSON，Git版本追踪，程序自动写入
    ↓ 生成
📈 展示层（GitHub Pages）    ← 可视化趋势网页，团队随时看
    ↓ 按需导入
📊 协作层（腾讯文档）         ← 团队手动编辑分析时，导入CSV到在线表格
    ↓ 提炼
📖 知识层（乐享知识库）       ← 分析报告、策略文档、知识沉淀
    ↓ 附件
📁 存储层（云盘）            ← 大文件、原始素材、非结构化数据
```

### 腾讯文档关键局限

> **没有公开的写入API** — 程序无法自动把采集数据写入腾讯文档。
> 适合人工协作编辑，不适合程序自动写入。

---

## 📜 自动化任务

| 任务 | 时间 | 说明 |
|------|------|------|
| 每日排行榜采集 | 由仓库外的调度器触发 | 调用 `python3 scripts/daily_collector.py`（按需加 `--live --git --viz`） |

定时任务在仓库之外：在克隆后的机器上用 cron 或其他调度器调用上面的命令。采集后也可以单独运行 `bash scripts/git_after_collect.sh`（加 `--push` 则推送当前分支）。
