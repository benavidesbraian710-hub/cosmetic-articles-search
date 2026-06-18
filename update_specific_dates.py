#!/usr/bin/env python3
"""
更新特定文章的发布时间为真实时间
"""

import sqlite3
import subprocess
import re
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"


def clean_html(text: str) -> str:
    """清理 HTML 标签和实体"""
    text = re.sub(r'<[^>]+?>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&quot;', '"')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def fetch_article_info(url: str) -> dict:
    """curl 抓取文章 HTML，解析真实标题和发布时间"""
    try:
        cmd = [
            "curl", "-s", "-L",
            "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "--max-time", "15",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        html = result.stdout
        
        # 解析发布时间
        publish_date = None
        # 方案1: 从 s1s_context_info 中提取 URL编码的 JSON 中的 publish_time 时间戳
        if not publish_date:
            m = re.search(r'publish_time%22%3A(\d{10})', html)
            if m:
                try:
                    ts = int(m.group(1))
                    dt = datetime.fromtimestamp(ts)
                    publish_date = dt.strftime('%Y-%m-%d')
                except:
                    pass
        # 方案2: 从 s1s_context_info 中提取已解码的 JSON 时间戳
        if not publish_date:
            m = re.search(r'"publish_time"\s*:\s*(\d{10})', html)
            if m:
                try:
                    ts = int(m.group(1))
                    dt = datetime.fromtimestamp(ts)
                    publish_date = dt.strftime('%Y-%m-%d')
                except:
                    pass
        # 方案3: 从页面中的 publish_time 元素获取（JS渲染后的）
        if not publish_date:
            m = re.search(r'id="publish_time"[^>]*>(.*?)</em>', html, re.DOTALL)
            if m:
                date_str = clean_html(m.group(1)).strip()
                if date_str:
                    try:
                        dt = datetime.strptime(date_str, '%Y-%m-%d')
                        publish_date = dt.strftime('%Y-%m-%d')
                    except:
                        pass
        
        return {
            "publish_date": publish_date or datetime.now().strftime('%Y-%m-%d')
        }
        
    except Exception as e:
        print(f"  ⚠️ 抓取失败: {e}")
        return {
            "publish_date": datetime.now().strftime('%Y-%m-%d')
        }


def update_specific_articles():
    """更新特定文章的发布时间"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取所有 publish_date 为 2026-06-18 的文章
    cursor.execute("SELECT id, url, title, publish_date FROM articles WHERE publish_date = '2026-06-18'")
    articles = cursor.fetchall()
    
    print(f"找到 {len(articles)} 篇需要更新的文章")
    
    updated = 0
    failed = 0
    
    for article_id, url, title, old_date in articles:
        print(f"\n[{updated + failed + 1}/{len(articles)}] 更新文章: {title[:50]}...")
        print(f"  旧日期: {old_date}")
        print(f"  URL: {url}")
        
        info = fetch_article_info(url)
        new_date = info['publish_date']
        
        if new_date != old_date:
            cursor.execute("UPDATE articles SET publish_date = ? WHERE id = ?", (new_date, article_id))
            conn.commit()
            print(f"  ✅ 新日期: {new_date}")
            updated += 1
        else:
            print(f"  ⏭️  日期未变: {new_date}")
        
        # 每篇文章暂停2秒，避免请求过快
        import time
        time.sleep(2)
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"✅ 完成！")
    print(f"   更新: {updated} 篇")
    print(f"   失败: {failed} 篇")
    print(f"   总计: {len(articles)} 篇")


if __name__ == "__main__":
    print("=" * 60)
    print("  更新特定文章的发布时间为真实时间")
    print("=" * 60)
    print()
    
    update_specific_articles()
