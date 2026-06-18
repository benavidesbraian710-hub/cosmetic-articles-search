#!/usr/bin/env python3
"""
微信公众号文章采集器 - Mac 整合版
连接 wechat-article-collector (Mac) 和 cosmetic_articles 数据库

功能：
1. 使用 peekaboo 采集微信公众号文章链接
2. 自动入库到 cosmetic_articles.db
3. 支持自然语言指令

前置要求：
- 安装 peekaboo: brew install steipete/tap/peekaboo
- 微信 Mac 版已登录
- 屏幕坐标适配（根据实际分辨率调整）

使用方法：
    python3 collect_and_save.py '<JSON配置>'
    python3 collect_and_save.py '获取妆合规最新5篇文章'
"""

import sqlite3
import json
import csv
import time
import sys
import re
import subprocess
from pathlib import Path
from datetime import datetime

# 数据库路径
DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"

# Mac 版采集器路径
COLLECTOR_PATH = Path.home() / ".openclaw/workspace/wechat-collector/skills/wechat-article-collector/scripts/collect.py"


class WeChatArticleCollector:
    """Mac 版微信文章采集器（整合版）"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.ensure_db_exists()
    
    def ensure_db_exists(self):
        """确保数据库存在"""
        conn = sqlite3.connect(self.db_path)
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
    
    def add_article(self, title, url, source, publish_date=None, summary=""):
        """添加文章到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if not publish_date:
            publish_date = datetime.now().strftime("%Y-%m-%d")
        
        # 检查是否已存在
        cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
        if cursor.fetchone():
            print(f"⚠️  文章已存在: {title}")
            conn.close()
            return False
        
        # 插入文章
        cursor.execute("""
            INSERT INTO articles (title, url, source, publish_date, summary, keywords, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, url, source, publish_date, summary, json.dumps([]), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        print(f"✅ 已入库: {title}")
        return True
    
    def collect_articles(self, tasks):
        """
        采集文章并入库
        
        Args:
            tasks: [{"account": "公众号", "keyword": "关键词", "count": 数量}]
        """
        if not COLLECTOR_PATH.exists():
            print(f"❌ 采集器未找到: {COLLECTOR_PATH}")
            print("请确认 wechat-article-collector 已安装")
            return []
        
        # 1. 运行采集器获取 CSV
        config = {"tasks": tasks}
        config_json = json.dumps(config, ensure_ascii=False)
        
        print(f"\n🚀 开始采集...")
        print(f"配置: {config_json}")
        
        try:
            result = subprocess.run(
                ["python3", str(COLLECTOR_PATH), config_json],
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            print(result.stdout)
            
            if result.returncode != 0:
                print(f"❌ 采集失败: {result.stderr}")
                return []
            
        except subprocess.TimeoutExpired:
            print("❌ 采集超时")
            return []
        except Exception as e:
            print(f"❌ 采集出错: {e}")
            return []
        
        # 2. 查找生成的 CSV 文件
        desktop = Path.home() / "Desktop"
        csv_files = sorted(desktop.glob("wechat_articles_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        if not csv_files:
            print("❌ 未找到采集结果 CSV")
            return []
        
        latest_csv = csv_files[0]
        print(f"\n📁 找到采集结果: {latest_csv}")
        
        # 3. 读取 CSV 并入库
        collected = []
        with open(latest_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                account = row.get('公众号', '')
                link = row.get('链接', '')
                keyword = row.get('关键词', '')
                
                if not link:
                    continue
                
                # 生成标题
                title = f"{account} 文章"
                if keyword and keyword != '-':
                    title += f" ({keyword})"
                
                # 入库
                if self.add_article(title, link, account):
                    collected.append({
                        'title': title,
                        'url': link,
                        'source': account
                    })
        
        print(f"\n✅ 采集完成: 新增 {len(collected)} 篇文章")
        return collected
    
    def get_stats(self):
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
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
    collector = WeChatArticleCollector()
    
    print("=" * 60)
    print("  微信公众号文章采集器 - Mac 整合版")
    print("=" * 60)
    print()
    
    if len(sys.argv) < 2:
        print("用法:")
        print(f"  python3 {sys.argv[0]} '<JSON配置>'")
        print(f"  python3 {sys.argv[0]} '获取妆合规最新5篇文章'")
        print()
        print("示例 JSON:")
        print('  \'{"tasks":[{"account":"妆合规","count":5}]}\'')
        print()
        print("自然语言示例:")
        print('  "获取妆合规最新5篇文章"')
        print('  "搜索个护前言关于法规的3篇文章"')
        print('  "先获取妆合规5篇，再获取个护前言3篇"')
        sys.exit(1)
    
    input_text = sys.argv[1]
    
    # 解析输入
    try:
        config = json.loads(input_text)
        tasks = config.get('tasks', [])
    except json.JSONDecodeError:
        # 尝试自然语言解析
        tasks = parse_natural_language(input_text)
    
    if not tasks:
        print("❌ 无法解析输入")
        sys.exit(1)
    
    print(f"共 {len(tasks)} 个任务:")
    for i, task in enumerate(tasks, 1):
        keyword = task.get('keyword', '')
        keyword_str = f" 关键词:{keyword}" if keyword else ''
        print(f"  {i}. {task['account']}  {task['count']}篇{keyword_str}")
    
    # 确认执行
    confirm = input("\n确认执行采集? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        sys.exit(0)
    
    # 执行采集
    collected = collector.collect_articles(tasks)
    
    # 显示统计
    print("\n" + "=" * 60)
    collector.get_stats()
    
    print("\n" + "=" * 60)
    print(f"✅ 完成！共新增 {len(collected)} 篇文章")


def parse_natural_language(text: str) -> list:
    """解析自然语言为任务列表"""
    tasks = []
    
    # 模式1: 获取/搜索 + 公众号 + 关键词 + 数量
    pattern1 = r'(?:获取|搜索)\s*([^\s]+)\s*(?:关于|搜索)?\s*([^\d\s]*)\s*(?:的)?\s*(\d*)\s*篇'
    matches = re.findall(pattern1, text)
    
    for account, keyword, count in matches:
        tasks.append({
            'account': account.strip(),
            'keyword': keyword.strip() or '',
            'count': int(count) if count.strip() else 1
        })
    
    return tasks


if __name__ == "__main__":
    main()
