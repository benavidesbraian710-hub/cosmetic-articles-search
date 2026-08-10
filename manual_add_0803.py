import sqlite3
import urllib.request
import re
import json
from datetime import datetime

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.47',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

def fetch_article(url):
    """抓取微信文章标题、发布日期、内容"""
    try:
        req = urllib.request.Request(url, headers=get_headers())
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode('utf-8')
        
        # 提取标题
        title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        title = title_match.group(1) if title_match else ''
        
        # 提取发布日期 - 多种模式
        publish_date = ''
        
        # 模式1: var createTime = '2026-08-03 08:00';
        m = re.search(r"var createTime\s*=\s*'([^']+)'", html)
        if m:
            publish_date = m.group(1)
        
        # 模式2: publish_time = '2026-08-03'
        if not publish_date:
            m = re.search(r"publish_time\s*=\s*'([^']+)'", html)
            if m:
                publish_date = m.group(1)
        
        # 模式3: 从页面文本提取
        if not publish_date:
            m = re.search(r'(\d{4}-\d{2}-\d{2})', html)
            if m:
                publish_date = m.group(1)
        
        # 统一截断为纯日期 YYYY-MM-DD
        if publish_date and len(publish_date) > 10:
            publish_date = publish_date[:10]
        
        # 提取内容
        content = ''
        content_match = re.search(r'<div class="rich_media_content[^"]*"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
        if content_match:
            content = content_match.group(1)
            # 清理HTML标签获取纯文本
            content_text = re.sub(r'<[^>]+>', '', content)
            content_text = re.sub(r'\s+', ' ', content_text).strip()
        else:
            content_text = ''
        
        # 提取图片
        images = re.findall(r'data-src="([^"]+)"', html)
        images = [img for img in images if 'mmbiz.qpic.cn' in img][:10]  # 限制10张
        
        return {
            'title': title,
            'publish_date': publish_date,
            'content': content_text[:5000] if content_text else '',  # 限制长度
            'content_html': content[:10000] if content else '',
            'images': images,
            'image_count': len(images),
        }
    except Exception as e:
        print(f"  ❌ 抓取失败: {e}")
        return None

def main():
    db_path = 'cosmetic_articles.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 读取待补录列表
    with open('manual_add_0803.txt', 'r') as f:
        lines = [l.strip() for l in f if l.strip()]
    
    added = 0
    skipped = 0
    failed = 0
    
    for line in lines:
        parts = line.split('|', 1)
        if len(parts) != 2:
            continue
        account, url = parts
        
        # 检查是否已存在
        cursor.execute('SELECT id FROM articles WHERE url = ?', (url,))
        if cursor.fetchone():
            print(f"⏭️  跳过(已存在): {url}")
            skipped += 1
            continue
        
        print(f"📥 抓取: {account} - {url}")
        article = fetch_article(url)
        
        if not article or not article['title']:
            print(f"  ❌ 抓取失败或标题为空")
            failed += 1
            continue
        
        # 插入数据库
        cursor.execute('''
            INSERT INTO articles (wechat_name, title, url, publish_date, content, content_html, images_json, image_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            account,
            article['title'],
            url,
            article['publish_date'],
            article['content'],
            article['content_html'],
            json.dumps(article['images']),
            article['image_count'],
            datetime.now().isoformat()
        ))
        
        print(f"  ✅ 新增: {article['title'][:50]}... | {article['publish_date']}")
        added += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n📊 补录完成: 新增 {added} 篇, 跳过 {skipped} 篇, 失败 {failed} 篇")

if __name__ == '__main__':
    main()
