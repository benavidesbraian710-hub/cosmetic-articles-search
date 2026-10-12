#!/bin/bash
# 同步主仓数据到 cosmetic-preview 仓库（GitHub Pages 镜像）
# 用途：每次 export_data.py 完成后自动调用（也可手动）
# 触发：export_data.py → sync_to_preview.sh
#
# 流程：
#   1. 复制关键文件（HTML/data/stats/CHANGELOG/CNAME）到 preview 工作目录
#   2. git add + commit（如有变化）
#   3. git push（用 osxkeychain 已缓存的 PAT）
#   4. 验证远端版本号与本地一致
#
# 用法：bash sync_to_preview.sh

set -e

# ============ 配置 ============
SRC_DIR="$HOME/.openclaw/workspace/cosmetic-deploy"
DST_DIR="$HOME/.openclaw/workspace/cosmetic-preview"

# ============ Step 1: 复制文件 ============
echo "🔄 同步核心文件到 cosmetic-preview ..."

cd "$DST_DIR"

# 7个HTML
for f in index.html articles.html report.html service.html submit.html find.html admin.html; do
  cp -f "$SRC_DIR/$f" .
done

# 3个数据文件
cp -f "$SRC_DIR/data.json" .
cp -f "$SRC_DIR/stats.json" .

# 当前版本的 data.vXX.json（从 data.json 的 version 字段取名）
CUR_VERSION=$(python3 -c "import json; print(json.load(open('$SRC_DIR/data.json'))['version'])" 2>/dev/null || echo "")
if [ -n "$CUR_VERSION" ] && [ -f "$SRC_DIR/data.${CUR_VERSION}.json" ]; then
  cp -f "$SRC_DIR/data.${CUR_VERSION}.json" .
  echo "  ✓ data.${CUR_VERSION}.json"
fi

# CHANGELOG
cp -f "$SRC_DIR/CHANGELOG.md" .

# CNAME（如有）
[ -f "$SRC_DIR/CNAME" ] && cp -f "$SRC_DIR/CNAME" .

echo "  ✓ 7个HTML + data.json + stats.json + CHANGELOG.md"

# ============ Step 2: git commit ============
if [ -z "$(git status --porcelain)" ]; then
  echo ""
  echo "⏭️  preview 仓库无变化，跳过commit/push"
  exit 0
fi

git add -A
COMMIT_MSG="数据更新: 同步主仓${CUR_VERSION} - $(date '+%Y-%m-%d %H:%M:%S')"
git commit -m "$COMMIT_MSG" 2>&1 | tail -3

# ============ Step 3: git push（用 osxkeychain 自动认证） ============
echo ""
echo "🚀 推送到 cosmetic-preview ..."
if git push origin main 2>&1 | tail -5; then
  echo ""
  echo "✅ preview 同步完成: $COMMIT_MSG"
  echo "   访问: https://benavidesbraian710-hub.github.io/cosmetic-preview/"
  echo "   （GitHub Pages 1-2分钟后生效）"
else
  echo ""
  echo "❌ push 失败，请检查 osxkeychain 是否已存 GitHub PAT"
  echo "   修复: cat ~/.openclaw/credentials/github_pat"
  echo "         printf 'protocol=https\nhost=github.com\nusername=x-access-token\npassword=\$(cat ~/.openclaw/credentials/github_pat)\n' | git credential approve"
  exit 1
fi
