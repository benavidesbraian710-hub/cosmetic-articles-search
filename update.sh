#!/bin/bash

# 化妆品文章检索系统 - 完整更新流程
# 整合 Mac 版 wechat-article-collector 采集和网站更新

echo "=========================================="
echo "  化妆品文章检索系统 - 完整更新流程"
echo "=========================================="
echo ""

cd /Users/yuming.chen/.openclaw/workspace/cosmetic-deploy

# 显示菜单
echo "请选择操作:"
echo "1. 🚀 采集公众号文章并更新网站"
echo "2. 📥 从 CSV 导入文章"
echo "3. 📝 手动添加文章"
echo "4. 📊 查看统计信息"
echo "5. 🔄 仅更新网站数据"
echo "6. ❌ 退出"
echo ""

read -p "请输入选项 (1-6): " choice

case $choice in
    1)
        echo ""
        echo "🚀 采集公众号文章..."
        echo ""
        echo "用法示例:"
        echo "  JSON格式: '{"tasks":[{"account":"妆合规","count":5}]}'"
        echo "  自然语言: '获取妆合规最新5篇文章'"
        echo ""
        read -p "请输入采集指令: " collect_cmd
        
        if [ -n "$collect_cmd" ]; then
            python3 collect_and_save.py "$collect_cmd"
        else
            echo "❌ 指令不能为空"
            exit 1
        fi
        
        # 继续执行更新网站
        ;;
    
    2)
        echo ""
        echo "📥 从 CSV 导入..."
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
    
    3)
        echo ""
        echo "📝 手动添加文章..."
        python3 collect_mac.py
        ;;
    
    4)
        echo ""
        echo "📊 查看统计..."
        python3 -c "
from collect_and_save import WeChatArticleCollector
collector = WeChatArticleCollector()
collector.get_stats()
"
        ;;
    
    5)
        echo ""
        echo "🔄 仅更新网站数据..."
        ;;
    
    6)
        echo ""
        echo "👋 再见!"
        exit 0
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