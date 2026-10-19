#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三十二批入库（2026-10-19 采集，1 个文件 89 条）
复用 batch_031_import.py 核心逻辑：
- DB_PATH 走环境变量 COSMETIC_DB_PATH（10-19 路径混淆治理）
- canonical_url 兜底（10-17 长URL重复bugfix）
- publish_date 强制 YYYY-MM-DD（10-08 时分格式治理）
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
import zipfile
from datetime import datetime
from collections import Counter

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 10-19 治理：DB_PATH 走 COSMETIC_DB_PATH 环境变量，缺省 deploy 仓
DB_PATH = os.environ.get('COSMETIC_DB_PATH', '/Users/yuming.chen/.openclaw/workspace/cosmetic-deploy/cosmetic_articles.db')
BATCH_DIR = '/Users/yuming.chen/.openclaw/workspace/cosmetic-deploy/batch_032'

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

# FALLBACK 日期：本批 10-19 采集，用今天
FALLBACK_DATE = '2026-10-19'


def read_xlsx_zipfile(xlsx_path):
    """用 zipfile 读 xlsx（不依赖 openpyxl）
    10-19 治理: 系统 Python 3.15 没装 openpyxl, PEP 668 + macOS pip truststore 都装不上
    """
    z = zipfile.ZipFile(xlsx_path)
    # 读 sharedStrings
    ss = []
    try:
        ss_xml = z.read('xl/sharedStrings.xml').decode('utf-8')
        for m in re.finditer(r'<si[^>]*>(.*?)</si>', ss_xml, re.S):
            chunk = m.group(1)
            parts = re.findall(r'<t[^>]*>(.*?)</t>', chunk, re.S)
            text = ''.join(parts)
            text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&apos;', "'")
            ss.append(text)
    except KeyError:
        pass

    # 读 sheet1
    sheet_xml = z.read('xl/worksheets/sheet1.xml').decode('utf-8')

    def col_letter_to_idx(s):
        n = 0
        for c in s:
            n = n * 26 + (ord(c.upper()) - ord('A') + 1)
        return n - 1

    rows = []
    for row_m in re.finditer(r'<row[^>]*>(.*?)</row>', sheet_xml, re.S):
        cells = {}
        for c_m in re.finditer(r'<c\s+r="([A-Z]+)(\d+)"(?:\s+s="[^"]*")?(?:\s+t="([^"]*)")?[^>]*?>(.*?)</c>', row_m.group(1), re.S):
            col_letter = c_m.group(1)
            col_idx = col_letter_to_idx(col_letter)
            ctype = c_m.group(3) or 'n'
            body = c_m.group(4)
            v_m = re.search(r'<v>(.*?)</v>', body, re.S)
            if not v_m:
                is_m = re.search(r'<is>.*?<t[^>]*>(.*?)</t>.*?</is>', body, re.S)
                val = is_m.group(1) if is_m else None
            else:
                raw = v_m.group(1)
                if ctype == 's':
                    val = ss[int(raw)]
                else:
                    val = raw
            if val:
                val = val.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&apos;', "'")
            cells[col_idx] = val
        rows.append(cells)

    # 过滤有效行: 第一列公众号名 + 第二列 URL
    records = []
    for r in rows[1:]:  # 跳过表头
        name = r.get(0)
        url = r.get(1)
        if name and url and url.startswith('http'):
            records.append((str(name).strip(), str(url).strip()))
    return records


def load_excel_files(batch_dir):
    """批量加载 batch_dir 下的 xlsx"""
    all_batches = []
    files = sorted([f for f in os.listdir(batch_dir) if f.endswith('.xlsx')])
    for fname in files:
        fpath = os.path.join(batch_dir, fname)
        records = read_xlsx_zipfile(fpath)
        all_batches.append((fname, records))
    return all_batches


def normalize_url(url):
    """微信长URL(mp.weixin.qq.com/s?search_click_id=...&sn=HASH) → 短URL(mp.weixin.qq.com/s/HASH)
    避免同一文章因两种URL格式导致重复入库（10-17 bugfix：4组长URL重复）
    """
    if 'search_click_id=' in url or '&sn=' in url:
        m = re.search(r'[?&]sn=([a-f0-9]+)', url)
        if m:
            return f'https://mp.weixin.qq.com/s/{m.group(1)}'
    return url


def dedup_against_db(records):
    """跨文件去重 + 跨DB去重
    支持微信长URL(mp.weixin.qq.com/s?search_click_id=...)与短URL视为同文章（10-17 dedup bugfix）
    """
    seen = set()
    unique = []
    for r in records:
        canonical = normalize_url(r[1])
        if canonical not in seen and r[1] not in seen:
            seen.add(canonical)
            seen.add(r[1])
            unique.append(r)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM articles')
    db_urls = {row[0] for row in cursor.fetchall()}
    conn.close()

    # 归一化所有db_urls以便匹配（短+长都视为相同）
    db_canonical_set = {normalize_url(u) for u in db_urls} | db_urls

    new_records = [r for r in unique if r[1] not in db_canonical_set and normalize_url(r[1]) not in db_canonical_set]
    return unique, new_records


def fetch_detail(url, retries=2):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone os 16_6 like Mac os X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1 microMessenger/8.0.47',
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
    """入库时同时写入 canonical_url，依赖UNIQUE INDEX兜底（10-17 彻底修复）
    任何 (wechat_name, title, publish_date) 重复都会被DB拒绝
    """
    canonical = normalize_url(url)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO articles 
              (title, wechat_name, source, url, canonical_url, publish_date, content, summary, keywords, images_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, wechat_name, '', url, canonical, publish_date, '', '', '', ''))
        conn.commit()
        if cursor.rowcount > 0:
            return cursor.lastrowid
        return None  # UNIQUE INDEX拦截，duplicate
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def main():
    print("=" * 70)
    print(f"第三十二批入库（1个文件 2026-10-19 采集）")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"DB_PATH: {DB_PATH}")
    print("=" * 70)

    print("\n[1] 读取 xlsx...")
    all_batches = load_excel_files(BATCH_DIR)
    total_raw = sum(len(recs) for _, recs in all_batches)
    print(f"    总原始记录: {total_raw} 条（{len(all_batches)}个文件）")

    print("\n[2] 全局去重...")
    all_records = []
    for fname, recs in all_batches:
        all_records.extend(recs)
    unique, new_records = dedup_against_db(all_records)
    print(f"    文件内去重: {total_raw} → {len(unique)}")
    print(f"    跨DB去重: {len(unique)} → {len(new_records)} 净新增")

    by_acc = Counter(r[0] for r in new_records)
    print(f"\n    净新增按公众号分布（共{len(by_acc)}个）:")
    for n, c in sorted(by_acc.items(), key=lambda x: -x[1]):
        mark = "✓" if n in ALLOWED_ACCOUNTS else "✗非白名单"
        print(f"      [{mark}] {n}: {c}")

    non_allowed = [r for r in new_records if r[0] not in ALLOWED_ACCOUNTS]
    if non_allowed:
        print(f"\n    ⚠️ {len(non_allowed)} 条非白名单将拦截")
    allowed_records = [r for r in new_records if r[0] in ALLOWED_ACCOUNTS]

    if not allowed_records:
        print("\n无新内容，退出")
        return

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
            failed.append((wechat_name, url, 'insert failed (duplicate or no insert)'))

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

    report_path = os.path.join(BATCH_DIR, f"import_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    report = {
        'batch': '32',
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
