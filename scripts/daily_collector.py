#!/usr/bin/env python3
"""
daily_collector.py — 每日排行榜采集 & 双写主脚本

三种运行模式:
  1. --dry-run        模拟运行，生成示例数据（开发测试用）
  2. --file <path>    读取本地原始文本文件，解析后写入（手动采集后处理）
  3. --live           真实采集（需 agent-browser + Edge CDP 环境）

用法:
  python3 daily_collector.py                    # 等价于 --dry-run
  python3 daily_collector.py --dry-run           # 模拟全量采集
  python3 daily_collector.py --live --source pc  # 真实采集PC端
  python3 daily_collector.py --file ./raw_pc.txt # 从文件解析

输出:
  /workspace/rank_data/daily/YYYY-MM-DD_{source}.csv
  /workspace/rank_data/daily/YYYY-MM-DD_{source}.json
  /workspace/rank_data/output/latest_{source}.csv
"""

import sys
import os
import json
import subprocess
import re
import argparse
from datetime import datetime, date

# 添加上级目录到路径
sys.path.insert(0, "/workspace/rank_data/scripts")
from data_standards import RankDataWriter, SINGLE_RANK_FIELDS, BRAND_RANK_FIELDS


# ═══════════════════════════════════════════════════
# 实时采集（agent-browser）
# ═══════════════════════════════════════════════════

# 排行榜URL
PC_RANK_URL = (
    "https://huodong.taobao.com/wow/z/tbhome/tbpc-venue/rank"
    "?wh_from=rank_popup&tagId=126467358&secondTab=18"
)
MOBILE_RANK_SHORT_URL = "https://m.tb.cn/h.R7FRxKK"  # 手机端单品榜短链
MOBILE_BRAND_SHORT_URL = "https://m.tb.cn/h.RiqB1O1"  # 手机端品牌榜短链


def agent_browser_exec(args: list[str], timeout: int = 30) -> str:
    """执行 agent-browser 命令并返回输出"""
    cmd = ["agent-browser"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"⚠️  agent-browser 超时 (timeout={timeout}s): {' '.join(args)}")
        return ""
    except FileNotFoundError:
        print("❌ agent-browser 未安装")
        return ""


def collect_pc_live() -> str:
    """用 agent-browser 采集PC端排行榜数据"""
    print("   → 打开PC排行页面...")
    agent_browser_exec(["open", PC_RANK_URL])
    # 等待页面加载
    import time
    time.sleep(8)

    print("   → 点击'展开更多'获取完整TOP30...")
    agent_browser_exec(["eval",
        "document.querySelector('[class*=rankContentWrap] [class*=Exprare]')"
        "&&document.querySelector('[class*=rankContentWrap] [class*=Exprare]')"
        ".click()"])
    time.sleep(3)

    print("   → 提取排行榜文本...")
    raw = agent_browser_exec(["eval",
        "document.querySelector('[class*=rankContentWrap]')"
        "?document.querySelector('[class*=rankContentWrap]').textContent:''",
        "--json"])

    return raw


def collect_mobile_live() -> str:
    """用 agent-browser 采集手机端排行榜数据（需先设置iPhone 14设备模式）"""
    print("   → 设置手机模拟模式 (iPhone 14)...")
    agent_browser_exec(["set", "device", "iPhone 14"])

    print("   → 打开手机端短链...")
    agent_browser_exec(["open", MOBILE_RANK_SHORT_URL])
    import time
    time.sleep(12)

    print("   → 滚动加载全部TOP30...")
    agent_browser_exec(["eval",
        "for(var i=0;i<40;i++){window.scrollBy(0,300);}"])
    time.sleep(3)

    print("   → 提取文本...")
    raw = agent_browser_exec(["eval",
        "document.body.innerText.substring(0, 8000)", "--json"])
    return raw


def collect_brand_live() -> str:
    """用 agent-browser 采集品牌榜数据"""
    print("   → 打开品牌榜短链...")
    agent_browser_exec(["eval",
        f"window.location.href = '{MOBILE_BRAND_SHORT_URL}'"])
    import time
    time.sleep(10)

    print("   → 滚动加载...")
    agent_browser_exec(["eval",
        "for(var i=0;i<40;i++){window.scrollBy(0,300);}"])
    time.sleep(3)

    raw = agent_browser_exec(["eval",
        "document.body.innerText.substring(0, 5000)", "--json"])
    return raw


