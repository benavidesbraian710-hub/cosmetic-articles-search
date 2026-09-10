#!/bin/bash
# 数据库同步脚本：Mac mini → ECS
# 用途：把 Mac mini 本地的 cosmetic_articles.db 推到 ECS 并重启 API 服务
# 触发：每次 export_data.py 完成后自动调用（也可手动）
#
# 流程：
#   1. 验证本地数据库存在
#   2. SCP 数据库到 ECS /tmp/
#   3. ECS 上：备份旧库 → 替换新库 → 改权限 → 重启 cosmetic-api 服务
#   4. 验证 ECS API 返回的文章数 == 本地数据库文章数
#
# 用法：bash sync_db_to_ecs.sh

set -e

# ============ 配置 ============
WORKSPACE="$HOME/.openclaw/workspace/cosmetic-deploy"
DB_FILE="$WORKSPACE/cosmetic_articles.db"
ECS_HOST="root@8.133.238.76"
ECS_PASS="Clarins202020"
ECS_DB_DIR="/opt/cosmetic-api/data"
ECS_SERVICE="cosmetic-api"
PYTHON="/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python"

# ============ Step 1: 验证本地数据库 ============
if [ ! -f "$DB_FILE" ]; then
    echo "❌ 错误：本地数据库不存在: $DB_FILE"
    exit 1
fi

LOCAL_SIZE=$(stat -f%z "$DB_FILE" 2>/dev/null || stat -c%s "$DB_FILE")
LOCAL_TOTAL=$($PYTHON -c "
import sqlite3
db = sqlite3.connect('$DB_FILE')
cur = db.cursor()
cur.execute('SELECT COUNT(*) FROM articles')
print(cur.fetchone()[0])
" 2>/dev/null)

if [ -z "$LOCAL_TOTAL" ] || [ "$LOCAL_TOTAL" -eq 0 ]; then
    echo "❌ 错误：本地数据库无文章记录"
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
echo "📦 本地数据库: $(basename $DB_FILE)"
echo "   大小: $LOCAL_SIZE bytes"
echo "   文章数: $LOCAL_TOTAL 篇"
echo "   时间戳: $TIMESTAMP"
echo ""

# ============ Step 2: SCP 到 ECS 临时目录 ============
echo "📤 步骤 1/3：传输到 ECS..."
sshpass -p "$ECS_PASS" scp -o StrictHostKeyChecking=no \
    "$DB_FILE" "$ECS_HOST:/tmp/cosmetic_articles.db.new" 2>&1 | grep -v "Warning" || true

# 验证文件传输成功
REMOTE_SIZE=$(sshpass -p "$ECS_PASS" ssh -o StrictHostKeyChecking=no "$ECS_HOST" \
    'stat -c "%s" /tmp/cosmetic_articles.db.new 2>/dev/null || stat -f "%z" /tmp/cosmetic_articles.db.new' 2>/dev/null)

if [ "$REMOTE_SIZE" != "$LOCAL_SIZE" ]; then
    echo "❌ 错误：传输后大小不匹配（本地 $LOCAL_SIZE vs ECS $REMOTE_SIZE）"
    sshpass -p "$ECS_PASS" ssh -o StrictHostKeyChecking=no "$ECS_HOST" 'rm -f /tmp/cosmetic_articles.db.new' 2>/dev/null
    exit 1
fi
echo "   ✅ 传输完成（$REMOTE_SIZE bytes）"
echo ""

# ============ Step 3: ECS 上替换数据库 + 重启服务 ============
echo "🔄 步骤 2/3：在 ECS 上更新数据库..."
sshpass -p "$ECS_PASS" ssh -o StrictHostKeyChecking=no "$ECS_HOST" bash -s "$TIMESTAMP" << 'EOF'
set -e
TIMESTAMP="$1"

# 备份旧库
echo "   备份旧库..."
cp /opt/cosmetic-api/data/cosmetic_articles.db \
   /opt/cosmetic-api/data/cosmetic_articles.db.backup-$TIMESTAMP

# 替换为新库
echo "   替换数据库..."
cp /tmp/cosmetic_articles.db.new /opt/cosmetic-api/data/cosmetic_articles.db

# 改权限（systemd 服务以 www-data 运行）
chown www-data:www-data /opt/cosmetic-api/data/cosmetic_articles.db

# 清理临时文件
rm /tmp/cosmetic_articles.db.new

# 重启服务
echo "   重启 cosmetic-api 服务..."
systemctl restart cosmetic-api
sleep 3

# 验证服务状态
if systemctl is-active --quiet cosmetic-api; then
    echo "   ✅ 服务已重启"
else
    echo "   ❌ 服务启动失败"
    systemctl status cosmetic-api --no-pager | head -20
    exit 1
fi
EOF

echo ""

# ============ Step 4: 验证同步结果 ============
echo "🔍 步骤 3/3：验证同步结果..."
sleep 2
REMOTE_TOTAL=$(sshpass -p "$ECS_PASS" ssh -o StrictHostKeyChecking=no "$ECS_HOST" \
    "curl -sS http://127.0.0.1:8000/api/stats 2>/dev/null | /opt/cosmetic-api/venv/bin/python3 -c 'import sys, json; print(json.load(sys.stdin)[\"total_articles\"])'" 2>/dev/null)

if [ "$LOCAL_TOTAL" = "$REMOTE_TOTAL" ]; then
    echo "   ✅ 同步成功！本地 $LOCAL_TOTAL 篇 = ECS $REMOTE_TOTAL 篇"
else
    echo "   ⚠️ 数量不匹配：本地 $LOCAL_TOTAL 篇 vs ECS $REMOTE_TOTAL 篇"
    exit 1
fi

echo ""
echo "✅ 数据库同步完成：$TIMESTAMP"
echo "   ECS 备份: /opt/cosmetic-api/data/cosmetic_articles.db.backup-$TIMESTAMP"
