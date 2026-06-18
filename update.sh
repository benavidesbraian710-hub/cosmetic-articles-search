#!/bin/bash

# 化妆品文章检索系统 - 完整更新流程
# 支持多种采集方式

echo "=========================================="
echo "  化妆品文章检索系统 - 数据更新"
echo "=========================================="
echo ""

cd /Users/yuming.chen/.openclaw/workspace/cosmetic-deploy

# 显示菜单
echo "请选择采集方式:"
echo "1. 从 wechat-macos-proxy 采集 (需要安装 skill)"
echo "2. 从剪贴板提取链接"
echo "3. 从 CSV 文件导入"
echo "4. 手动添加单篇文章"
echo "5. 直接导出当前数据到网站"
echo ""

read -p "请输入选项 (1-5): " choice

case $choice in
    1)
        echo ""
        echo "📤 使用 wechat-macos-proxy 采集..."
        python3 collect_from_wechat_mac.py
        ;;
    2)
        echo ""
        echo "📋 从剪贴板提取..."
        python3 extract_from_clipboard.py
        ;;
    3)
        echo ""
        echo "📁 从 CSV 导入..."
        read -p "请输入 CSV 文件路径: " csv_file
        if [ -f "$csv_file" ]; then
            python3 -c "
import sys
sys.path.insert(0, '.')
from collect_mac import WeChatArticleCollectorMac
collector = WeChatArticleCollectorMac()
collector.import_from_csv('$csv_file')
"
        else
            echo "❌ 文件不存在: $csv_file"
            exit 1
        fi
        ;;
    4)
        echo ""
        echo "📝 手动添加..."
        python3 collect_mac.py
        ;;
    5)
        echo ""
        echo "📤 直接导出数据..."
        ;;
    *)
        echo "❌ 无效选项"
        exit 1
        ;;
esac

# 导出数据到 JSON
echo ""
echo "📤 导出数据到网站..."
python3 export_data.py

if [ $? -ne 0 ]; then
    echo "❌ 导出失败"
    exit 1
fi

# 推送到 GitHub
echo ""
echo "🚀 推送到 GitHub 部署..."
git add data.json
git commit -m "数据更新: $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 更新成功！"
    echo ""
    echo "网站地址: https://benavidesbraian710-hub.github.io/cosmetic-articles-search/"
    echo "等待 1-2 分钟后刷新查看"
else
    echo "❌ 推送失败"
    exit 1
fi

echo ""
echo "=========================================="