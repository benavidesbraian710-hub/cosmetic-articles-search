#!/usr/bin/env python3
"""今日采集入库导出部署脚本"""

import json
import sqlite3
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import os

# 今日采集结果（正确的12个公众号，已去重）
TODAY_LINKS = {
  '妆研24小时': [
    'https://mp.weixin.qq.com/s/Q_Vv8tHn_URLWc1TNRkCKA',
    'https://mp.weixin.qq.com/s/W6JBuHco8yNqGp0zbddWTg',
    'https://mp.weixin.qq.com/s/g61vgigWatg1-pikCDGWig',
    'https://mp.weixin.qq.com/s/tR8WPbfdW9xzKnBA36qywA'
  ],
  '个护前沿': [
    'https://mp.weixin.qq.com/s/eHmEamQKro3xn8gFKN_jRA',
    'https://mp.weixin.qq.com/s/1Nyno0kyAJo2Ike6LJdi8w',
    'https://mp.weixin.qq.com/s/qvTOX01u2L8AGFcfLKtclg',
    'https://mp.weixin.qq.com/s/ptwzArKYig47xAvQHOVAAg'
  ],
  '中国化妆品': [
    'https://mp.weixin.qq.com/s/vsBi1lkuk7i3PBtuIkGoMA',
    'https://mp.weixin.qq.com/s/QBIltmbu5g0NBkj6FU8gjw',
    'https://mp.weixin.qq.com/s/RL2Z9gdG9ABhFbLj837aDA'
  ],
  '化妆品观察 品观': [
    'https://mp.weixin.qq.com/s/17a_-RBqSAXxLTsX-Les4w',
    'https://mp.weixin.qq.com/s/7QkldEz5QSzV7sfhJgFfuA',
    'https://mp.weixin.qq.com/s/Rrkzs6NYiq2LN5ivecv1vA',
    'https://mp.weixin.qq.com/s/VTjTEDv3o3GTicOlUiPCcg'
  ],
  '非科学美妆传播': [
    'https://mp.weixin.qq.com/s/5sBjxJI07qT9cxsZZ0m8Gg',
    'https://mp.weixin.qq.com/s/eRtfz378Aol_IOTtzCQ2gw',
    'https://mp.weixin.qq.com/s/ily6gpN4T6BdwBn9q1SiFA',
    'https://mp.weixin.qq.com/s/64Y-A4YAYAfbr2OH3O0ODQ'
  ],
  'Fbeauty未来迹': [
    'https://mp.weixin.qq.com/s/J0egeVqwt9OF9wguZmz-ug',
    'https://mp.weixin.qq.com/s/kjj4u0W-bYf-Hd8ige-sfQ',
    'https://mp.weixin.qq.com/s/EyiWixY_Ro99nIFPmiJ6MQ',
    'https://mp.weixin.qq.com/s/3NTI9rlgT_7eB24FLqfcEQ'
  ],
  '原料合规观察': [
    'https://mp.weixin.qq.com/s/Yj5Umo-kXDMvUcT0GzhQtg',
    'https://mp.weixin.qq.com/s/WzTTjvyMuvpJzI5y2muRJA',
    'https://mp.weixin.qq.com/s/V2XO_pBJzIKlo77dQ_l6Mg',
    'https://mp.weixin.qq.com/s/xfhMjGj9SFmNoEVZeiX5Dg'
  ],
  '肤见未来实验室': [
    'https://mp.weixin.qq.com/s/wJpkMag43k9kSDt77FYjFQ',
    'https://mp.weixin.qq.com/s/AyYwZhRhBmcUVaYYeQBx3g',
    'https://mp.weixin.qq.com/s/ZO7nsPrSE0HbzeIL9B7HeA',
    'https://mp.weixin.qq.com/s/Ow0GrDHbrhGp3UhJRMYXkg'
  ],
  '妆合规': [
    'https://mp.weixin.qq.com/s/vPrAk_NQjTN8rbzihx8I4w',
    'https://mp.weixin.qq.com/s/s1IXq9NDJvMaE6ZKWtGBPw',
    'https://mp.weixin.qq.com/s/4udFuvgBoF3W_IysiX6l6g',
    'https://mp.weixin.qq.com/s/PWR6q7YiFYxaKkWcuIo2Iw'
  ],
  'KEV美妆': [
    'https://mp.weixin.qq.com/s/pDVwhEL-SsRt64Hb1H3MuQ',
    'https://mp.weixin.qq.com/s/kK_l6HPKrtDXtMl9_CFzqw',
    'https://mp.weixin.qq.com/s/BQTyaxFxriNJs5mCfhgl-A',
    'https://mp.weixin.qq.com/s/1Mea5XK1V7JmNhF_anoE1Q'
  ],
  '美业颜究院': [
    'https://mp.weixin.qq.com/s/7bjHnV367LNFTc17XlqAtQ',
    'https://mp.weixin.qq.com/s/v98znr4DIRT2BJ4ROhQJ0w',
    'https://mp.weixin.qq.com/s/YowNDzJCMYw0iR2wWIzYVw',
    'https://mp.weixin.qq.com/s/M84VMfkWt8Gpumese3GrDg'
  ],
  '上海日化协会': [
    'https://mp.weixin.qq.com/s/JG4Yep6qWjKNHxTEbcaENA',
    'https://mp.weixin.qq.com/s/kbILMB42XU9LftiLoIuI2Q',
    'https://mp.weixin.qq.com/s/mPUjfCboGkyYbJKnmr85vw',
    'https://mp.weixin.qq.com/s/-OybNueOfWaKjaX9UGtWQA'
  ]
}

