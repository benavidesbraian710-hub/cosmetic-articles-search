#!/usr/bin/env python3
"""
微信公众号文章采集器 - Mac 适配版
基于 wechat-article-collector 适配 Mac 系统

功能：
1. 从微信 Mac 版获取公众号文章链接
2. 支持手动输入或自动采集
3. 自动入库到 cosmetic_articles.db

使用方法：
1. 在微信 Mac 版中打开公众号文章列表
2. 运行脚本采集文章链接
3. 自动保存到数据库
"""

import sqlite3
import json
import csv
import time
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
import re
import urllib.parse

# 数据库路径
DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"

class WeChatArticleCollectorMac:
    """Mac 版微信文章采集器"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.ensure_db_exists()
    
    def ensure_db_exists(self):
        """确保数据库存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建文章表（如果不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                publish_date TEXT,
                summary TEXT,
                keywords TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        print(f"✅ 数据库就绪: {self.db_path}")
    
    def add_article(self, title, url, source, publish_date=None, summary=""):
        """添加单篇文章到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if not publish_date:
            publish_date = datetime.now().strftime("%Y-%m-%d")
        
        # 检查是否已存在
        cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
        if cursor.fetchone():
            print(f"⚠️  文章已存在: {title}")
            conn.close()
            return False
        
        # 插入文章
        cursor.execute("""
            INSERT INTO articles (title, url, source, publish_date, summary, keywords, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, url, source, publish_date, summary, json.dumps([]), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        print(f"✅ 已添加: {title}")
        return True
    
    def import_from_csv(self, csv_file):
        """从 CSV 文件导入文章"""
        if not os.path.exists(csv_file):
            print(f"❌ 文件不存在: {csv_file}")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        added = 0
        skipped = 0
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 检查必要字段
                if 'url' not in row or not row['url']:
                    continue
                
                # 检查是否已存在
                cursor.execute("SELECT id FROM articles WHERE url = ?", (row['url'],))
                if cursor.fetchone():
                    skipped += 1
                    continue
                
                # 插入文章
                cursor.execute("""
                    INSERT INTO articles (title, url, source, publish_date, summary, keywords, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('title', '未命名文章'),
                    row['url'],
                    row.get('source', '未知公众号'),
                    row.get('publish_date', datetime.now().strftime("%Y-%m-%d")),
                    row.get('summary', ''),
                    json.dumps([]),
                    datetime.now().isoformat()
                ))
                added += 1
        
        conn.commit()
        conn.close()
        print(f"✅ 导入完成: 新增 {added} 篇, 跳过 {skipped} 篇")
    
    def export_to_csv(self, output_file=None):
        """导出文章到 CSV"""
        if not output_file:
            output_file = f"wechat_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM articles ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        if not rows:
            print("⚠️  数据库中没有文章")
            conn.close()
            return
        
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['公众号', '标题', '链接', '发布日期', '摘要', '采集时间'])
            
            for row in rows:
                writer.writerow([
                    row['source'],
                    row['title'],
                    row['url'],
                    row['publish_date'],
                    row['summary'],
                    row['created_at']
                ])
        
        conn.close()
        print(f"✅ 已导出 {len(rows)} 篇文章到: {output_file}")
    
    def get_stats(self):
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM articles")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT source) FROM articles")
        sources = cursor.fetchone()[0]
        
        cursor.execute("SELECT source, COUNT(*) as count FROM articles GROUP BY source ORDER BY count DESC")
        source_list = cursor.fetchall()
        
        conn.close()
        
        print(f"\n📊 数据库统计:")
        print(f"   总文章数: {total}")
        print(f"   公众号数: {sources}")
        print(f"\n📰 公众号列表:")
        for source, count in source_list:
            print(f"   {source}: {count}篇")
    
    def interactive_add(self):
        """交互式添加文章"""
        print("\n📝 手动添加文章")
        print("=" * 50)
        
        source = input("请输入公众号名称: ").strip()
        if not source:
            print("❌ 公众号名称不能为空")
            return
        
        while True:
            print("\n" + "-" * 50)
            title = input("请输入文章标题 (或输入 'q' 退出): ").strip()
            if title.lower() == 'q':
                break
            
            url = input("请输入文章链接: ").strip()
            if not url:
                print("❌ 链接不能为空")
                continue
            
            publish_date = input("请输入发布日期 (格式: YYYY-MM-DD, 默认今天): ").strip()
            if not publish_date:
                publish_date = datetime.now().strftime("%Y-%m-%d")
            
            summary = input("请输入文章摘要 (可选): ").strip()
            
            self.add_article(title, url, source, publish_date, summary)
            print("\n✅ 文章添加成功！")

def main():
    """主函数"""
    collector = WeChatArticleCollectorMac()
    
    print("=" * 60)
    print("  微信公众号文章采集器 - Mac 版")
    print("=" * 60)
    print()
    
    while True:
        print("请选择操作:")
        print("1. 📥 从 CSV 导入文章")
        print("2. 📝 手动添加文章")
        print("3. 📤 导出文章到 CSV")
        print("4. 📊 查看统计信息")
        print("5. ❌ 退出")
        print()
        
        choice = input("请输入选项 (1-5): ").strip()
        
        if choice == '1':
            csv_file = input("请输入 CSV 文件路径: ").strip()
            collector.import_from_csv(csv_file)
        
        elif choice == '2':
            collector.interactive_add()
        
        elif choice == '3':
            output = input("请输入输出文件名 (默认自动生成): ").strip()
            collector.export_to_csv(output if output else None)
        
        elif choice == '4':
            collector.get_stats()
        
        elif choice == '5':
            print("\n👋 再见!")
            break
        
        else:
            print("❌ 无效选项，请重新选择")
        
        print("\n")

if __name__ == "__main__":
    main()
