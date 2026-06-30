#!/usr/bin/env python3
"""
直接获取微信文章页面中的发布时间
使用 AppleScript 读取微信窗口文本
"""

import sqlite3
import subprocess
import re
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"

def get_wechat_page_text() -> str:
    """获取微信文章页面的所有文本"""
    
    # AppleScript 获取微信窗口文本
    script = '''
    tell application "System Events"
        tell process "WeChat"
            try
                set win to window 1
                set allText to ""
                
                -- 获取所有 UI 元素的文本
                repeat with elem in UI elements of win
                    try
                        set elemText to name of elem
                        if elemText is not "" then
                            set allText to allText & elemText & "\n"
                        end if
                    end try
                end repeat
                
                return allText
            on error errMsg
                return "Error: " & errMsg
            end try
        end tell
    end tell
    '''
    
    try:
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return result.stdout
    except Exception as e:
        print(f"获取文本失败: {e}")
    
    return ""


def extract_date_from_text(text: str) -> str:
    """从文本中提取日期"""
    # 匹配模式: 2026-06-18 或 2026年06月18日
    patterns = [
        r'(\d{4})-(\d{2})-(\d{2})',
        r'(\d{4})年(\d{2})月(\d{2})日',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month}-{day}"
    
    return None


def main():
    print("=" * 60)
    print("  获取微信文章页面时间")
    print("=" * 60)
    print()
    print("请确保：")
    print("1. 微信已打开")
    print("2. 文章页面已加载")
    print("3. 可以看到文章发布时间")
    print()
    
    input("按回车键开始获取...")
    
    print("\n正在获取页面文本...")
    text = get_wechat_page_text()
    
    if text:
        print(f"\n获取到的文本（前500字）:")
        print(text[:500])
        
        date = extract_date_from_text(text)
        if date:
            print(f"\n✅ 找到日期: {date}")
        else:
            print("\n❌ 未找到日期")
    else:
        print("\n❌ 无法获取页面文本")


if __name__ == "__main__":
    main()