# ═══════════════════════════════════════════════════
# 解析器调用
# ═══════════════════════════════════════════════════

def parse_rank_text(raw_text: str, source: str) -> list[dict]:
    """调用解析器解析原始文本"""
    from parsers import parse_pc_rank, parse_mobile_rank, parse_brand_rank

    if not raw_text or raw_text in ('""', "''"):
        print(f"⚠️  {source} 原始文本为空")
        return []

    # agent-browser --json 返回的可能是JSON字符串，需处理引号
    cleaned = raw_text.strip().strip('"').strip("'")
    # 处理JSON转义
    if cleaned.startswith('"') and cleaned.endswith('"'):
        try:
            cleaned = json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    if source == "pc":
        return parse_pc_rank(cleaned)
    elif source == "mobile":
        return parse_mobile_rank(cleaned)
    elif source == "brand":
        return parse_brand_rank(cleaned)
    return []


# ═══════════════════════════════════════════════════
# Git 自动 commit
# ═══════════════════════════════════════════════════

def git_commit(today: str):
    """采集后自动 git commit"""
    import subprocess
    repo_dir = "/workspace/rank_data"

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=repo_dir
    )
    if not result.stdout.strip():
        print("✅ 没有新变更，跳过 git commit")
        return

    added = result.stdout.count("?? ")
    modified = result.stdout.count(" M")
    now = datetime.now().strftime("%H:%M")
    msg = f"data: 排行榜数据更新 {today} {now}"
    if added:
        msg += f" (+{added}新增)"
    if modified:
        msg += f" (~{modified}修改)"

    subprocess.run(["git", "add", "-A"], cwd=repo_dir)
    subprocess.run(["git", "commit", "-m", msg, "--quiet"], cwd=repo_dir)
    print(f"\n📦 Git commit: {msg}")

    diff = subprocess.run(
        ["git", "show", "--stat", "--format=", "HEAD"],
        capture_output=True, text=True, cwd=repo_dir
    )
    if diff.stdout:
        lines = [l for l in diff.stdout.strip().split("\n") if l.strip()]
        print(f"📊 变更文件 ({len(lines)} 个):")
        for l in lines[:6]:
            print(f"   {l}")
        if len(lines) > 6:
            print(f"   ... 还有 {len(lines) - 6} 个文件")


# ═══════════════════════════════════════════════════
# 示例数据（dry-run 用）
# ═══════════════════════════════════════════════════

SAMPLE_RAW_PC = """TOP1蝉联榜首8周值得买近7天销售300+件格米莱双瞳商用咖啡机...¥45996期免息
TOP2排名上升2位近7天销售200+件wigomatW12商用咖啡机...¥11349
TOP3霸榜前三值得买近7天销售150+件海氏C9Pro双锅炉咖啡机...¥12999
TOP4近7天销售100+件Delonghi德龙ECAM...¥8999
TOP5近7天销售80+件百胜图Barsetto...¥6999"""

SAMPLE_RAW_MOBILE = """蝉联榜首wigomatW12商用咖啡机¥13349券后¥11349
格米莱双瞳商用咖啡机¥5599券后¥4599近30天内销量1000+件
海氏C9Pro双锅炉家用商用咖啡机¥14999券后¥12999
4
wigomatW12商用咖啡机¥11349券后¥9349
近30天内销量900+件
5
Delonghi德龙ECAM...¥10499券后¥8999
近30天内销量800+件"""

SAMPLE_RAW_BRAND = """Delonghi德龙
热卖商品1万+件，1万+人购买
Delonghi
千人购买 ¥2990
百人好评 ¥4190
千人种草 ¥2940

GEMILAI格米莱
热卖商品3000+件，2000+人购买
GEMILAI
千人购买 ¥4599
百人好评 ¥6599
千人种草 ¥8599

wigomat唯咖美
40万+人正在关注，1000+人加购
wigomat
火爆热卖 ¥7549
好评如潮 ¥13349
种草好物 ¥15649"""

SAMPLE_RAW = {
    "pc": SAMPLE_RAW_PC,
    "mobile": SAMPLE_RAW_MOBILE,
    "brand": SAMPLE_RAW_BRAND,
}


# ═══════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════

