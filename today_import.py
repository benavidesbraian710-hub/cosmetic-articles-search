#!/usr/bin/env python3
"""
今日采集后处理脚本：从collect.py输出中提取链接，抓取信息，入库，导出，部署
"""

import subprocess
import json
import sqlite3
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path
import shutil

# 数据库路径
DB_PATH = Path.home() / ".openclaw/workspace/cosmetic-deploy/cosmetic_articles.db"
GIT_PATH = Path.home() / ".openclaw/workspace/cosmetic-deploy"
EXPORT_PATH = Path.home() / ".openclaw/workspace/cosmetic-deploy/export_data.py"

# 今日采集结果（从日志中提取的真实链接，已去重）
TODAY_LINKS = {
  "妆研24小时": [
    "https://mp.weixin.qq.com/s/47JsOTu0fL03ViD31IE-pQ"
  ],
  "个护前沿": [
    "https://mp.weixin.qq.com/s/eHmEamQKro3xn8gFKN_jRA",
    "https://mp.weixin.qq.com/s/1Nyno0kyAJo2Ike6LJdi8w",
    "https://mp.weixin.qq.com/s/qvTOX01u2L8AGFcfLKtclg",
    "https://mp.weixin.qq.com/s/ptwzArKYig47xAvQHOVAAg"
  ],
  "中国化妆品": [
    "https://mp.weixin.qq.com/s/vsBi1lkuk7i3PBtuIkGoMA",
    "https://mp.weixin.qq.com/s/QBIltmbu5g0NBkj6FU8gjw",
    "https://mp.weixin.qq.com/s/RL2Z9gdG9ABhFbLj837aDA"
  ],
  "化妆品观察 品观": [
    "https://mp.weixin.qq.com/s/17a_-RBqSAXxLTsX-Les4w",
    "https://mp.weixin.qq.com/s/Rrkzs6NYiq2LN5ivecv1vA",
    "https://mp.weixin.qq.com/s/7QkldEz5QSzV7sfhJgFfuA",
    "https://mp.weixin.qq.com/s/VTjTEDv3o3GTicOlUiPCcg"
  ],
  "非科学美妆传播": [
    "https://mp.weixin.qq.com/s/5sBjxJI07qT9cxsZZ0m8Gg",
    "https://mp.weixin.qq.com/s/eRtfz378Aol_IOTtzCQ2gw",
    "https://mp.weixin.qq.com/s/ily6gpN4T6BdwBn9q1SiFA",
    "https://mp.weixin.qq.com/s/64Y-A4YAYAfbr2OH3O0ODQ"
  ],
  "Fbeauty未来迹": [
    "https://mp.weixin.qq.com/s/J0egeVqwt9OF9wguZmz-ug",
    "https://mp.weixin.qq.com/s/kjj4u0W-bYf-Hd8ige-sfQ",
    "https://mp.weixin.qq.com/s/EyiWixY_Ro99nIFPmiJ6MQ",
    "https://mp.weixin.qq.com/s/3NTI9rlgT_7eB24FLqfcEQ"
  ],
  "原料合规观察": [
    "https://mp.weixin.qq.com/s/Yj5Umo-kXDMvUcT0GzhQtg",
    "https://mp.weixin.qq.com/s/WzTTjvyMuvpJzI5y2muRJA",
    "https://mp.weixin.qq.com/s/V2XO_pBJzIKlo77dQ_l6Mg",
    "https://mp.weixin.qq.com/s/xfhMjGj9SFmNoEVZeiX5Dg"
  ],
  "肤见未来实验室": [
    "https://mp.weixin.qq.com/s/wJpkMag43k9kSDt77FYjFQ",
    "https://mp.weixin.qq.com/s/AyYwZhRhBmcUVaYYeQBx3g",
    "https://mp.weixin.qq.com/s/ZO7nsPrSE0HbzeIL9B7HeA",
    "https://mp.weixin.qq.com/s/Ow0GrDHbrhGp3UhJRMYXkg"
  ],
  "美妆内行人": [
    "https://mp.weixin.qq.com/s/6yRPVRCkULmi32RsludHRQ",
    "https://mp.weixin.qq.com/s/oAuwRV6JEfE4dxWq82zG1g",
    "https://mp.weixin.qq.com/s/OprHAUPDzHmrxbUCNgsBdw",
    "https://mp.weixin.qq.com/s/Yjc8JEsg2i00ips5P-aPNA"
  ],
  "Beauty Insider": [
    "https://mp.weixin.qq.com/s/6yRPVRCkULmi32RsludHRQ",
    "https://mp.weixin.qq.com/s/oAuwRV6JEfE4dxWq82zG1g",
    "https://mp.weixin.qq.com/s/OprHAUPDzHmrxbUCNgsBdw",
    "https://mp.weixin.qq.com/s/Yjc8JEsg2i00ips5P-aPNA"
  ],
  "美业颜究院": [
    "https://mp.weixin.qq.com/s/7bjHnV367LNFTc17XlqAtQ",
    "https://mp.weixin.qq.com/s/v98znr4DIRT2BJ4ROhQJ0w",
    "https://mp.weixin.qq.com/s/YowNDzJCMYw0iR2wWIzYVw",
    "https://mp.weixin.qq.com/s/M84VMfkWt8Gpumese3GrDg"
  ],
  "青眼": [
    "https://mp.weixin.qq.com/s/HlhD4gcr3DgWXJSeoxdGQg",
    "https://mp.weixin.qq.com/s/N8tZX9OMCkn1jg96SLlj6g",
    "https://mp.weixin.qq.com/s/KK5_upo6rRY9XLeySAevjw",
    "https://mp.weixin.qq.com/s/0VBq6BPu_605SlL9S0BetA"
  ]
}

