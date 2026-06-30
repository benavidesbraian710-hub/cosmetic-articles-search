#!/usr/bin/env python3
"""
使用微信内置浏览器获取文章真实发布时间
"""

import sqlite3
import subprocess
import re
from datetime import datetime
from pathlib import Path
import time

DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"

def get_time_from_wechat_browser(url: str) -> str:
    """使用微信内置浏览器获取文章时间"""
    
    # 方法1: 使用 AppleScript 控制微信，获取页面文本
    applescript = '''
    tell application "System Events"
        tell process "WeChat"
            try
                -- 获取页面所有文本元素
                set allTexts to {}
                repeat with i from 1 to 50
                    try
                        set t to name of UI element i of scroll area 1 of window 1
                        if t is not "" then
                            set end of allTexts to t
                        end if
                    end try
                end repeat
                return allTexts as string
            on error
                return ""
            end try
        end tell
    end tell
    '''
    
    try:
        result = subprocess.run(['osascript', '-e', applescript], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            text = result.stdout
            # 查找日期模式: 2026-06-18 或 2026年06月18日
            date_match = re.search(r'(\d{4})[-年](\d{2})[-月](\d{2})', text)
            if date_match:
                year, month, day = date_match.groups()
                return f"{year}-{month}-{day}"
    except Exception as e:
        print(f"AppleScript 错误: {e}")
    
    # 方法2: 使用 osascript 获取微信浏览器URL，从中提取参数
    try:
        url_script = '''
        tell application "System Events"
            tell process "WeChat"
                try
                    -- 尝试获取当前页面URL
                    set frontWindow to window 1
                    return name of frontWindow as string
                on error
                    return ""
                end try
            end tell
        end tell
        '''
        
        result = subprocess.run(['osascript', '-e', url_script], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            window_title = result.stdout.strip()
            # 窗口标题可能包含时间信息
            date_match = re.search(r'(\d{4})[-年](\d{2})[-月](\d{2})', window_title)
            if date_match:
                year, month, day = date_match.groups()
                return f"{year}-{month}-{day}"
    except:
        pass
    
    return None


def fix_articles_with_wechat():
    """使用微信内置浏览器修复文章时间"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取需要修复的文章（时间可能不正确的）
    cursor.execute("""
        SELECT id, url, title, publish_date 
        FROM articles 
        WHERE publish_date = '' OR publish_date IS NULL OR publish_date = '2026-06-18' OR publish_date = '2026-06-17'
        ORDER BY id
    """)
    
    articles = cursor.fetchall()
    
    if not articles:
        print("没有需要修复的文章！")
        conn.close()
        return
    
    print(f"共 {len(articles)} 篇文章需要修复")
    print("=" * 60)
    print("请确保微信已打开，并且文章页面已加载")
    print("=" * 60)
    
    updated = 0
    failed = 0
    
    for i, (article_id, url, title, old_date) in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] {title[:50]}...")
        print(f"  旧日期: {old_date}")
        
        # 使用微信浏览器获取时间
        real_date = get_time_from_wechat_browser(url)
        
        if real_date and real_date != old_date:
            cursor.execute(
                "UPDATE articles SET publish_date = ? WHERE id = ?",
                (real_date, article_id)
            )
            conn.commit()
            print(f"  ✅ 更新为: {real_date}")
            updated += 1
        elif real_date:
            print(f"  ✅ 时间正确")
        else:
            print(f"  ⚠️ 无法获取，保持原样")
            failed += 1
        
        # 每篇暂停2秒
        time.sleep(2)
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"✅ 完成！")
    print(f"   更新: {updated} 篇")
    print(f"   失败: {failed} 篇")
    print(f"   总计: {len(articles)} 篇")


if __name__ == "__main__":
    print("=" * 60)
    print("  使用微信内置浏览器修复文章时间")
    print("=" * 60)
    print()
    print("说明：此脚本使用 AppleScript 控制微信获取页面时间")
    print("请确保微信已打开，并且文章页面可以访问")
    print()
    
    fix_articles_with_wechat()
