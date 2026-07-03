#!/usr/bin/env python3
"""
全量采集脚本 v2 - 直接入库，不生成 CSV 文件

流程:
1. 采集文章链接（微信坐标点击）
2. 直接抓取文章信息（标题、日期、内容）
3. 直接入库 SQLite（去重）
4. 导出 data.json 并推送到 GitHub
"""

import subprocess
import time
import json
import sqlite3
import re
from datetime import datetime
from pathlib import Path

# 公众号列表（12个）
ACCOUNTS = [
    "妆研24小时",
    "非科学美妆传播", 
    "原料合规观察",
    "妆合规",
    "Fbeauty未来迹",
    "个护前沿",
    "KEV美妆",
    "美业颜究院",
    "肤见未来实验室",
    "化妆品观察 品观",
    "中国化妆品",
    "上海日化协会"
]

# 采集器路径
COLLECTOR_PATH = Path.home() / ".openclaw/workspace/wechat-collector/skills/wechat-article-collector/scripts/collect.py"

# 数据库路径
DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"

# 导出脚本路径
EXPORT_PATH = Path.home() / ".openclaw/workspace/cosmetic-deploy/export_data.py"

# Git 推送
GIT_PATH = Path.home() / ".openclaw/workspace/cosmetic-deploy"


def collect_links_batch(count_per_account: int = 4) -> dict:
    """批量采集所有公众号文章链接，返回 {公众号: [链接列表]}"""
    print(f"\n{'='*60}")
    print(f"批量采集 {len(ACCOUNTS)} 个公众号")
    print('='*60)
    
    # 构建批量采集任务
    tasks = []
    for account in ACCOUNTS:
        tasks.append({"account": account, "count": count_per_account})
    
    # 运行采集器（批量采集所有公众号）
    cmd = [
        "python3", "-u", str(COLLECTOR_PATH),
        json.dumps({"tasks": tasks, "skip_csv": True})
    ]
    
    print(f"批量采集 {len(tasks)} 个公众号...")
    
    try:
        # 使用Popen实时读取输出，避免缓冲
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(COLLECTOR_PATH.parent)
        )
        
        print("Skill启动成功，等待输出...")
        
        # 实时读取stdout
        stdout_lines = []
        for line in process.stdout:
            line = line.strip()
            stdout_lines.append(line)
            print(f"  [Skill] {line[:100]}")
        
        # 等待进程完成
        process.wait(timeout=1800)
        
        print(f"Skill返回码: {process.returncode}")
        
        # 从输出中提取JSON
        stdout_text = '\n'.join(stdout_lines)
        json_start = stdout_text.find('{')
        json_end = stdout_text.rfind('}')
        
        if json_start != -1 and json_end != -1:
            json_str = stdout_text[json_start:json_end+1]
            try:
                all_links = json.loads(json_str)
                print(f"✅ 批量采集完成，共 {len(all_links)} 个公众号")
                return all_links
            except json.JSONDecodeError:
                print("❌ JSON解析失败")
        
        # 从文本中提取
        all_links = {}
        current_account = None
        for line in stdout_lines:
            if '✅ 链接:' in line:
                link = line.replace('✅ 链接:', '').strip()
                if current_account and link:
                    all_links[current_account].append(link)
            elif '采集:' in line:
                match = re.search(r'采集:\s*(.+?)\s*\(', line)
                if match:
                    current_account = match.group(1).strip()
                    all_links[current_account] = []
        
        print(f"✅ 批量采集完成，共 {len(all_links)} 个公众号")
        return all_links
        
    except subprocess.TimeoutExpired:
        print(f"⚠️  批量采集超时（30分钟）")
        process.kill()
        return {}
    except Exception as e:
        print(f"❌ 批量采集失败: {e}")
        return {}