def fetch_article_info(url: str) -> dict:
    """抓取文章信息"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://mp.weixin.qq.com/',
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='replace')
        
        # 提取标题
        title = ""
        m = re.search(r'<h1[^>]*class="rich_media_title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        
        # 提取发布时间
        publish_date = ""
        m = re.search(r'publish_time%22%3A(\d{10})', html)
        if m:
            ts = int(m.group(1))
            publish_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        else:
            m = re.search(r'"publish_time"\s*:\s*(\d{10})', html)
            if m:
                ts = int(m.group(1))
                publish_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            else:
                dates = re.findall(r'(\d{4}-\d{2}-\d{2})', html)
                if dates:
                    valid_dates = [d for d in dates if d >= '2024-01-01']
                    if valid_dates:
                        publish_date = valid_dates[0]
        
        return {
            'url': url,
            'title': title,
            'publish_date': publish_date
        }
    except Exception as e:
        print(f"  ⚠️  抓取失败: {url} - {e}")
        return None

def save_to_db(articles: list, wechat_name: str) -> int:
    """保存文章到数据库，返回新增数量。自动过滤6月15日之前文章。"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    added = 0
    skipped_old = 0
    
    for article in articles:
        if not article:
            continue
        
        # 过滤6月15日之前文章
        if article['publish_date'] and article['publish_date'] < '2026-06-15':
            skipped_old += 1
            print(f"  ⏭️  跳过(6月15日前): {article['title'][:50]}... | {article['publish_date']}")
            continue
        
        try:
            cursor.execute('''
                INSERT INTO articles (wechat_name, title, url, publish_date)
                VALUES (?, ?, ?, ?)
            ''', (wechat_name, article['title'], article['url'], article['publish_date']))
            added += 1
            print(f"  ✅ 新增: {article['title'][:50]}...")
        except sqlite3.IntegrityError:
            print(f"  ⏭️  跳过(已存在): {article['title'][:50]}...")
    
    conn.commit()
    conn.close()
    
    if skipped_old > 0:
        print(f"  ⚠️  过滤 {skipped_old} 篇6月15日前文章")
    
    return added

