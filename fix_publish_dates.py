#!/usr/bin/env python3
"""
修复所有文章的发布时间为真实时间
"""

import sqlite3
import urllib.request
import re
from pathlib import Path
from datetime import datetime
import time

DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"


def fetch_real_publish_date(url: str) -> str:
    """从文章页面获取真实发布时间"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://mp.weixin.qq.com/',
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            text = response.read().decode('utf-8')
        
        # 检查是否被拦截
        if '环境异常' in text or '完成验证' in text:
            return None
        
        # 方法1: 从 s1s_context_info 中提取 URL编码的 JSON 中的 publish_time 时间戳
        m = re.search(r'publish_time%22%3A(\d{10})', text)
        if m:
            try:
                ts = int(m.group(1))
                return datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            except:
                pass
        
        # 方法2: 从 s1s_context_info 中提取已解码的 JSON 时间戳
        m = re.search(r'"publish_time"\s*:\s*(\d{10})', text)
        if m:
            try:
                ts = int(m.group(1))
                return datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            except:
                pass
        
        # 方法3: 从页面中的 publish_time 元素获取（JS渲染后的）
        m = re.search(r'id="publish_time"[^>]*>(.*?)</em>', text, re.DOTALL)
        if m:
            date_str = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if date_str:
                try:
                    return datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
                except:
                    pass
        
        return None
        
    except Exception as e:
        print(f"  ⚠️ 抓取失败: {e}")
        return None


def fix_all_publish_dates():
    """修复所有文章的发布时间"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取所有文章
    cursor.execute("SELECT id, url, title, publish_date FROM articles ORDER BY id")
    articles = cursor.fetchall()
    
    print(f"共 {len(articles)} 篇文章需要检查")
    print("=" * 60)
    
    updated = 0
    failed = 0
    skipped = 0
    
    for i, (article_id, url, title, old_date) in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] {title[:50]}...")
        print(f"  旧日期: {old_date}")
        
        # 获取真实时间
        real_date = fetch_real_publish_date(url)
        
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
                skipped += 1
        else:
            print(f"  ⚠️ 无法获取真实时间")
            failed += 1
        
        # 每10篇文章暂停2秒，避免请求过快
        if i % 10 == 0:
            print(f"\n  ⏸️ 暂停2秒...")
            time.sleep(2)
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"✅ 完成！")
    print(f"   更新: {updated} 篇")
    print(f"   正确: {skipped} 篇")
    print(f"   失败: {failed} 篇")
    print(f"   总计: {len(articles)} 篇")


if __name__ == "__main__":
    print("=" * 60)
    print("  修复所有文章的发布时间为真实时间")
    print("=" * 60)
    print()
    
    fix_all_publish_dates()