def fetch_article_info(url: str) -> dict:
    """抓取文章信息"""
    import urllib.request
    
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
        # 方法1: s1s_context_info
        m = re.search(r'publish_time%22%3A(\d{10})', html)
        if m:
            ts = int(m.group(1))
            publish_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        else:
            # 方法2: JSON时间戳
            m = re.search(r'"publish_time"\s*:\s*(\d{10})', html)
            if m:
                ts = int(m.group(1))
                publish_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            else:
                # 方法3: 页面所有日期
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
    """保存文章到数据库，返回新增数量"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    added = 0
    for article in articles:
        if not article:
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
    return added


def export_and_push():
    """导出数据并推送到GitHub"""
    print(f"\n{'='*60}")
    print("导出数据并推送...")
    print('='*60)
    
    cmd = ["python3", str(EXPORT_PATH)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    print(result.stdout)
    
    git_cmds = [
        ["git", "add", "data.json"],
        ["git", "commit", "-m", f"数据更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
        ["git", "push", "origin", "main"]
    ]
    
    for cmd in git_cmds:
        result = subprocess.run(cmd, cwd=GIT_PATH, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"Git 命令失败: {cmd}")
            print(result.stderr)
        else:
            print(result.stdout)


def main():
    print("="*60)
    print("微信公众号全量采集 v2 - 直接入库")
    print(f"共 {len(ACCOUNTS)} 个公众号")
    print("="*60)
    
    # 1. 批量采集所有公众号链接
    print("\n开始批量采集...")
    all_links = collect_links_batch(4)
    
    if not all_links:
        print("❌ 批量采集失败")
        return
    
    # 2. 逐个处理每个公众号的文章
    total_added = 0
    total_skipped = 0
    failed_accounts = []
    
    for i, account in enumerate(ACCOUNTS, 1):
        print(f"\n\n[{i}/{len(ACCOUNTS)}] 处理: {account}")
        
        links = all_links.get(account, [])
        
        if not links:
            failed_accounts.append(account)
            print(f"❌ {account}: 未获取到链接")
            continue
        
        # 抓取文章信息
        print(f"  抓取 {len(links)} 篇文章信息...")
        articles = []
        for url in links:
            info = fetch_article_info(url)
            if info:
                articles.append(info)
            time.sleep(0.5)
        
        # 入库
        added = save_to_db(articles, account)
        total_added += added
        total_skipped += len(articles) - added
        
        print(f"✅ {account}: 新增 {added} 篇, 跳过 {len(articles) - added} 篇")
        
        # 间隔
        if i < len(ACCOUNTS):
            print(f"等待 3 秒...")
            time.sleep(3)
    
    # 3. 导出和推送
    export_and_push()
    
    # 4. 自动部署到 Vercel (使用 Deploy Hook)
    print(f"\n{'='*60}")
    print("正在部署到 Vercel...")
    print('='*60)
    
    # 使用 Deploy Hook 触发自动部署
    deploy_hook_url = os.environ.get('VERCEL_DEPLOY_HOOK', '')
    if deploy_hook_url:
        try:
            import urllib.request
            req = urllib.request.Request(deploy_hook_url, method='POST')
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 201:
                    print("✅ Vercel 部署已触发 (Deploy Hook)")
                else:
                    print(f"⚠️ Deploy Hook 返回状态: {response.status}")
        except Exception as e:
            print(f"⚠️ Deploy Hook 触发失败: {e}")
            print("请手动在 Vercel 控制台点击 Redeploy")
    else:
        print("⚠️ 未配置 VERCEL_DEPLOY_HOOK 环境变量")
        print("请配置后自动部署生效")
        print("配置方法: export VERCEL_DEPLOY_HOOK='https://api.vercel.com/v1/integrations/deploy/...'")
    
    # 5. 总结
    print(f"\n{'='*60}")
    print("采集完成!")
    print('='*60)
    print(f"新增: {total_added} 篇")
    print(f"跳过: {total_skipped} 篇")
    print(f"失败: {len(failed_accounts)} 个")
    if failed_accounts:
        print(f"失败列表: {', '.join(failed_accounts)}")


if __name__ == "__main__":
    main()
