#!/usr/bin/env python3
"""
单独采集三个新公众号：财经早餐、亿邦动力、铱星云商
"""

import subprocess
import time
import json
import sqlite3
import re
from datetime import datetime
from pathlib import Path

# Vercel Deploy Hook URL
VERCEL_DEPLOY_HOOK = 'https://api.vercel.com/v1/integrations/deploy/prj_YSlalkG8s0mnj6tOhT2x40NI5MNg/TYK5SZROD3'

# 只采集这三个新号
ACCOUNTS = [
    "财经早餐",
    "亿邦动力",
    "铱星云商"
]

# 采集器路径
COLLECTOR_PATH = Path.home() / ".openclaw/workspace/cosmetic-deploy/collect.py"

# 数据库路径
DB_PATH = Path.home() / ".openclaw/workspace/cosmetic-deploy/cosmetic_articles.db"

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
        "/usr/bin/python3", "-u", str(COLLECTOR_PATH),
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
        
        # 解析输出，提取链接
        links = {}
        current_account = None
        for line in stdout_lines:
            # 匹配 "[x/n] 采集: 公众号名" 或 "处理: 公众号名"
            if "采集:" in line and "]" in line:
                current_account = line.split("采集:", 1)[1].strip().split(" ")[0]
                links[current_account] = []
            elif line.startswith("处理:"):
                current_account = line.split(":", 1)[1].strip()
                links[current_account] = []
            # 匹配 "✅ 链接: http..." 或 "链接: http..."
            elif ("✅ 链接:" in line or line.startswith("链接:")) and current_account:
                if "✅ 链接:" in line:
                    url = line.split("✅ 链接:", 1)[1].strip()
                else:
                    url = line.split(":", 1)[1].strip()
                if url and url.startswith("http"):
                    links[current_account].append(url)
        
        return links
        
    except Exception as e:
        print(f"采集异常: {e}")
        return {}


def fetch_article_info(url: str) -> dict:
    """抓取文章信息（标题、日期、内容）"""
    try:
        # 使用 curl 获取页面内容
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", "30", url],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return None
        
        html = result.stdout
        
        # 提取标题
        title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        title = title_match.group(1) if title_match else ""
        
        # 提取日期
        date_match = re.search(r'<meta property="article:published_time" content="([^"]+)"', html)
        publish_date = date_match.group(1)[:10] if date_match else ""
        
        # 提取内容（简化版）
        content = ""
        
        return {
            "title": title,
            "publish_date": publish_date,
            "content": content
        }
        
    except Exception as e:
        print(f"抓取文章信息失败 {url}: {e}")
        return None


def save_to_db(account: str, articles: list) -> tuple:
    """保存到数据库，返回 (新增数, 跳过数)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_count = 0
    skip_count = 0
    
    for article in articles:
        url = article.get("url", "")
        if not url:
            continue
        
        # 检查是否已存在
        cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
        if cursor.fetchone():
            skip_count += 1
            continue
        
        # 插入新记录
        cursor.execute("""
            INSERT INTO articles (wechat_name, title, url, publish_date, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            account,
            article.get("title", ""),
            url,
            article.get("publish_date", ""),
            article.get("content", ""),
            datetime.now().isoformat()
        ))
        new_count += 1
    
    conn.commit()
    conn.close()
    
    return new_count, skip_count


def export_and_deploy():
    """导出数据并部署"""
    print(f"\n{'='*60}")
    print("导出数据并推送...")
    print('='*60)
    
    # 导出数据
    result = subprocess.run(
        ["/usr/bin/python3", str(EXPORT_PATH)],
        capture_output=True,
        text=True,
        cwd=str(GIT_PATH)
    )
    
    if result.returncode != 0:
        print(f"导出失败: {result.stderr}")
        return False
    
    print(result.stdout)
    
    # Git 提交并推送
    subprocess.run(["git", "add", "-A"], cwd=str(GIT_PATH))
    
    # 获取版本号
    version_file = GIT_PATH / "data.json"
    with open(version_file) as f:
        data = json.load(f)
        version = data.get("version", "unknown")
    
    commit_msg = f"data: update to {version} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=str(GIT_PATH))
    
    # 推送
    push_result = subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True,
        text=True,
        cwd=str(GIT_PATH)
    )
    
    if push_result.returncode != 0:
        print(f"推送失败: {push_result.stderr}")
        return False
    
    print(f"✅ 推送完成: {version}")
    
    # 触发 Vercel 部署
    print(f"\n{'='*60}")
    print("正在部署到 Vercel...")
    print('='*60)
    
    deploy_result = subprocess.run(
        ["curl", "-s", "-X", "POST", VERCEL_DEPLOY_HOOK],
        capture_output=True,
        text=True
    )
    
    print(f"✅ Vercel 部署已触发")
    print(f"   任务状态: {deploy_result.stdout[:100]}")
    
    return True


def main():
    print(f"开始采集: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标公众号: {', '.join(ACCOUNTS)}")
    
    # 1. 采集链接
    links = collect_links_batch(count_per_account=4)
    
    if not links:
        print("未采集到任何链接")
        return
    
    # 2. 抓取文章信息并入库
    total_new = 0
    total_skip = 0
    failed_accounts = []
    
    for i, account in enumerate(ACCOUNTS, 1):
        print(f"\n[{i}/{len(ACCOUNTS)}] 处理: {account}")
        
        account_links = links.get(account, [])
        if not account_links:
            print(f"❌ {account}: 未获取到链接")
            failed_accounts.append(account)
            continue
        
        print(f"  抓取 {len(account_links)} 篇文章信息...")
        
        articles = []
        for url in account_links:
            info = fetch_article_info(url)
            if info:
                info["url"] = url
                articles.append(info)
                print(f"  ✅ 新增: {info['title'][:50]}...")
            else:
                print(f"  ❌ 抓取失败: {url[:50]}...")
        
        # 入库
        new_count, skip_count = save_to_db(account, articles)
        total_new += new_count
        total_skip += skip_count
        
        print(f"✅ {account}: 新增 {new_count} 篇, 跳过 {skip_count} 篇")
        
        if i < len(ACCOUNTS):
            print("等待 3 秒...")
            time.sleep(3)
    
    # 3. 导出并部署
    if total_new > 0:
        export_and_deploy()
    
    # 4. 总结
    print(f"\n{'='*60}")
    print("采集完成!")
    print('='*60)
    print(f"新增: {total_new} 篇")
    print(f"跳过: {total_skip} 篇")
    print(f"失败: {len(failed_accounts)} 个")
    if failed_accounts:
        print(f"失败列表: {', '.join(failed_accounts)}")


if __name__ == "__main__":
    main()
