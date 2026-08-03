import sqlite3
import urllib.request
import re
import json

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
        
        # 提取标题 - 多种模式
        title = ''
        
        # 模式1: og:title
        m = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        if m:
            title = m.group(1)
        
        # 模式2: rich_media_title
        if not title:
            m = re.search(r'<h1 class="rich_media_title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        
        # 模式3: msg_title
        if not title:
            m = re.search(r"var msg_title\s*=\s*'([^']+)'", html)
            if m:
                title = m.group(1)
        
        # 提取发布日期 - 多种模式
        publish_date = ''
        
        # 模式1: var createTime
        m = re.search(r"var createTime\s*=\s*'([^']+)'", html)
        if m:
            publish_date = m.group(1)
        
        # 模式2: publish_time
        if not publish_date:
            m = re.search(r"publish_time\s*=\s*'([^']+)'", html)
            if m:
                publish_date = m.group(1)
        
        # 模式3: 从页面文本提取
        if not publish_date:
            m = re.search(r'(\d{4}-\d{2}-\d{2})', html)
            if m:
                publish_date = m.group(1)
        
        # 提取内容
        content = ''
        content_match = re.search(r'<div class="rich_media_content[^"]*"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
        if content_match:
            content = content_match.group(1)
            content_text = re.sub(r'<[^>]+>', '', content)
            content_text = re.sub(r'\s+', ' ', content_text).strip()
        else:
            content_text = ''
        
        # 提取图片
        images = re.findall(r'data-src="([^"]+)"', html)
        images = [img for img in images if 'mmbiz.qpic.cn' in img][:10]
        
        return {
            'title': title,
            'publish_date': publish_date,
            'content': content_text[:5000] if content_text else '',
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
    
    # 问题文章列表
    problem_urls = [
        ('财经早餐', 'https://mp.weixin.qq.com/s/NG2o0MEnwKVTVErzcAmUHQ', 1319),
        ('铱星云商', 'https://mp.weixin.qq.com/s/7Xlhh5g8SiA9kf21B9SCow', 1194),
        ('财经早餐', 'https://mp.weixin.qq.com/s/yWpIYYzBkfjaRjJ8Z0-ZsQ', 1193),
        ('财经早餐', 'https://mp.weixin.qq.com/s/eVqDAmuUUnNt_3CRgdxCTA', 1192),
    ]
    
    fixed = 0
    failed = 0
    
    for account, url, article_id in problem_urls:
        print(f"📥 修复: {account} - {url}")
        article = fetch_article(url)
        
        if not article:
            print(f"  ❌ 抓取失败")
            failed += 1
            continue
        
        if not article['title']:
            print(f"  ⚠️ 标题仍为空")
            failed += 1
            continue
        
        # 更新数据库
        cursor.execute('''
            UPDATE articles 
            SET title = ?, publish_date = ?, content = ?, content_html = ?, images_json = ?, image_count = ?
            WHERE id = ?
        ''', (
            article['title'],
            article['publish_date'],
            article['content'],
            article['content_html'],
            json.dumps(article['images']),
            article['image_count'],
            article_id
        ))
        
        print(f"  ✅ 修复: {article['title'][:50]}... | {article['publish_date']}")
        fixed += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n📊 修复完成: 成功 {fixed} 篇, 失败 {failed} 篇")

if __name__ == '__main__':
    main()
