#!/usr/bin/env python3
"""
使用 Playwright 获取微信文章真实发布时间
"""

import sqlite3
from playwright.sync_api import sync_playwright
from datetime import datetime
from pathlib import Path
import re

DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"

def fetch_article_time(url: str) -> str:
    """使用 Playwright 获取文章发布时间"""
    with sync_playwright() as p:
        # 启动浏览器（使用微信的 User-Agent）
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.0'
        )
        page = context.new_page()
        
        try:
            # 访问文章页面
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # 等待页面加载
            page.wait_for_timeout(2000)
            
            # 方法1: 从页面元素获取
            time_selectors = [
                '#publish_time',
                '.rich_media_meta_text',
                '#js_content em',
                'em[class*="time"]',
                'span[class*="time"]',
            ]
            
            for selector in time_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        text = element.inner_text().strip()
                        # 匹配日期格式
                        match = re.search(r'(\d{4})[-年](\d{2})[-月](\d{2})', text)
                        if match:
                            year, month, day = match.groups()
                            return f"{year}-{month}-{day}"
                except:
                    pass
            
            # 方法2: 从页面文本中提取
            page_text = page.inner_text('body')
            date_patterns = [
                r'(\d{4}-\d{2}-\d{2})',
                r'(\d{4}年\d{2}月\d{2}日)',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, page_text)
                if match:
                    date_str = match.group(1)
                    if '年' in date_str:
                        date_str = date_str.replace('年', '-').replace('月', '-').replace('日', '')
                    return date_str
            
            # 方法3: 从URL参数中提取
            # 微信文章URL有时包含时间参数
            
            return None
            
        except Exception as e:
            print(f"获取失败: {e}")
            return None
        finally:
            browser.close()


def fix_remaining_articles():
    """修复剩余文章的时间"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取没有正确时间的文章
    cursor.execute("""
        SELECT id, url, title, publish_date 
        FROM articles 
        WHERE publish_date = '' OR publish_date IS NULL
        ORDER BY id
    """)
    
    articles = cursor.fetchall()
    
    if not articles:
        print("没有需要修复的文章！")
        conn.close()
        return
    
    print(f"共 {len(articles)} 篇文章需要修复")
    print("=" * 60)
    
    updated = 0
    failed = 0
    
    for i, (article_id, url, title, old_date) in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] {title[:50]}...")
        
        real_date = fetch_article_time(url)
        
        if real_date:
            cursor.execute(
                "UPDATE articles SET publish_date = ? WHERE id = ?",
                (real_date, article_id)
            )
            conn.commit()
            print(f"  ✅ 更新为: {real_date}")
            updated += 1
        else:
            print(f"  ⚠️ 无法获取")
            failed += 1
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"✅ 完成！")
    print(f"   更新: {updated} 篇")
    print(f"   失败: {failed} 篇")


if __name__ == "__main__":
    print("=" * 60)
    print("  使用 Playwright 修复文章时间")
    print("=" * 60)
    print()
    
    fix_remaining_articles()
