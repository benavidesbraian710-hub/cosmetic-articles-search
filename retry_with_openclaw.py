#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重跑失败的文章摘要和关键词生成
使用OpenClaw sessions_spawn调用Kimi K3
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
import subprocess
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
    """获取所有需要生成摘要和关键词的文章"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, title, url 
        FROM articles 
        WHERE keywords IS NULL OR keywords = ''
        ORDER BY id
    """)
    
    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return articles

def fetch_article_content(url):
    """按链接实时抓取文章正文"""
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
        
        # 提取正文
        content_match = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
        if not content_match:
            content_match = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>', html, re.DOTALL)
        
        if content_match:
            content_html = content_match.group(1)
            content = re.sub(r'<[^>]+>', '', content_html)
            content = re.sub(r'\s+', ' ', content).strip()
            content = re.sub(r'var\s+.*?=\s*.*?;', '', content)
            content = re.sub(r'function\s*\(\)\s*\{.*?\}', '', content)
            return content[:8000]
        
        return None
    except Exception as e:
        print(f"  抓取失败: {e}")
        return None

def generate_with_kimi(title, content):
    """使用Kimi K3生成摘要和关键词 - 通过OpenClaw CLI"""
    
    prompt = f"""请为以下化妆品行业文章生成摘要和关键词。

标题：{title}

正文内容：
{content}

请按以下格式输出：
【摘要】200-400字的文章摘要，概括核心内容和关键信息
【关键词】10-15个关键词，用逗号分隔，包括：核心成分/技术、品牌/公司、行业趋势、政策法规、产品类型等维度

注意：
1. 摘要要客观准确，突出行业价值
2. 关键词要专业规范，便于检索
3. 如果内容涉及广告或推广，也要客观描述其推广的产品/技术"""

    try:
        # 使用openclaw CLI调用
        cmd = [
            "openclaw", "chat",
            "--model", "kimi/kimi-k3",
            "--message", prompt,
            "--format", "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            response = json.loads(result.stdout)
            text = response.get('content', '')
            
            # 解析摘要
            summary_match = re.search(r'【摘要】\s*(.+?)(?=【关键词】|$)', text, re.DOTALL)
            summary = summary_match.group(1).strip() if summary_match else ""
            
            # 解析关键词
            keywords_match = re.search(r'【关键词】\s*(.+?)$', text, re.DOTALL)
            keywords = keywords_match.group(1).strip() if keywords_match else ""
            
            # 清理关键词格式
            keywords = re.sub(r'[，、]', ',', keywords)
            keywords = re.sub(r'\s+', '', keywords)
            
            return summary, keywords
        else:
            print(f"  CLI调用失败: {result.stderr}")
            return None, None
            
    except Exception as e:
        print(f"  LLM调用失败: {e}")
        return None, None

def update_article_summary_keywords(article_id, summary, keywords):
    """只更新摘要和关键词"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE articles 
        SET summary = ?, keywords = ?
        WHERE id = ?
    """, (summary, keywords, article_id))
    
    conn.commit()
    conn.close()

def main():
    print("=" * 60)
    print("重跑失败的文章摘要和关键词生成")
    print("流程：按链接实时抓取全文 → Kimi K3生成摘要/关键词 → 只存摘要和关键词")
    print("=" * 60)
    
    # 获取失败的文章
    failed_articles = get_failed_articles()
    total = len(failed_articles)
    
    print(f"\n发现 {total} 篇文章需要生成摘要和关键词\n")
    
    if total == 0:
        print("没有需要处理的文章！")
        return
    
    # 统计
    success_count = 0
    fetch_fail_count = 0
    llm_fail_count = 0
    
    for i, article in enumerate(failed_articles, 1):
        article_id = article['id']
        title = article['title'][:50]
        url = article['url']
        
        print(f"[{i}/{total}] ID:{article_id} | {title}...")
        
        # 1. 实时抓取正文
        print(f"  抓取正文...", end=" ")
        content = fetch_article_content(url)
        
        if not content:
            print("失败")
            fetch_fail_count += 1
            continue
        
        print(f"成功 ({len(content)}字符)")
        
        # 2. 生成摘要和关键词
        print(f"  生成摘要/关键词...", end=" ")
        summary, keywords = generate_with_kimi(article['title'], content)
        
        if not summary or not keywords:
            print("失败")
            llm_fail_count += 1
            continue
        
        print("成功")
        
        # 3. 只更新摘要和关键词
        update_article_summary_keywords(article_id, summary, keywords)
        success_count += 1
        
        print(f"  ✓ 已入库")
        print()
        
        # 限速
        if i % 5 == 0:
            print(f"--- 已完成 {i}/{total}，休息3秒 ---")
            time.sleep(3)
        else:
            time.sleep(1)
    
    # 最终统计
    print("=" * 60)
    print("任务完成！")
    print(f"  成功: {success_count}")
    print(f"  抓取失败: {fetch_fail_count}")
    print(f"  LLM生成失败: {llm_fail_count}")
    print(f"  总计: {total}")
    print("=" * 60)

if __name__ == "__main__":
    main()