def collect_and_write(source: str, writer: RankDataWriter,
                      mode: str = "dry-run", file_path: str = None):
    """采集指定来源的数据并双写"""
    print(f"\n{'='*50}")
    mode_labels = {"dry-run": "🟡 模拟", "file": "📂 文件解析", "live": "🔴 实时采集"}
    print(f"  {mode_labels.get(mode, '❓')}  来源: {source.upper()}")
    print(f"{'='*50}")

    raw_text = ""
    records = []

    if mode == "dry-run":
        raw_text = SAMPLE_RAW.get(source, "")

    elif mode == "file":
        if not file_path:
            print("❌ --file 模式需要指定文件路径")
            return
        path = file_path if file_path.startswith("/") else \
            f"/workspace/rank_data/{file_path}"
        if not os.path.exists(path):
            print(f"❌ 文件不存在: {path}")
            return
        with open(path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        print(f"   → 读取文件: {path} ({len(raw_text)} chars)")

    elif mode == "live":
        print("   → 开始实时采集...")
        if source == "pc":
            raw_text = collect_pc_live()
        elif source == "mobile":
            raw_text = collect_mobile_live()
        elif source == "brand":
            raw_text = collect_brand_live()
        else:
            print(f"❌ 不支持的来源: {source}")
            return
        print(f"   → 采集完成 ({len(raw_text)} chars)")

    # 解析
    if raw_text:
        records = parse_rank_text(raw_text, source)

    if not records:
        print(f"❌ 未解析到 {source} 数据")
        # 保存原始文本供排查
        if raw_text:
            debug_path = f"{writer.daily_dir}/{writer.today}_{source}_raw.txt"
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(raw_text)
            print(f"   💾 原始文本已保存: {debug_path}")
        return

    fields = SINGLE_RANK_FIELDS if source != "brand" else BRAND_RANK_FIELDS
    writer.write(records, source, fields)

    # 汇总
    print(f"📊 共 {len(records)} 条记录")
    for r in records[:5]:
        brand = r.get("brand") or r.get("brand_en", "")
        model = r.get("model", "")
        price = r.get("price", "")
        cp = r.get("coupon_price", "")
        cp_str = f" (券后¥{cp})" if cp else ""
        print(f"   #{r['rank']}  {brand:>12}  {model:<12}  ¥{price}{cp_str}")
    if len(records) > 5:
        print(f"   ... 还有 {len(records) - 5} 条")


def main():
    parser = argparse.ArgumentParser(
        description="每日排行榜采集 & 双写系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
三种运行模式:
  (默认)    模拟运行，生成示例数据
  --dry-run 同默认，明确模拟模式
  --file    读取本地原始文本文件解析
  --live    真实采集（需 agent-browser 环境）

示例:
  python3 daily_collector.py --dry-run --source all
  python3 daily_collector.py --file raw_pc.txt --source pc
  python3 daily_collector.py --live --source pc
  python3 daily_collector.py --live --source mobile
        """)
    parser.add_argument("--source", choices=["pc", "mobile", "brand", "all"],
                        default="all", help="数据来源 (默认: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="模拟运行（默认行为）")
    parser.add_argument("--file", type=str, default=None,
                        help="从文件读取原始文本解析")
    parser.add_argument("--live", action="store_true",
                        help="实时采集（需 agent-browser）")
    parser.add_argument("--git", action="store_true",
                        help="采集后自动 git commit")
    args = parser.parse_args()

    # 模式判定
    mode = "dry-run"
    if args.live:
        mode = "live"
    elif args.file:
        mode = "file"

    print("╔══════════════════════════════════════════╗")
    print("║     每日排行榜数据采集 & 双写系统         ║")
    print(f"║     运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}      ║")
    print(f"║     运行模式: {mode:>12}            ║")
    print("╚══════════════════════════════════════════╝")

    writer = RankDataWriter()

    sources = ["pc", "mobile", "brand"] if args.source == "all" else [args.source]
    for src in sources:
        collect_and_write(src, writer, mode=mode, file_path=args.file)

    print(f"\n{'='*50}")
    print("✅ 完成！数据已保存至 /workspace/rank_data/")
    print("   daily/  → 按日期归档（CSV + JSON）")
    print("   output/ → latest 最新数据")

    from pathlib import Path
    files = sorted(Path(writer.daily_dir).glob(f"{writer.today}_*"))
    if files:
        print(f"\n📂 本次生成文件 ({len(files)} 个):")
        for p in files:
            print(f"   📄 {p.name} ({p.stat().st_size:>6} bytes)")

    # ── Git 自动 commit ──
    if args.git:
        git_commit(writer.today)


if __name__ == "__main__":
    main()
