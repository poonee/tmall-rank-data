#!/bin/bash
#
# git_after_collect.sh — 采集后自动提交到 Git
#
# 在 daily_collector.py 执行完成后调用，自动：
#   1. git add 新增/修改的数据文件
#   2. git commit（带日期标记）
#   3. (可选) git push 到远程仓库
#
# 用法:
#   bash scripts/git_after_collect.sh                          # 仅本地 commit
#   bash scripts/git_after_collect.sh --push                   # commit + push
#   bash scripts/git_after_collect.sh --message "自定义消息"    # 自定义 commit 消息
#
# 配置远程仓库:
#   bash scripts/git_after_collect.sh --remote <仓库URL>       # 添加远程仓库
#

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

MODE="${1:-commit}"
PUSH=false
CUSTOM_MSG=""

# 解析参数
for arg in "$@"; do
    case "$arg" in
        --push) PUSH=true ;;
        --remote=*) REMOTE_URL="${arg#*=}" ;;
        --message=*) CUSTOM_MSG="${arg#*=}" ;;
        --help)
            head -30 "$0" | grep "^#" | sed 's/^#//'
            exit 0
            ;;
    esac
done

# 设置远程仓库
if [ -n "$REMOTE_URL" ]; then
    echo "🔗 添加远程仓库: $REMOTE_URL"
    if git remote get-url origin 2>/dev/null; then
        git remote set-url origin "$REMOTE_URL"
    else
        git remote add origin "$REMOTE_URL"
    fi
fi

# 检查有无变更
if ! git status --porcelain | grep -q .; then
    echo "✅ 没有新变更，跳过 commit"
    exit 0
fi

# 生成 commit 消息
if [ -n "$CUSTOM_MSG" ]; then
    COMMIT_MSG="$CUSTOM_MSG"
else
    TODAY=$(date +%Y-%m-%d)
    NOW=$(date +%H:%M)
    # 统计变更
    ADDED=$(git status --porcelain | grep -c "^??" || true)
    MODIFIED=$(git status --porcelain | grep -c "^ M" || true)
    
    COMMIT_MSG="data: 排行榜数据更新 $TODAY $NOW"
    [ "$ADDED" -gt 0 ]    && COMMIT_MSG="$COMMIT_MSG (+${ADDED}新增)"
    [ "$MODIFIED" -gt 0 ] && COMMIT_MSG="$COMMIT_MSG (~${MODIFIED}修改)"

    # 提取 TOP 变化
    CHANGES=$(git diff --stat -- "daily/*.csv" "output/*.csv" 2>/dev/null | tail -3)
fi

# 添加文件并提交
git add -A
git commit -m "$COMMIT_MSG" --quiet

echo "✅ Git commit: $COMMIT_MSG"

# 查看变更摘要
echo ""
echo "📊 变更摘要:"
git show --stat --format="" HEAD | head -10

# Push（可选）
if [ "$PUSH" = true ]; then
    echo ""
    echo "📤 推送到远程仓库..."
    if git remote get-url origin 2>/dev/null; then
        git push origin main
        echo "✅ Push 完成"
    else
        echo "⚠️  未配置远程仓库，跳过 push"
        echo "   配置: bash scripts/git_after_collect.sh --remote <仓库URL>"
    fi
fi
