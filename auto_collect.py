#!/usr/bin/env python3
"""
微信公众号文章采集器 - 一键采集+入库

正确流程：
1. 运行 wechat-article-collector (Mac) 生成 CSV
2. 读取 CSV 提取文章链接
3. 入库到 cosmetic_articles.db
4. 导出 data.json 并推送 GitHub

使用方法：
    python3 auto_collect.py '获取妆合规最新5篇文章'
    python3 auto_collect.py '搜索妆合规关于法规的3篇文章'
    python3 auto_collect.py '{"tasks":[{"account":"妆合规","count":5}]}'
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

# 路径配置
COLLECTOR_PATH = Path.home() / ".openclaw/workspace/wechat-collector/skills/wechat-article-collector/scripts/collect.py"
CSV_IMPORTER = Path.home() / ".openclaw/workspace/cosmetic-deploy/collect_from_csv.py"
EXPORT_SCRIPT = Path.home() / ".openclaw/workspace/cosmetic-deploy/export_data.py"
PROJECT_DIR = Path.home() / ".openclaw/workspace/cosmetic-deploy"


def run_collector(command):
    """运行 wechat-article-collector"""
    if not COLLECTOR_PATH.exists():
        print(f"❌ 采集器未找到: {COLLECTOR_PATH}")
        return False
    
    print(f"🚀 开始采集: {command}")
    print("⚠️  请确保微信窗口在前台，不要操作鼠标键盘")
    print("")
    
    try:
        result = subprocess.run(
            ["python3", str(COLLECTOR_PATH), command],
            capture_output=False,
            text=True,
            timeout=300
        )
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ 采集超时")
        return False
    except Exception as e:
        print(f"❌ 采集出错: {e}")
        return False


def import_csv():
    """导入最新的 CSV"""
    print("\n📥 导入采集结果...")
    
    try:
        result = subprocess.run(
            ["python3", str(CSV_IMPORTER)],
            capture_output=False,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False


def export_data():
    """导出数据到 JSON"""
    print("\n📤 导出数据到网站...")
    
    try:
        result = subprocess.run(
            ["python3", str(EXPORT_SCRIPT)],
            capture_output=False,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 导出失败: {e}")
        return False


def push_to_github():
    """推送到 GitHub"""
    print("\n🚀 推送到 GitHub 部署...")
    
    try:
        os.chdir(PROJECT_DIR)
        
        # 添加更改
        subprocess.run(["git", "add", "data.json"], check=True)
        
        # 提交
        commit_msg = f"数据更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        
        # 推送
        subprocess.run(["git", "push", "origin", "main"], check=True)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Git 操作失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 推送失败: {e}")
        return False


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("=" * 60)
        print("  微信公众号文章采集 - 一键采集+入库")
        print("=" * 60)
        print()
        print("用法:")
        print(f"  python3 {sys.argv[0]} '获取妆合规最新5篇文章'")
        print(f"  python3 {sys.argv[0]} '搜索妆合规关于法规的3篇文章'")
        print(f"  python3 {sys.argv[0]} '{{\"tasks\":[{{\"account\":\"妆合规\",\"count\":5}}]}}'")
        print()
        print("流程:")
        print("  1. 运行 wechat-article-collector 采集文章")
        print("  2. 读取 CSV 导入数据库")
        print("  3. 导出 data.json")
        print("  4. 推送到 GitHub 更新网站")
        sys.exit(1)
    
    command = sys.argv[1]
    
    print("=" * 60)
    print("  微信公众号文章采集 - 一键采集+入库")
    print("=" * 60)
    print()
    
    # 1. 采集文章
    if not run_collector(command):
        print("\n❌ 采集失败")
        sys.exit(1)
    
    print("\n✅ 采集完成")
    
    # 2. 导入 CSV
    if not import_csv():
        print("\n❌ 导入失败")
        sys.exit(1)
    
    # 3. 导出数据
    if not export_data():
        print("\n❌ 导出失败")
        sys.exit(1)
    
    # 4. 推送 GitHub
    if not push_to_github():
        print("\n❌ 推送失败")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ 全部完成！")
    print("=" * 60)
    print()
    print("网站地址: https://benavidesbraian710-hub.github.io/cosmetic-articles-search/")
    print("等待 1-2 分钟后刷新查看")


if __name__ == "__main__":
    main()
