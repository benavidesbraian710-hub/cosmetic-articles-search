#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重跑失败的文章摘要和关键词生成
针对08-21批量任务中失败的817篇文章（content为空或keywords为空）
"""

import sqlite3
import urllib.request
import urllib.parse
import urllib.error
import re
import json
import time
import ssl
import sys
from datetime import datetime

# 创建SSL上下文
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 数据库路径
DB_PATH = "/Users/yuming.chen/.openclaw/workspace/cosmetic-deploy/cosmetic_articles.db"

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_failed_articles():
    """获取所有失败的文章（content为空或keywords为空）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, title, url 
        FROM articles 
        WHERE content IS NULL OR content = '' 
           OR keywords IS NULL OR keywords = ''
        ORDER BY id
    """)
    
    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return articles

def fetch_article_content(url):
    """按链接抓取文章正文"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1 MicroMessenger/8.0.47',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://mp.weixin.qq.com/',
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as resp:
            html = resp.read().decode('utf-8')
        
        # 提取正文 - 微信文章正文在js_content div中
        content_match = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
        if not content_match:
            content_match = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>', html, re.DOTALL)
        
        if content_match:
            content_html = content_match.group(1)
            # 清理HTML标签
            content = re.sub(r'<[^>]+>', '', content_html)
            content = re.sub(r'\s+', ' ', content).strip()
            # 清理微信特有的干扰文本
            content = re.sub(r'var\s+.*?=\s*.*?;', '', content)
            content = re.sub(r'function\s*\(\)\s*\{.*?\}', '', content)
            return content[:15000]  # 限制长度
        
        return None
    except Exception as e:
        print(f"  抓取失败: {e}")
        return None

def update_article_content(article_id, content):
    """先更新文章内容"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE articles 
        SET content = ?
        WHERE id = ?
    """, (content, article_id))
    
    conn.commit()
    conn.close()

def main():
    print("=" * 60)
    print("第一步：抓取失败文章的正文内容")
    print("=" * 60)
    
    # 获取失败的文章
    failed_articles = get_failed_articles()
    total = len(failed_articles)
    
    print(f"\n发现 {total} 篇失败文章需要重跑\n")
    
    if total == 0:
        print("没有需要重跑的文章！")
        return
    
    # 统计
    success_count = 0
    fetch_fail_count = 0
    
    for i, article in enumerate(failed_articles, 1):
        article_id = article['id']
        title = article['title'][:50]
        url = article['url']
        
        print(f"[{i}/{total}] ID:{article_id} | {title}...")
        
        # 抓取正文
        print(f"  抓取正文...", end=" ")
        content = fetch_article_content(url)
        
        if not content:
            print("失败")
            fetch_fail_count += 1
            continue
        
        print(f"成功 ({len(content)}字符)")
        
        # 更新数据库中的content
        update_article_content(article_id, content)
        success_count += 1
        
        print(f"  ✓ 内容已入库")
        print()
        
        # 限速，避免请求过快
        if i % 10 == 0:
            print(f"--- 已完成 {i}/{total}，休息5秒 ---")
            time.sleep(5)
        else:
            time.sleep(1)
    
    # 最终统计
    print("=" * 60)
    print("第一步完成！正文抓取结果：")
    print(f"  成功: {success_count}")
    print(f"  失败: {fetch_fail_count}")
    print(f"  总计: {total}")
    print("=" * 60)
    print("\n下一步：运行第二步脚本生成摘要和关键词")

if __name__ == "__main__":
    main()
