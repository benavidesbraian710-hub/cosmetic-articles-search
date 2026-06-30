#!/usr/bin/env python3
"""
全量采集脚本 - 网页版
通过直接抓取网页获取文章，不依赖微信客户端
"""

import sqlite3
import json
import urllib.request
import re
from pathlib import Path
from datetime import datetime

# 数据库路径
DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"

# 公众号列表
ACCOUNTS = [
    {"name": "妆研24小时", "biz": ""},
    {"name": "非科学美妆传播", "biz": ""},
    {"name": "原料合规观察", "biz": ""},
    {"name": "妆合规", "biz": ""},
    {"name": "Fbeauty未来迹", "biz": ""},
    {"name": "个护前沿", "biz": ""},
    {"name": "KEV美妆", "biz": ""},
    {"name": "美业颜究院", "biz": ""},
    {"name": "美妆内行人", "biz": ""},
    {"name": "肤见未来实验室", "biz": ""},
    {"name": "个护前言", "biz": ""},
    {"name": "Beauty Insider", "biz": ""},
    {"name": "化妆品观察 品观", "biz": ""},
    {"name": "中国化妆品", "biz": ""},
    {"name": "上海日化协会", "biz": ""}
]


def ensure_db():
    """确保数据库存在"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            wechat_name TEXT NOT NULL,
            publish_date TEXT,
            content TEXT,
            keywords TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def fetch_article_info(url):
    """抓取文章信息"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://mp.weixin.qq.com/',
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            html = response.read().decode('utf-8')
        
        if "环境异常" in html or "完成验证" in html:
            return None
        
        # 解析标题
        title = None
        title_match = re.search(r'<h1[^>]*class="rich_media_title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL)
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
        
        # 解析发布时间
        publish_date = None
        m = re.search(r'publish_time%22%3A(\d{10})', html)
        if m:
            try:
                ts = int(m.group(1))
                dt = datetime.fromtimestamp(ts)
                publish_date = dt.strftime('%Y-%m-%d')
            except:
                pass
        
        if not publish_date:
            m = re.search(r'"publish_time"\s*:\s*(\d{10})', html)
            if m:
                try:
                    ts = int(m.group(1))
                    dt = datetime.fromtimestamp(ts)
                    publish_date = dt.strftime('%Y-%m-%d')
                except:
                    pass
        
        if not publish_date:
            dates = re.findall(r'(\d{4}-\d{2}-\d{2})', html)
            if dates:
                valid_dates = [d for d in dates if d >= '2024-01-01']
                if valid_dates:
                    publish_date = valid_dates[0]
        
        return {
            "title": title or "未知标题",
            "publish_date": publish_date or datetime.now().strftime('%Y-%m-%d')
        }
    except Exception as e:
        print(f"  ⚠️ 抓取失败: {e}")
        return None


def add_article(url, source_name, title=None, publish_date=None):
    """添加文章到数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查是否已存在
    cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
    if cursor.fetchone():
        conn.close()
        return False
    
    # 如果没有提供标题，抓取网页
    if not title:
        info = fetch_article_info(url)
        if info:
            title = info["title"]
            publish_date = info["publish_date"]
        else:
            title = f"{source_name} 文章"
            publish_date = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute("""
        INSERT INTO articles (title, url, wechat_name, publish_date, content, keywords, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        url,
        source_name,
        publish_date,
        '',
        json.dumps([]),
        datetime.now().isoformat()
    ))
    
    conn.commit()
    conn.close()
    return True


def get_stats():
    """获取统计信息"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM articles")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT wechat_name) FROM articles")
    sources = cursor.fetchone()[0]
    
    cursor.execute("SELECT wechat_name, COUNT(*) as count FROM articles GROUP BY wechat_name ORDER BY count DESC")
    stats = cursor.fetchall()
    
    conn.close()
    
    return total, sources, stats


def main():
    print("=" * 60)
    print("微信公众号全量采集 - 网页版")
    print("=" * 60)
    
    ensure_db()
    
    # 显示当前状态
    total, sources, stats = get_stats()
    print(f"\n当前数据库状态:")
    print(f"  总文章数: {total}")
    print(f"  公众号数: {sources}")
    print(f"\n各公众号文章数:")
    for name, count in stats:
        print(f"  {name}: {count}篇")
    
    print("\n" + "=" * 60)
    print("注意: 网页版采集需要手动提供文章链接")
    print("请使用 wechat-article-collector 工具采集 CSV 后导入")
    print("=" * 60)


if __name__ == "__main__":
    main()
