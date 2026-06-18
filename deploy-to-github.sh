#!/bin/bash

# 化妆品文章检索系统 - 部署到 GitHub
# 用户名: benavidesbraian710-hub

echo "=========================================="
echo "  推送代码到 GitHub"
echo "=========================================="
echo ""

cd /Users/yuming.chen/.openclaw/workspace/cosmetic-deploy

# 检查是否有未提交的更改
if [ -n "$(git status --porcelain)" ]; then
    echo "📝 提交更改..."
    git add .
    git commit -m "v1.0.0 Basic版本 - 可选择导出、跨公众号多选、中文乱码修复"
fi

# 推送代码
echo "🚀 推送到 GitHub..."
echo ""
echo "⚠️  提示：需要输入 GitHub 密码或 Personal Access Token"
echo ""

git branch -M main
git push -u origin main

echo ""
echo "=========================================="
echo "  完成！"
echo "=========================================="