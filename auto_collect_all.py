#!/usr/bin/env python3
"""
全量采集脚本 - 自动分批执行

自动采集所有公众号，分批执行避免超时
"""

import subprocess
import time
import json
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

# 入库脚本路径
IMPORT_PATH = Path.home() / ".openclaw/workspace/cosmetic-deploy/collect_from_csv.py"

# 导出脚本路径
EXPORT_PATH = Path.home() / ".openclaw/workspace/cosmetic-deploy/export_data.py"

# Git 推送
GIT_PATH = Path.home() / ".openclaw/workspace/cosmetic-deploy"


def collect_account(account: str, count: int = 4) -> bool:
    """采集单个公众号"""
    print(f"\n{'='*60}")
    print(f"采集: {account} ({count}篇)")
    print('='*60)
    
    # 先激活微信窗口
    print("激活微信窗口...")
    subprocess.run([
        'osascript', '-e',
        'tell application "WeChat" to activate'
    ], capture_output=True)
    time.sleep(2)
    
    # 使用 peekaboo 聚焦窗口
    for app_name in ["WeChat", "微信"]:
        result = subprocess.run(
            f'peekaboo focus --app "{app_name}"',
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  已聚焦到: {app_name}")
            break
    time.sleep(1)
    
    cmd = [
        "python3", str(COLLECTOR_PATH),
        json.dumps({"tasks": [{"account": account, "count": count}]})
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        print(result.stdout)
        if result.stderr:
            print(f"stderr: {result.stderr}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"⚠️  采集超时: {account}")
        return False
    except Exception as e:
        print(f"❌ 采集失败: {account} - {e}")
        return False


def import_csv() -> int:
    """导入最新的CSV文件（兼容旧版本）"""
    print(f"\n{'='*60}")
    print("导入CSV到数据库...")
    print('='*60)
    
    # 找到最新的CSV文件
    desktop = Path.home() / "Desktop"
    csv_files = list(desktop.glob("wechat_articles_*.csv"))
    
    if not csv_files:
        print("⚠️  没有找到CSV文件（可能已使用直接入库模式）")
        return 0
    
    # 按修改时间排序，取最新的
    latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
    
    print(f"导入: {latest_csv}")
    
    cmd = ["python3", str(IMPORT_PATH), str(latest_csv)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    print(result.stdout)
    
    # 解析导入结果
    added = 0
    for line in result.stdout.split('\n'):
        if '新增:' in line:
            try:
                added = int(line.split('新增:')[1].split('篇')[0].strip())
            except:
                pass
    
    return added


def export_and_push():
    """导出数据并推送到GitHub"""
    print(f"\n{'='*60}")
    print("导出数据并推送...")
    print('='*60)
    
    # 导出数据
    cmd = ["python3", str(EXPORT_PATH)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    print(result.stdout)
    
    # Git 推送
    git_cmds = [
        ["git", "add", "data.json"],
        ["git", "commit", "-m", f"全量采集更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
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
    print("微信公众号全量采集")
    print(f"共 {len(ACCOUNTS)} 个公众号")
    print("="*60)
    
    total_collected = 0
    failed_accounts = []
    
    for i, account in enumerate(ACCOUNTS, 1):
        print(f"\n\n[{i}/{len(ACCOUNTS)}] 开始采集: {account}")
        
        # 采集
        success = collect_account(account, 4)
        
        if success:
            # 导入
            added = import_csv()
            total_collected += added
            print(f"✅ {account}: 新增 {added} 篇")
        else:
            failed_accounts.append(account)
            print(f"❌ {account}: 采集失败")
        
        # 间隔，避免过快
        if i < len(ACCOUNTS):
            print(f"等待 3 秒...")
            time.sleep(3)
    
    # 最后导出和推送
    export_and_push()
    
    # 总结
    print(f"\n{'='*60}")
    print("采集完成!")
    print('='*60)
    print(f"总采集: {total_collected} 篇")
    print(f"失败: {len(failed_accounts)} 个")
    if failed_accounts:
        print(f"失败列表: {', '.join(failed_accounts)}")
    
    # 保存失败列表到文件
    if failed_accounts:
        failed_file = Path.home() / "Desktop/failed_accounts.txt"
        with open(failed_file, 'w') as f:
            f.write('\n'.join(failed_accounts))
        print(f"失败列表已保存: {failed_file}")


if __name__ == "__main__":
    main()
