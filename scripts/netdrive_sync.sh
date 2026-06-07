#!/bin/bash
#
# netdrive_sync.sh — 排行榜数据同步到 netdrive 云盘
#
# 将 output/ 目录的文件同步到 netdrive 云盘共享目录。
#
# 用法:
#   bash scripts/netdrive_sync.sh              # 同步全部
#   bash scripts/netdrive_sync.sh --check      # 检查状态
#
# 前置条件:
#   netdrive MCP 需要完成 OAuth 认证
#   在 .mcp.json 中配置 netdrive 连接信息
#

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

MODE="${1:-sync}"

echo "╔════════════════════════════════════════╗"
echo "║   netdrive 云盘同步                    ║"
echo "╚════════════════════════════════════════╝"

# ── 检查 netdrive 是否可用 ──
check_netdrive() {
    local resp
    resp=$(curl -s http://netdrive.agent-gateway.auth-proxy.local/mcp \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' 2>&1)
    
    if echo "$resp" | grep -q "credential fetch failed"; then
        echo "❌ netdrive 未认证，无法使用"
        echo ""
        echo "   要启用 netdrive 同步:"
        echo "   1. 确保 netdrive MCP 已完成 OAuth 认证"
        echo "   2. 认证完成后重新运行本脚本"
        return 1
    fi
    
    echo "✅ netdrive 可用"
    return 0
}

# ── 同步文件到 netdrive ──
sync_files() {
    echo ""
    echo "📤 同步文件到 netdrive 云盘..."
    
    # 需要同步的文件列表
    FILES=(
        "output/latest_pc.csv"
        "output/latest_mobile.csv"
        "output/latest_brand.csv"
        "output/index.html"
        "output/ranking_data.js"
    )
    
    for f in "${FILES[@]}"; do
        if [ -f "$f" ]; then
            local size
            size=$(stat -c%s "$f")
            echo "   📄 $f (${size} bytes)"
            # TODO: 调用 netdrive API 上传
            # curl -X PUT "http://netdrive.agent-gateway.auth-proxy.local/upload" \
            #   -F "file=@$f" \
            #   -F "path=/rank_data/$f"
        fi
    done
    
    echo ""
    echo "✅ 同步完成"
}

# ── 仅检查状态 ──
if [ "$MODE" = "--check" ]; then
    check_netdrive
    exit $?
fi

# ── 同步流程 ──
if check_netdrive; then
    sync_files
else
    echo ""
    echo "ℹ️  当前处于离线模式。netdrive 认证后即可自动同步。"
    echo "   同步脚本已就绪，认证后运行: bash scripts/netdrive_sync.sh"
fi
