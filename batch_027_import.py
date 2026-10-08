#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第二十七批入库（2026-09-28~2026-10-08 采集，19个文件批量）
复用 batch_026_import.py 的核心逻辑，改造为多文件版本。
"""

import sqlite3
import urllib.request
import urllib.error
import re
import json
import time
import ssl
import sys
import os
from datetime import datetime
from collections import Counter

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

DB_PATH = "/Users/yuming.chen/.openclaw/workspace/cosmetic-deploy/cosmetic_articles.db"
BATCH_DIR = "/Users/yuming.chen/.openclaw/workspace/cosmetic-deploy/batch_027"

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

FALLBACK_DATE = '2026-10-08'


def load_excel_files(batch_dir):
    """批量加载batch_dir下的xlsx，返回 [(filename, [(name,url),...]), ...]"""
    import openpyxl
    all_batches = []
    files = sorted([f for f in os.listdir(batch_dir) if f.endswith('.xlsx')])
    for fname in files:
        fpath = os.path.join(batch_dir, fname)
        wb = openpyxl.load_workbook(fpath, read_only=True)
        ws = wb.active
        records = []
        for row in ws.iter_rows(values_only=True):
            if row and len(row) >= 2 and row[0] and row[1] and str(row[1]).startswith('http'):
                records.append((str(row[0]).strip(), str(row[1]).strip()))
        all_batches.append((fname, records))
    return all_batches


def dedup_against_db(records):
    """跨文件去重 + 跨DB去重"""
    # 文件内去重
    seen = set()
    unique = []
    for r in records:
        if r[1] not in seen:
            seen.add(r[1])
            unique.append(r)

    # 跨DB去重
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
    print("=" * 70)
    print(f"第二十七批入库（19个文件 9-28~10-08）")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 1. 读所有xlsx
    print("\n[1] 读取19个xlsx...")
    all_batches = load_excel_files(BATCH_DIR)
    total_raw = sum(len(recs) for _, recs in all_batches)
    print(f"    总原始记录: {total_raw} 条（{len(all_batches)}个文件）")

    # 2. 全局合并去重
    print("\n[2] 全局去重...")
    all_records = []
    for fname, recs in all_batches:
        all_records.extend(recs)
    unique, new_records = dedup_against_db(all_records)
    print(f"    文件内去重: {total_raw} → {len(unique)}")
    print(f"    跨DB去重: {len(unique)} → {len(new_records)} 净新增")

    # 按公众号分布
    by_acc = Counter(r[0] for r in new_records)
    print(f"\n    净新增按公众号分布（共{len(by_acc)}个）:")
    for n, c in sorted(by_acc.items(), key=lambda x: -x[1]):
        mark = "✓" if n in ALLOWED_ACCOUNTS else "✗非白名单"
        print(f"      [{mark}] {n}: {c}")

    # 白名单拦截
    non_allowed = [r for r in new_records if r[0] not in ALLOWED_ACCOUNTS]
    if non_allowed:
        print(f"\n    ⚠️ {len(non_allowed)} 条非白名单将拦截")
    allowed_records = [r for r in new_records if r[0] in ALLOWED_ACCOUNTS]

    if not allowed_records:
        print("\n无新内容，退出")
        return

    # 3. 抓取入库
    print(f"\n[3] 抓取入库（{len(allowed_records)}条）...")
    success = []
    failed = []
    start_time = time.time()

    for i, (wechat_name, url) in enumerate(allowed_records, 1):
        elapsed = time.time() - start_time
        eta = (elapsed / i) * (len(allowed_records) - i) if i > 0 else 0

        sys.stdout.write(f"\r    [{i}/{len(allowed_records)}] {wechat_name[:14]:<14} {url[-20:]}  已用{elapsed:.0f}s  剩{eta:.0f}s")
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

    # 4. 报告
    total_time = time.time() - start_time
    print(f"\n\n{'='*70}")
    print(f"[4] 完成！用时 {total_time/60:.1f} 分钟")
    print(f"    ✅ 成功: {len(success)}")
    print(f"    ❌ 失败: {len(failed)}")
    print(f"    🚫 非白名单拦截: {len(non_allowed)}")

    if success:
        print(f"\n    成功入库明细（前10条）:")
        for sid, acc, t, dt in success[:10]:
            print(f"      #{sid:<5} {acc[:14]:<14} {dt} | {t}")

    if failed:
        print(f"\n    失败明细（前10条）:")
        for acc, url, err in failed[:10]:
            print(f"      {acc[:14]:<14} {url[-30:]} | {err[:40]}")

    # 5. 保存报告
    report_path = os.path.join(BATCH_DIR, f"import_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    report = {
        'batch': '27',
        'start_time': datetime.now().isoformat(),
        'total_time_sec': total_time,
        'total_raw': total_raw,
        'unique_after_dedup': len(unique),
        'new_records': len(new_records),
        'success': len(success),
        'failed': len(failed),
        'non_allowed_blocked': len(non_allowed),
        'success_ids': [i[0] for i in success],
        'failed_list': [(i[0], i[1], i[2]) for i in failed],
    }
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n    📋 详细报告: {report_path}")


if __name__ == '__main__':
    main()