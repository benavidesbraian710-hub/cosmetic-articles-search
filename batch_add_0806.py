#!/usr/bin/env python3
"""
微信公众号文章批量入库脚本 v2.0
修复：wechat_name空值校验 + 公众号白名单 + 自动从页面抓取公众号名兜底
"""

import sqlite3
import urllib.request
import re
import json
import time
import sys
from datetime import datetime

# ===== 公众号白名单 =====
WHITELISTED_SOURCES = {
    '亿邦动力', '个护前沿', '财经早餐', '化妆品观察 品观', '中国化妆品',
    'WWD 国际时尚特讯', 'Fbeauty未来迹', '妆研24小时', '肤见未来实验室',
    '化妆品财经在线', '非科学美妆传播', '铱星云商', 'Vogue Business',
    '妆合规', '原料合规观察', 'KEV美妆', '上海日化协会', '美业颜究院'
}

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.47',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

def fetch_wechat_name_from_page(url):
    """从微信文章页面抓取真实的公众号名称（兜底策略）"""
    try:
        req = urllib.request.Request(url, headers=get_headers())
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode('utf-8')

        # 尝试多种模式提取公众号名称
        patterns = [
            # 模式1: var nickname = htmlDecode("xxx")
            r'nickname\s*=\s*htmlDecode\("([^"]+)"\)',
            # 模式2: var nickname = "xxx"
            r'var\s+nickname\s*=\s*"([^"]+)"',
            # 模式3: "nickname":"xxx"
            r'"nickname"\s*:\s*"([^"]+)"',
            # 模式4: data-nickname="xxx"
            r'data-nickname\s*=\s*"([^"]+)"',
        ]

        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                name = m.group(1).replace('\\"', '"').strip()
                if name and len(name) > 1:
                    return name

        # 备选：从页面元素提取
        m = re.search(r'id="activity-name"[^>]*>\s*([^<]+)\s*</', html)
        if m:
            return m.group(1).strip()

        return ''
    except Exception as e:
        print(f"    ⚠️ 抓取公众号名失败: {e}")
        return ''


def fetch_article(url):
    """抓取微信文章标题、发布日期、内容"""
    try:
        req = urllib.request.Request(url, headers=get_headers())
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode('utf-8')

        # 提取标题 - 优先 og:title，备选 rich_media_title
        title = ''
        title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        if title_match:
            title = title_match.group(1)
        if not title:
            title_match = re.search(r'var msg_title\s*=\s*[\'"]([^\'"]*)[\'"]', html)
            if title_match:
                title = title_match.group(1)
        if not title:
            title_match = re.search(r'<h1[^>]*class="rich_media_title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL)
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

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

        # 模式3: var ct = "1691234567" (时间戳)
        if not publish_date:
            m = re.search(r'var ct\s*=\s*"(\d{10})"', html)
            if m:
                ts = int(m.group(1))
                publish_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')

        # 模式4: 从页面文本提取日期
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
        print(f"    ❌ 抓取异常: {e}")
        return None


def main():
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = '/tmp/batch_input.txt'

    db_path = 'cosmetic_articles.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 读取待补录列表
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        print(f"❌ 文件不存在: {input_file}")
        print(f"   用法: python3 batch_add_0806.py <输入文件>")
        sys.exit(1)

    print(f"📂 读取到 {len(lines)} 条记录")
    print(f"📋 白名单公众号: {len(WHITELISTED_SOURCES)} 个")
    print(f"{'='*60}")

    added = 0
    skipped = 0
    failed = 0
    skipped_by_whitelist = 0
    failed_list = []

    for i, line in enumerate(lines, 1):
        parts = line.split('\t', 1)
        if len(parts) != 2:
            print(f"⚠️  [{i}/{len(lines)}] 格式错误，跳过: {line[:80]}")
            failed += 1
            failed_list.append(('格式错误', line[:80]))
            continue

        account, url = parts
        account = account.strip() if account else ''
        url = url.strip()

        # 检查是否已存在
        cursor.execute('SELECT id FROM articles WHERE url = ?', (url,))
        if cursor.fetchone():
            print(f"⏭️  [{i}/{len(lines)}] 跳过(已存在)")
            skipped += 1
            continue

        print(f"📥 [{i}/{len(lines)}] 抓取: {account or '(空)'} - {url[:50]}...")

        # ===== 关键修复：wechat_name空值兜底策略 =====
        wechat_name = account

        # 如果Excel中wechat_name为空或不在白名单，尝试从页面抓取
        if not wechat_name or wechat_name not in WHITELISTED_SOURCES:
            print(f"    🔍 Excel中公众号名「{wechat_name or '(空)'}」无效，尝试从页面抓取...")
            page_wechat_name = fetch_wechat_name_from_page(url)
            if page_wechat_name:
                print(f"    ✅ 页面抓取到公众号: {page_wechat_name}")
                wechat_name = page_wechat_name
            else:
                print(f"    ⚠️ 页面也抓取失败")

        # ===== 关键修复：白名单校验 =====
        if wechat_name not in WHITELISTED_SOURCES:
            print(f"    🚫 公众号「{wechat_name or '(空)'}」不在白名单，跳过")
            print(f"       白名单: {', '.join(sorted(WHITELISTED_SOURCES))}")
            skipped_by_whitelist += 1
            skipped += 1
            continue

        # 抓取文章内容
        article = fetch_article(url)

        if not article or not article['title']:
            print(f"    ❌ 抓取失败或标题为空")
            failed += 1
            failed_list.append((wechat_name, url, '抓取失败'))
            continue

        # 插入数据库
        cursor.execute('''
            INSERT INTO articles (wechat_name, title, url, publish_date, content, summary, keywords, images_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            wechat_name,
            article['title'],
            url,
            article['publish_date'],
            article['content'],
            article['content'][:500] if article['content'] else '',  # summary用content前500字符
            '',  # keywords留空
            json.dumps(article['images']),
            datetime.now().isoformat()
        ))

        print(f"    ✅ 新增: {article['title'][:50]} | {article['publish_date']}")
        added += 1

        # 每篇间隔1秒，避免触发反爬
        if i < len(lines):
            time.sleep(1)

    conn.commit()

    # 统计
    cursor.execute('SELECT COUNT(*) FROM articles')
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(DISTINCT wechat_name) FROM articles')
    source_count = cursor.fetchone()[0]

    conn.close()

    print(f"\n{'='*60}")
    print(f"📊 入库完成:")
    print(f"   ✅ 新增: {added} 篇")
    print(f"   ⏭️  跳过(已存在): {skipped - skipped_by_whitelist} 篇")
    print(f"   🚫 跳过(非白名单): {skipped_by_whitelist} 篇")
    print(f"   ❌ 失败: {failed} 篇")
    print(f"📊 数据库现有: {total} 篇文章, {source_count} 个公众号")

    if failed_list:
        print(f"\n❌ 失败清单 ({len(failed_list)} 条):")
        for item in failed_list[:20]:  # 最多显示20条
            if len(item) == 3:
                print(f"   {item[0]}: {item[1]}")
            else:
                print(f"   {item}")
        if len(failed_list) > 20:
            print(f"   ... 还有 {len(failed_list) - 20} 条")

    # 关键修复确认
    print(f"\n🔒 数据质量保护机制:")
    print(f"   • wechat_name空值时自动从页面抓取兜底")
    print(f"   • 非白名单公众号拒绝入库")
    print(f"   • 已存在URL跳过，避免重复")


if __name__ == '__main__':
    main()
