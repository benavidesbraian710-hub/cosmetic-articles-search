#!/bin/bash

# 化妆品文章检索系统 - 完整更新流程
# 1. 运行 wechat-article-collector 获取新文章
# 2. 导出数据到 data.json
# 3. 推送到 GitHub 自动部署

echo "=========================================="
echo "  化妆品文章检索系统 - 完整更新流程"
echo "=========================================="
echo ""

# 设置路径
PROJECT_DIR="/Users/yuming.chen/.openclaw/workspace/cosmetic-deploy"
DB_PATH="/Users/yuming.chen/.openclaw/cosmetic_articles.db"

cd "$PROJECT_DIR"

# 步骤1: 检查是否有新文章（可选）
echo "📥 步骤1: 检查数据库状态..."
python3 -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM articles')
count = cursor.fetchone()[0]
cursor.execute('SELECT MAX(created_at) FROM articles')
latest = cursor.fetchone()[0]
conn.close()
print(f'数据库文章数: {count}')
print(f'最新文章时间: {latest}')
"

# 步骤2: 导出数据
echo ""
echo "📤 步骤2: 导出数据到 JSON..."
python3 export_data.py

if [ $? -ne 0 ]; then
    echo "❌ 导出失败"
    exit 1
fi

# 步骤3: 推送到 GitHub
echo ""
echo "🚀 步骤3: 推送到 GitHub 部署..."
git add data.json
git commit -m "数据更新: $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 更新成功！"
    echo ""
    echo "网站地址: https://benavidesbraian710-hub.github.io/cosmetic-articles-search/"
    echo "等待 1-2 分钟后刷新网站查看更新"
else
    echo "❌ 推送失败"
    exit 1
fi

echo ""
echo "=========================================="
