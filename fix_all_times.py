#!/usr/bin/env python3
"""
修复文章发布时间 - 使用多种方法获取真实时间
"""

import sqlite3
import urllib.request
import re
from pathlib import Path
from datetime import datetime
import time

DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"

def fetch_article_time(url: str) -> str:
    """从文章链接获取真实发布时间"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://mp.weixin.qq.com/',
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            html = response.read().decode('utf-8')
        
        # 检查是否被拦截
        if '环境异常' in html or '完成验证' in html:
            return None
        
        # 方法1: 从 s1s_context_info 中提取 URL编码的 JSON 时间戳
        m = re.search(r'publish_time%22%3A(\d{10})', html)
        if m:
            try:
                ts = int(m.group(1))
                return datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            except:
                pass
        
        # 方法2: 从 JSON 中提取时间戳
        m = re.search(r'"publish_time"\s*:\s*(\d{10})', html)
        if m:
            try:
                ts = int(m.group(1))
                return datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            except:
                pass
        
        # 方法3: 从页面元素获取
        m = re.search(r'id="publish_time"[^>]*>(.*?)</em>', html, re.DOTALL)
        if m:
            date_str = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if date_str:
                try:
                    return datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
                except:
                    pass
        
        # 方法4: 从页面中提取所有日期，使用第一个合理的日期
        dates = re.findall(r'(\d{4}-\d{2}-\d{2})', html)
        if dates:
            # 过滤掉不合理的日期（如2024年之前的）
            valid_dates = [d for d in dates if d >= '2024-01-01']
            if valid_dates:
                return valid_dates[0]
        
        return None
        
    except Exception as e:
        print(f"  ⚠️ 抓取失败: {e}")
        return None


def fix_all_articles():
    """修复所有文章的时间"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取所有文章
    cursor.execute("SELECT id, url, title, publish_date FROM articles ORDER BY id")
    articles = cursor.fetchall()
    
    print(f"共 {len(articles)} 篇文章需要检查")
    print("=" * 60)
    
    updated = 0
    failed = 0
    correct = 0
    
    for i, (article_id, url, title, old_date) in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] {title[:50]}...")
        print(f"  旧日期: {old_date}")
        
        real_date = fetch_article_time(url)
        
        if real_date:
            if real_date != old_date:
                cursor.execute(
                    "UPDATE articles SET publish_date = ? WHERE id = ?",
                    (real_date, article_id)
                )
                conn.commit()
                print(f"  ✅ 更新为: {real_date}")
                updated += 1
            else:
                print(f"  ✅ 时间正确")
                correct += 1
        else:
            print(f"  ⚠️ 无法获取真实时间")
            failed += 1
        
        # 每10篇文章暂停2秒
        if i % 10 == 0:
            print(f"\n  ⏸️ 暂停2秒...")
            time.sleep(2)
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"✅ 完成！")
    print(f"   更新: {updated} 篇")
    print(f"   正确: {correct} 篇")
    print(f"   失败: {failed} 篇")
    print(f"   总计: {len(articles)} 篇")


if __name__ == "__main__":
    print("=" * 60)
    print("  修复所有文章的发布时间为真实时间")
    print("=" * 60)
    print()
    
    fix_all_articles()
