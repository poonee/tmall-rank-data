#!/usr/bin/env python3
"""
csv_viewer.py — 排行榜 CSV 快速查看工具

用法:
  python3 csv_viewer.py                           # 查看所有 daily 文件
  python3 csv_viewer.py --file daily/2026-06-07_pc.csv  # 查看指定文件
  python3 csv_viewer.py --latest pc               # 查看最新PC端数据
  python3 csv_viewer.py --summary                 # 汇总统计
"""

import sys, os, csv, json, glob
from datetime import datetime

sys.path.insert(0, "/workspace/rank_data/scripts")
from data_standards import print_csv_preview

DATA_DIR = "/workspace/rank_data"


def list_daily_files():
    """列出所有 daily 文件"""
    files = sorted(glob.glob(f"{DATA_DIR}/daily/*.csv"))
    if not files:
        print("📭 daily/ 目录下暂无 CSV 文件")
        return

    print(f"\n📂 daily/ 目录共 {len(files)} 个 CSV 文件:\n")
    for f in files:
        size = os.path.getsize(f)
        fname = os.path.basename(f)
        # 从文件名提取日期和来源
        parts = fname.replace(".csv", "").split("_")
        date_part = parts[0] if len(parts) >= 1 else "???"
        src_part = parts[1] if len(parts) >= 2 else "???"
        print(f"   📄 {fname}  ({size:>6} bytes)  │ {date_part} │ {src_part:>6}")


def show_summary():
    """显示汇总统计"""
    files = sorted(glob.glob(f"{DATA_DIR}/daily/*.csv"))
    if not files:
        print("📭 暂无数据")
        return

    brands = {}
    total_records = 0

    for f in files:
        with open(f, "r", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                total_records += 1
                brand = row.get("brand") or row.get("brand_en", "")
                if brand:
                    brands[brand] = brands.get(brand, 0) + 1

    print(f"\n📊 汇总统计:")
    print(f"   CSV 文件数: {len(files)}")
    print(f"   总记录数: {total_records}")
    print(f"\n   出现品牌 Top 10:")
    for i, (b, c) in enumerate(sorted(brands.items(), key=lambda x: -x[1])[:10], 1):
        print(f"      {i:>2}. {b:>12}  ({c} 次)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="排行榜CSV查看工具")
    parser.add_argument("--file", help="指定CSV文件路径（相对 daily/ 或绝对路径）")
    parser.add_argument("--latest", choices=["pc", "mobile", "brand"],
                        help="查看最新数据")
    parser.add_argument("--summary", action="store_true", help="汇总统计")
    parser.add_argument("--rows", type=int, default=5, help="预览行数 (默认5)")
    args = parser.parse_args()

    if args.summary:
        show_summary()
        return

    if args.latest:
        path = f"{DATA_DIR}/output/latest_{args.latest}.csv"
        if os.path.exists(path):
            print(f"\n📄 最新 {args.latest.upper()} 数据 ({path}):\n")
            print_csv_preview(path, args.rows)
        else:
            print(f"❌ 暂无 {args.latest} 数据")
        return

    if args.file:
        path = args.file if args.file.startswith("/") else f"{DATA_DIR}/{args.file}"
        if os.path.exists(path):
            print(f"\n📄 {path}:\n")
            print_csv_preview(path, args.rows)
        else:
            print(f"❌ 文件不存在: {path}")
        return

    list_daily_files()
    show_summary()


if __name__ == "__main__":
    main()
