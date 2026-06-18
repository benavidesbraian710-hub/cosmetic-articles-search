#!/usr/bin/env python3
"""
微信文章链接提取工具 - Mac 版
从剪贴板或文本中提取微信公众号文章链接并入库

使用方法：
1. 在微信 Mac 版中选中文章链接，复制到剪贴板
2. 运行此脚本自动提取并入库
"""

import sqlite3
import json
import re
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

# 数据库路径
DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"

def get_clipboard_content():
    """获取剪贴板内容"""
    try:
        # Mac 使用 pbpaste 获取剪贴板
        result = subprocess.run(['pbpaste'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
    except Exception as e:
        print(f"⚠️  无法获取剪贴板: {e}")
    return ""

def extract_wechat_links(text):
    """从文本中提取微信公众号文章链接"""
    # 匹配 mp.weixin.qq.com 链接
    pattern = r'https?://mp\.weixin\.qq\.com/s/[a-zA-Z0-9_-]+'
    links = re.findall(pattern, text)
    return list(set(links))  # 去重

def add_article_to_db(title, url, source, publish_date=None, summary=""):
    """添加文章到数据库"""
    conn = sqlite3.connect(DB_PATH)
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
    print(f"✅ 已添加: {title}")
    return True

def main():
    print("=" * 60)
    print("  微信文章链接提取工具 - Mac 版")
    print("=" * 60)
    print()
    
    # 获取剪贴板内容
    print("📋 正在获取剪贴板内容...")
    clipboard = get_clipboard_content()
    
    if not clipboard:
        print("❌ 剪贴板为空，请先复制文章链接")
        return
    
    # 提取链接
    links = extract_wechat_links(clipboard)
    
    if not links:
        print("⚠️  未找到微信公众号文章链接")
        print("剪贴板内容预览:")
        print(clipboard[:200] + "..." if len(clipboard) > 200 else clipboard)
        return
    
    print(f"✅ 找到 {len(links)} 个文章链接")
    print()
    
    # 询问公众号名称
    source = input("请输入这些文章所属的公众号名称: ").strip()
    if not source:
        print("❌ 公众号名称不能为空")
        return
    
    # 处理每个链接
    added = 0
    for i, url in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] 处理链接: {url}")
        
        # 尝试从链接或剪贴板提取标题
        title = input("请输入文章标题 (直接回车使用默认标题): ").strip()
        if not title:
            title = f"文章_{datetime.now().strftime('%Y%m%d')}_{i}"
        
        publish_date = input("请输入发布日期 (YYYY-MM-DD, 默认今天): ").strip()
        if not publish_date:
            publish_date = datetime.now().strftime("%Y-%m-%d")
        
        if add_article_to_db(title, url, source, publish_date):
            added += 1
    
    print(f"\n✅ 完成！成功添加 {added}/{len(links)} 篇文章")

if __name__ == "__main__":
    main()
