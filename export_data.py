#!/usr/bin/env python3
"""
化妆品文章数据导出脚本
用于定时更新网站数据
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.expanduser('~/.openclaw/cosmetic_articles.db')
OUTPUT_PATH = os.path.expanduser('~/.openclaw/workspace/cosmetic-deploy/data.json')

def export_data():
    """导出数据库数据为JSON"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取统计信息
        cursor.execute("SELECT COUNT(*) FROM articles")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT source) FROM articles")
        source_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(publish_date), MAX(publish_date) FROM articles")
        date_range = cursor.fetchone()
        
        # 获取公众号列表
        cursor.execute("""
            SELECT source, COUNT(*) as count 
            FROM articles 
            GROUP BY source 
            ORDER BY count DESC
        """)
        sources = []
        for row in cursor.fetchall():
            sources.append({
                'name': row['source'],
                'count': row['count']
            })
        
        # 获取所有文章（按公众号分组）
        articles_by_source = {}
        for source in sources:
            source_name = source['name']
            cursor.execute("""
                SELECT id, title, source, publish_date, url, summary, keywords
                FROM articles
                WHERE source = ?
                ORDER BY publish_date DESC
            """, (source_name,))
            
            articles = []
            for row in cursor.fetchall():
                try:
                    keywords = json.loads(row['keywords']) if row['keywords'] else []
                except:
                    keywords = []
                
                articles.append({
                    'id': row['id'],
                    'title': row['title'],
                    'source': row['source'],
                    'publish_date': row['publish_date'],
                    'url': row['url'],
                    'summary': row['summary'] or '',
                    'keywords': keywords
                })
            
            articles_by_source[source_name] = articles
        
        conn.close()
        
        # 构建数据
        data = {
            'stats': {
                'total_articles': total,
                'source_count': source_count,
                'date_range': {
                    'start': date_range[0],
                    'end': date_range[1]
                },
                'last_update': datetime.now().isoformat()
            },
            'sources': sources,
            'articles': articles_by_source
        }
        
        # 保存为JSON
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 数据导出成功: {OUTPUT_PATH}")
        print(f"   文章总数: {total}")
        print(f"   公众号数: {source_count}")
        print(f"   更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 导出失败: {e}")
        return False

if __name__ == '__main__':
    export_data()
