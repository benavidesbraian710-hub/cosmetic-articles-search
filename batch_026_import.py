#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第二十六批入库（2026-09-28 采集，1个文件）
"""

import sqlite3
import urllib.request
import urllib.error
import re
import json
import time
import ssl
import sys
from datetime import datetime

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

DB_PATH = "/Users/yuming.chen/.openclaw/workspace/cosmetic-deploy/cosmetic_articles.db"

EXCEL_FILE = '/Users/yuming.chen/.openclaw/media/inbound/2026_9_28_8010_1---7473ef99-9782-4a32-acb7-79276a63af94.xlsx'

ALLOWED_ACCOUNTS = {
    'KEV美妆', 'Vogue Business', 'WWD 国际时尚特讯', '上海日化协会',
    '个护前沿', '中国化妆品', '亿邦动力', '化妆品观察 品观',
    '化妆品财经在线', '原料合规观察', '妆合规', '妆研24小时',
    '美业颜究院', '肤见未来实验室', '财经早餐', '铱星云商',
    '非科学美妆传播', 'Fbeauty未来迹',
}

DATE_PATTERNS = [
    r'var\s+publish_time\s*=\s*["\']([^"\']+)["\']',
    r'var\s+ct\s*=\s*["\']([^"\']+)["\']',
    r'var\s+create_time\s*=\s*["\']([^"\']+)["\']',
]

FALLBACK_DATE = '2026-09-28'


def load_excel_urls():
    import openpyxl
    records = []
    wb = openpyxl.load_workbook(EXCEL_FILE)
    ws = wb.active
    for row in ws.iter_rows(values_only=True):
        if row[0] and row[1] and str(row[1]).startswith('http'):
            records.append((str(row[0]).strip(), str(row[1]).strip()))
    return records


def dedup(records):
    seen = set()
    unique = []
    for r in records:
        if r[1] not in seen:
            seen.add(r[1])
            unique.append(r)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM articles')
    db_urls = {row[0] for row in cursor.fetchall()}
    conn.close()

    new_records = [r for r in unique if r[1] not in db_urls]
    return unique, new_records


def fetch_detail(url, retries=2):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1 MicroMessenger/8.0.47',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://mp.weixin.qq.com/',
    }

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ssl_context, timeout=20) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                break
        except Exception as e:
            if attempt == retries - 1:
                return None, None, str(e)
            time.sleep(1)

    title_match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html)
    if not title_match:
        title_match = re.search(r'<h1[^>]*class=["\']rich_media_title["\'][^>]*>([^<]+)</h1>', html)
    if not title_match:
        title_match = re.search(r'<title>([^<]+)</title>', html)
    title = title_match.group(1).strip() if title_match else ''

    publish_date = None
    for pat in DATE_PATTERNS:
        m = re.search(pat, html)
        if m:
            ts_str = m.group(1)
            try:
                ts = int(ts_str)
                if ts > 1e12:
                    ts = ts / 1000
                publish_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            except (ValueError, TypeError, OSError):
                pass
            if publish_date:
                break

    if not publish_date:
        m = re.search(r'<meta[^>]*property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']', html)
        if m:
            try:
                publish_date = m.group(1)[:10]
            except Exception:
                pass

    return title, publish_date, None


def insert_article(wechat_name, url, title, publish_date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO articles (title, wechat_name, source, url, publish_date, content, summary, keywords, images_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, wechat_name, '', url, publish_date, '', '', '', ''))
        conn.commit()
        new_id = cursor.lastrowid
        return new_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def main():
    print("=" * 60)
    print("第二十六批入库（2026-09-28 采集，1个文件）")
    print("=" * 60)

    records = load_excel_urls()
    print(f"[1] Excel 读入: {len(records)} 条")

    unique, new_records = dedup(records)
    print(f"[2] 文件内去重: {len(records)} → {len(unique)} | 跨库去重: → {len(new_records)} 净新增")
    print()

    if not new_records:
        print("无新内容，退出")
        return

    from collections import Counter
    by_acc = Counter(r[0] for r in new_records)
    print("    净新增按公众号分布:")
    for name, cnt in by_acc.most_common():
        print(f"      {name}: {cnt}")
    print()

    non_allowed = [r for r in new_records if r[0] not in ALLOWED_ACCOUNTS]
    if non_allowed:
        print(f"⚠️ 发现 {len(non_allowed)} 条非白名单公众号，将拦截:")
        for r in non_allowed:
            print(f"    {r[0]}: {r[1]}")

    success = []
    failed = []
    skipped_non_allowed = []

    for i, (wechat_name, url) in enumerate(new_records, 1):
        if wechat_name not in ALLOWED_ACCOUNTS:
            skipped_non_allowed.append((wechat_name, url))
            continue

        sys.stdout.write(f"\r    [{i}/{len(new_records)}] {wechat_name[:14]:<14} {url[-20:]}")
        sys.stdout.flush()

        title, pub_date, err = fetch_detail(url)
        if not title:
            failed.append((wechat_name, url, err or 'no title'))
            continue

        if not pub_date:
            pub_date = FALLBACK_DATE

        new_id = insert_article(wechat_name, url, title, pub_date)
        if new_id:
            success.append((new_id, wechat_name, title[:30], pub_date))
        else:
            failed.append((wechat_name, url, 'insert failed'))

    print()
    print()
    print(f"[3] 抓取入库完成: {len(success)} 成功 / {len(failed)} 失败 / {len(skipped_non_allowed)} 非白名单拦截")

    if success:
        print()
        print("    入库明细:")
        for sid, acc, title, dt in success:
            print(f"      #{sid:<5} {acc[:14]:<14} {dt} | {title}")

    if failed:
        print()
        print("    失败明细:")
        for acc, url, err in failed:
            print(f"      {acc[:14]:<14} {url[-30:]} | {err}")


if __name__ == '__main__':
    main()