#!/bin/bash
# Mac mini 端：每日定时将数据库推送到 GitHub，让 ECS 能 git pull
# 用法：bash sync_db_to_ecs.sh

set -e

WORKSPACE="$HOME/.openclaw/workspace/cosmetic-deploy"
DB_FILE="$WORKSPACE/cosmetic_articles.db"

echo "=== 复制数据库到 api-server/data/ ==="
mkdir -p "$WORKSPACE/api-server/data"
cp "$DB_FILE" "$WORKSPACE/api-server/data/cosmetic_articles.db"

echo "=== 推送到 GitHub ==="
cd "$WORKSPACE"
git add api-server/data/cosmetic_articles.db api-server/main.py api-server/requirements.txt
git commit -m "data: 同步最新数据库到 api-server ($(date +%Y-%m-%d))" 2>/dev/null || echo "⚠️ 无变更"

# 仅推送到 feature/new-arch 分支
git push origin feature/new-arch

echo "✅ 数据库已推送，ECS 每小时自动 pull + restart"