DB_PATH = Path.home() / '.openclaw/workspace/cosmetic-deploy/cosmetic_articles.db'
GIT_PATH = Path.home() / '.openclaw/workspace/cosmetic-deploy'
EXPORT_PATH = Path.home() / '.openclaw/workspace/cosmetic-deploy/export_data.py'

def fetch_article_info(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://mp.weixin.qq.com/',
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='replace')
        
        title = ''
        m = re.search(r'<h1[^>]*class="rich_media_title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        
        publish_date = ''
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
        
        return {'url': url, 'title': title, 'publish_date': publish_date}
    except Exception as e:
        print(f'  ⚠️  抓取失败: {url} - {e}')
        return None

def main():
    print('=' * 60)
    print('今日采集入库导出部署')
    print('=' * 60)
    
    # 入库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    total_added = 0
    total_skipped = 0
    
    for account, links in TODAY_LINKS.items():
        print(f'\n[{account}] 处理 {len(links)} 篇文章...')
        added = 0
        skipped = 0
        
        for url in links:
            info = fetch_article_info(url)
            if not info:
                skipped += 1
                continue
            
            # 过滤6月15日前
            if info['publish_date'] and info['publish_date'] < '2026-06-15':
                print(f'  ⏭️  跳过(6月15日前): {info["title"][:50]}... | {info["publish_date"]}')
                skipped += 1
                continue
            
            try:
                cursor.execute('INSERT INTO articles (wechat_name, title, url, publish_date) VALUES (?, ?, ?, ?)',
                              (account, info['title'], info['url'], info['publish_date']))
                added += 1
                print(f'  ✅ 新增: {info["title"][:50]}...')
            except sqlite3.IntegrityError:
                print(f'  ⏭️  跳过(已存在): {info["title"][:50]}...')
                skipped += 1
            
            time.sleep(0.5)
        
        total_added += added
        total_skipped += skipped
        print(f'✅ {account}: 新增 {added} 篇, 跳过 {skipped} 篇')
    
    conn.commit()
    conn.close()
    
    print(f'\n📊 入库完成: 新增 {total_added} 篇, 跳过 {total_skipped} 篇')
    
    # 导出
    print('\n📦 导出数据...')
    result = subprocess.run(['python3', str(EXPORT_PATH)], capture_output=True, text=True, timeout=60)
    print(result.stdout)
    if result.returncode != 0:
        print(f'❌ 导出失败: {result.stderr}')
        return
    
    # 递增版本号
    index_html = GIT_PATH / 'index.html'
    html_content = index_html.read_text(encoding='utf-8')
    version_match = re.search(r'data\.v(\d+)\.json', html_content)
    if version_match:
        current_version = int(version_match.group(1))
        new_version = current_version + 1
    else:
        new_version = 1
    
    old_filename = f'data.v{current_version}.json' if version_match else 'data.json'
    new_filename = f'data.v{new_version}.json'
    
    print(f'\n📦 版本更新: {old_filename} → {new_filename}')
    
    data_json = GIT_PATH / 'data.json'
    new_data_file = GIT_PATH / new_filename
    
    if data_json.exists():
        old_data_file = GIT_PATH / old_filename
        if old_data_file.exists() and old_data_file != data_json:
            old_data_file.unlink()
            print(f'🗑️  删除旧版本: {old_filename}')
        shutil.copy2(data_json, new_data_file)
        print(f'✅ 创建新版本: {new_filename}')
    else:
        print('❌ data.json 不存在')
        return
    
    updated_html = html_content.replace(old_filename, new_filename)
    index_html.write_text(updated_html, encoding='utf-8')
    print(f'✅ 更新 index.html 加载路径: {new_filename}')
    
    # Git推送
    git_cmds = [
        ['git', 'add', '-A'],
        ['git', 'commit', '-m', f'data: update to v{new_version} ({datetime.now().strftime("%Y-%m-%d %H:%M")})'],
        ['git', 'push', 'origin', 'main']
    ]
    
    for cmd in git_cmds:
        result = subprocess.run(cmd, cwd=GIT_PATH, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f'Git失败: {cmd}')
            print(result.stderr)
        else:
            print(result.stdout.strip())
    
    print(f'✅ 推送完成: v{new_version}')
    
    # 触发Deploy Hook
    print('\n🚀 触发Vercel Deploy Hook...')
    try:
        VERCEL_DEPLOY_HOOK = os.environ.get('VERCEL_DEPLOY_HOOK', 'https://api.vercel.com/v1/integrations/deploy/prj_YSlalkG8s0mnj6tOhT2x40NI5MNg/TYK5SZROD3')
        req = urllib.request.Request(VERCEL_DEPLOY_HOOK, method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status == 201:
                print('✅ Vercel 部署已触发')
            else:
                print(f'⚠️ Deploy Hook 状态: {response.status}')
    except Exception as e:
        print(f'⚠️ Deploy Hook 失败: {e}')
    
    print('\n' + '=' * 60)
    print('✅ 全部完成!')
    print(f'新增: {total_added} 篇')
    print(f'跳过: {total_skipped} 篇')
    print(f'版本: v{new_version}')
    print('=' * 60)

if __name__ == '__main__':
    main()