def export_and_push():
    """导出数据并推送到GitHub"""
    print(f"\n{'='*60}")
    print("导出数据并推送...")
    print('='*60)
    
    # 1. 运行导出脚本
    cmd = ["python3", str(EXPORT_PATH)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ 导出失败: {result.stderr}")
        return False
    
    # 2. 获取当前版本号并递增
    index_html = GIT_PATH / "index.html"
    html_content = index_html.read_text(encoding='utf-8')
    
    version_match = re.search(r"data\.v(\d+)\.json", html_content)
    if version_match:
        current_version = int(version_match.group(1))
        new_version = current_version + 1
    else:
        new_version = 1
    
    old_filename = f"data.v{current_version}.json" if version_match else "data.json"
    new_filename = f"data.v{new_version}.json"
    
    print(f"📦 版本更新: {old_filename} → {new_filename}")
    
    # 3. 重命名 data.json 为新版本
    data_json = GIT_PATH / "data.json"
    new_data_file = GIT_PATH / new_filename
    
    if data_json.exists():
        old_data_file = GIT_PATH / old_filename
        if old_data_file.exists() and old_data_file != data_json:
            old_data_file.unlink()
            print(f"🗑️  删除旧版本: {old_filename}")
        
        shutil.copy2(data_json, new_data_file)
        print(f"✅ 创建新版本: {new_filename}")
    else:
        print(f"❌ data.json 不存在")
        return False
    
    # 4. 更新 index.html 加载路径
    updated_html = html_content.replace(old_filename, new_filename)
    index_html.write_text(updated_html, encoding='utf-8')
    print(f"✅ 更新 index.html 加载路径: {new_filename}")
    
    # 5. Git 提交和推送
    git_cmds = [
        ["git", "add", "-A"],
        ["git", "commit", "-m", f"data: update to v{new_version} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"],
        ["git", "push", "origin", "main"]
    ]
    
    for cmd in git_cmds:
        result = subprocess.run(cmd, cwd=GIT_PATH, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"Git 命令失败: {cmd}")
            print(result.stderr)
            return False
        else:
            print(result.stdout.strip())
    
    print(f"✅ 推送完成: {new_filename}")
    return True

def main():
    print("="*60)
    print("今日采集后处理 - 入库+导出+部署")
    print("="*60)
    
    # 1. 抓取文章信息并入库
    total_added = 0
    total_skipped = 0
    
    for account, links in TODAY_LINKS.items():
        print(f"\n[{account}] 处理 {len(links)} 篇文章...")
        
        articles = []
        for url in links:
            info = fetch_article_info(url)
            if info:
                articles.append(info)
            time.sleep(0.5)
        
        added = save_to_db(articles, account)
        total_added += added
        total_skipped += len(articles) - added
        
        print(f"✅ {account}: 新增 {added} 篇, 跳过 {len(articles) - added} 篇")
    
    # 2. 导出和推送
    push_success = export_and_push()
    
    # 3. 触发 Vercel Deploy Hook
    if push_success:
        print(f"\n{'='*60}")
        print("正在部署到 Vercel...")
        print('='*60)
        
        try:
            import os
            VERCEL_DEPLOY_HOOK = os.environ.get('VERCEL_DEPLOY_HOOK', 'https://api.vercel.com/v1/integrations/deploy/prj_YSlalkG8s0mnj6tOhT2x40NI5MNg/TYK5SZROD3')
            req = urllib.request.Request(VERCEL_DEPLOY_HOOK, method='POST')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 201:
                    print("✅ Vercel 部署已触发 (Deploy Hook)")
                else:
                    print(f"⚠️ Deploy Hook 返回状态: {response.status}")
        except Exception as e:
            print(f"⚠️ Deploy Hook 触发失败: {e}")
    
    # 4. 总结
    print(f"\n{'='*60}")
    print("处理完成!")
    print('='*60)
    print(f"新增: {total_added} 篇")
    print(f"跳过: {total_skipped} 篇")

if __name__ == "__main__":
    main()
