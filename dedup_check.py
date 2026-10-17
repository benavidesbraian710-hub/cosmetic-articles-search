#!/usr/bin/env python3
"""主动审计脚本：检查并报告任何 (wechat_name, title, publish_date) 重复
每次批次入库后/数据导出前/手动运行均可。
依赖: DB层 UNIQUE INDEX idx_unique_article 已建立
"""
import sqlite3
import sys
import re
from collections import defaultdict

DB_PATH = "/Users/yuming.chen/.openclaw/workspace/cosmetic-deploy/cosmetic_articles.db"


def normalize_url(url):
    if not url:
        return url
    if 'search_click_id=' in url or '&sn=' in url:
        m = re.search(r'[?&]sn=([a-f0-9]+)', url)
        if m:
            return f'https://mp.weixin.qq.com/s/{m.group(1)}'
    return url


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("="*70)
    print("重复文章审计报告")
    print("="*70)

    # 1. 跨URL格式的重复
    dupes_by_article = cur.execute("""
        SELECT wechat_name, title, publish_date, COUNT(*) as cnt,
               GROUP_CONCAT(id, '|') as ids,
               GROUP_CONCAT(CASE WHEN url LIKE '%search_click_id=%' THEN 'LONG' ELSE 'SHORT' END, '|') as types,
               GROUP_CONCAT(canonical_url, '||') as canonicals
        FROM articles 
        GROUP BY wechat_name, title, publish_date 
        HAVING cnt > 1
        ORDER BY cnt DESC
    """).fetchall()

    # 2. canonical_url 与 url 不一致（说明归一化没生效）
    mismatches = cur.execute("""
        SELECT id, wechat_name, title, url, canonical_url
        FROM articles
        WHERE canonical_url IS NULL OR canonical_url = ''
           OR (url LIKE '%search_click_id=%' AND canonical_url = url)
    """).fetchall()

    # 3. canonical_url 在多条记录中重复
    canonical_dupes = cur.execute("""
        SELECT canonical_url, COUNT(*) as cnt, GROUP_CONCAT(id, '|') as ids
        FROM articles
        WHERE canonical_url IS NOT NULL
        GROUP BY canonical_url
        HAVING cnt > 1
    """).fetchall()

    total = cur.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    print(f"数据库总数: {total}")
    print(f"(wechat_name+title+date) 重复组: {len(dupes_by_article)}")
    print(f"URL 归一化未生效: {len(mismatches)}")
    print(f"canonical_url 重复: {len(canonical_dupes)}")

    if dupes_by_article:
        print("\n[详情] 重复组:")
        for r in dupes_by_article:
            print(f"  x{r['cnt']} [{r['wechat_name']}] {r['publish_date']}")
            print(f"      title: {r['title'][:60]}")
            print(f"      ids: {r['ids']} | types: {r['types']}")
            print(f"      canonicals: {r['canonicals'][:100]}")

    if mismatches:
        print("\n[详情] 归一化未生效记录:")
        for r in mismatches[:5]:
            print(f"  #{r['id']} {r['url'][:80]} → {r['canonical_url']}")

    if canonical_dupes:
        print("\n[详情] canonical_url 重复:")
        for r in canonical_dupes[:5]:
            print(f"  x{r['cnt']} {r['canonical_url']} (ids: {r['ids']})")

    has_issue = bool(dupes_by_article or mismatches or canonical_dupes)
    print()
    if has_issue:
        print("⚠️  发现数据问题！")
        sys.exit(1)
    else:
        print("✅ 数据干净，0重复 0未归一化")
        sys.exit(0)


if __name__ == '__main__':
    main()
