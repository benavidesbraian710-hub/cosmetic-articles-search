from flask import Flask, render_template, request, jsonify, make_response
import json
import sqlite3
import os
import csv
import io
from datetime import datetime

app = Flask(__name__)

# 数据库路径 - 使用环境变量或默认路径
DB_PATH = os.environ.get('DB_PATH', os.path.expanduser('~/.openclaw/cosmetic_articles.db'))

# 版本信息
VERSION = "1.0.0"
VERSION_NAME = "Basic"

@app.route('/')
def index():
    """首页 - 当前版本"""
    return render_template('index.html', version=VERSION, version_name=VERSION_NAME)

@app.route('/api/stats')
def api_stats():
    """统计API"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM articles")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT source) FROM articles")
        sources = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(publish_date), MAX(publish_date) FROM articles")
        date_range = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            'total_articles': total,
            'source_count': sources,
            'date_range': {
                'start': date_range[0],
                'end': date_range[1]
            },
            'version': VERSION,
            'version_name': VERSION_NAME
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sources')
def api_sources():
    """公众号列表API"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
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
        
        conn.close()
        return jsonify(sources)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/articles')
def api_articles():
    """文章列表API"""
    source = request.args.get('source', '')
    
    if not source:
        return jsonify([])
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, source, publish_date, url, summary, keywords
            FROM articles
            WHERE source = ?
            ORDER BY publish_date DESC
        """, (source,))
        
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
        
        conn.close()
        return jsonify(articles)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-basic', methods=['POST'])
def api_export_basic():
    """Basic版本导出API"""
    data = request.get_json()
    articles = data.get('articles', [])
    
    if not articles:
        return jsonify({'error': 'No articles to export'}), 400
    
    # 创建CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头（4列：公众号名称、文章名称、时间、链接）
    writer.writerow(['公众号名称', '文章名称', '时间', '链接'])
    
    # 写入数据
    for article in articles:
        writer.writerow([
            article.get('source', ''),
            article['title'],
            article['publish_date'],
            article['url']
        ])
    
    csv_content = output.getvalue()
    output.close()
    
    # 生成文件名
    filename = f"articles_{datetime.now().strftime('%Y%m%d')}.csv"
    
    # 创建响应，添加UTF-8 BOM
    response = make_response('\ufeff' + csv_content)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@app.route('/api/version')
def api_version():
    """版本信息API"""
    return jsonify({
        'version': VERSION,
        'version_name': VERSION_NAME,
        'build_time': datetime.now().isoformat(),
        'features': [
            'Basic版本 - 简洁视图',
            '可选择导出',
            '跨公众号多选',
            '导出含公众号名称列'
        ]
    })

if __name__ == '__main__':
    app.run(debug=True)