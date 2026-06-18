#!/usr/bin/env python3
"""
微信公众号文章采集器 - 正确整合版

正确流程：
1. 运行 wechat-article-collector (Mac) 生成 CSV
2. 读取 CSV 提取文章链接
3. 入库到 cosmetic_articles.db
4. 导出 data.json 并推送 GitHub

前置要求：
- 安装 peekaboo: brew install steipete/tap/peekaboo
- 微信 Mac 版已登录
- 屏幕坐标适配（根据实际分辨率调整）

使用方法：
    # 方式1：先采集，后入库
    python3 /Users/yuming.chen/.openclaw/workspace/wechat-collector/skills/wechat-article-collector/scripts/collect.py '获取妆合规最新5篇文章'
    python3 collect_from_csv.py

    # 方式2：一键采集+入库
    python3 auto_collect.py '获取妆合规最新5篇文章'
"""

import sqlite3
import json
import csv
import os
import sys
import subprocess
import glob
from pathlib import Path
from datetime import datetime

# 数据库路径
DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"

# 采集器路径
COLLECTOR_PATH = Path.home() / ".openclaw/workspace/wechat-collector/skills/wechat-article-collector/scripts/collect.py"


def ensure_db_exists():
    """确保数据库存在"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            publish_date TEXT,
            summary TEXT,
            keywords TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()


def find_latest_csv():
    """查找桌面最新的 wechat_articles CSV 文件"""
    desktop = Path.home() / "Desktop"
    csv_files = list(desktop.glob("wechat_articles_*.csv"))
    
    if not csv_files:
        return None
    
    # 按修改时间排序，取最新的
    latest = sorted(csv_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    return latest


def import_from_csv(csv_path, source_name=None):
    """从 CSV 导入文章到数据库"""
    if not os.path.exists(csv_path):
        print(f"❌ 文件不存在: {csv_path}")
        return 0
    
    ensure_db_exists()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    added = 0
    skipped = 0
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 获取字段
            account = row.get('公众号', '')
            link = row.get('链接', '')
            keyword = row.get('关键词', '-')
            
            if not link or not link.startswith('http'):
                continue
            
            # 使用传入的 source_name 或 CSV 中的公众号名称
            source = source_name or account or '未知公众号'
            
            # 生成标题
            title = f"{source} 文章"
            if keyword and keyword != '-':
                title += f" ({keyword})"
            
            # 检查是否已存在
            cursor.execute("SELECT id FROM articles WHERE url = ?", (link,))
            if cursor.fetchone():
                skipped += 1
                continue
            
            # 插入文章
            cursor.execute("""
                INSERT INTO articles (title, url, source, publish_date, summary, keywords, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                title,
                link,
                source,
                datetime.now().strftime("%Y-%m-%d"),
                '',
                json.dumps([keyword] if keyword and keyword != '-' else []),
                datetime.now().isoformat()
            ))
            added += 1
    
    conn.commit()
    conn.close()
    
    print(f"✅ 导入完成: {csv_path}")
    print(f"   新增: {added} 篇")
    print(f"   跳过: {skipped} 篇")
    
    return added


def run_collector(command):
    """运行 wechat-article-collector"""
    if not COLLECTOR_PATH.exists():
        print(f"❌ 采集器未找到: {COLLECTOR_PATH}")
        return False
    
    print(f"🚀 运行采集器: {command}")
    print("⚠️  请确保微信窗口在前台，不要操作鼠标键盘")
    print("")
    
    try:
        result = subprocess.run(
            ["python3", str(COLLECTOR_PATH), command],
            capture_output=False,  # 显示实时输出
            text=True,
            timeout=300  # 5分钟超时
        )
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ 采集超时")
        return False
    except Exception as e:
        print(f"❌ 采集出错: {e}")
        return False


def get_stats():
    """获取统计信息"""
    ensure_db_exists()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM articles")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT source) FROM articles")
    sources = cursor.fetchone()[0]
    
    cursor.execute("SELECT source, COUNT(*) as count FROM articles GROUP BY source ORDER BY count DESC")
    source_list = cursor.fetchall()
    
    conn.close()
    
    print(f"\n📊 数据库统计:")
    print(f"   总文章数: {total}")
    print(f"   公众号数: {sources}")
    print(f"\n📰 公众号列表:")
    for source, count in source_list:
        print(f"   {source}: {count}篇")
    
    return total, sources


def main():
    """主函数"""
    print("=" * 60)
    print("  微信公众号文章采集 - CSV 导入工具")
    print("=" * 60)
    print()
    
    if len(sys.argv) > 1:
        # 指定了 CSV 文件路径
        csv_path = sys.argv[1]
        if os.path.exists(csv_path):
            import_from_csv(csv_path)
        else:
            print(f"❌ 文件不存在: {csv_path}")
    else:
        # 自动查找最新的 CSV
        latest_csv = find_latest_csv()
        
        if latest_csv:
            print(f"📁 找到最新采集结果: {latest_csv}")
            print(f"   修改时间: {datetime.fromtimestamp(latest_csv.stat().st_mtime)}")
            print()
            
            confirm = input("是否导入此文件? (y/n): ").strip().lower()
            if confirm == 'y':
                # 询问公众号名称（可选）
                source_name = input("请输入公众号名称 (直接回车使用CSV中的名称): ").strip()
                if not source_name:
                    source_name = None
                
                import_from_csv(latest_csv, source_name)
            else:
                print("已取消")
        else:
            print("❌ 未找到 wechat_articles_*.csv 文件")
            print()
            print("请先运行采集器:")
            print(f"  python3 {COLLECTOR_PATH} '获取妆合规最新5篇文章'")
    
    # 显示统计
    print("\n" + "=" * 60)
    get_stats()


if __name__ == "__main__":
    main()
