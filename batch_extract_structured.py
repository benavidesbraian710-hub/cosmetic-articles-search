#!/usr/bin/env python3
"""
批量提取文章结构化内容（宏观叙述 + 微观节点）
基于现有摘要，用 Kimi K3 提取结构化内容
"""

import sqlite3
import json
import os
import time
import requests
import sys
from datetime import datetime

# 强制刷新输出
sys.stdout.reconfigure(line_buffering=True)

DB_PATH = os.path.expanduser('~/.openclaw/workspace/cosmetic-deploy/cosmetic_articles.db')
KIMI_API_KEY = 'sk-kimi-KdTuRhVUWR5mJsyqgGSHRx31ALOaiVs4WjzvN9mzqFDXfy3Q4UA6Xfm7tXRgKvH3'
KIMI_API_URL = 'https://api.kimi.com/coding/v1/messages'

def call_kimi_api(prompt: str, timeout: int = 60) -> str:
    """调用 Kimi API（Anthropic 格式）"""
    headers = {
        'x-api-key': KIMI_API_KEY,
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': 'kimi-k3',
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 4096
    }
    
    try:
        # 手动 JSON 序列化并 UTF-8 编码
        import json as json_lib
        payload_json = json_lib.dumps(payload, ensure_ascii=False)
        payload_bytes = payload_json.encode('utf-8')
        
        response = requests.post(
            KIMI_API_URL, 
            headers=headers, 
            data=payload_bytes,
            timeout=timeout
        )
        response.raise_for_status()
        result = response.json()
        
        # 取 text 类型（最终输出）
        if 'content' in result:
            for item in result['content']:
                if item.get('type') == 'text':
                    return item.get('text', '')
            # 如果没有 text，取 thinking
            for item in result['content']:
                if item.get('type') == 'thinking':
                    return item.get('thinking', '')
        
        return ''
    except Exception as e:
        print(f"Kimi API 调用失败: {e}")
        return ''

def extract_structured_content(title: str, summary: str) -> dict:
    """提取结构化内容"""
    
    prompt = f"""请分析以下文章，提取结构化内容：

标题：{title}
摘要：{summary}

请输出以下JSON格式（不要其他内容）：
{{
  "macro_narrative": "文章总体叙述走向（宏观，如：从行业现状→技术突破→市场应用→未来趋势）",
  "micro_nodes": ["关键节点1", "关键节点2", "关键节点3", "关键节点4", "关键节点5"],
  "main_topic": "主要主题",
  "secondary_topics": ["次要主题1", "次要主题2"],
  "key_entities": ["核心实体1", "核心实体2", "核心实体3"]
}}

注意：
- macro_narrative：概括文章的整体脉络/主线/论述逻辑
- micro_nodes：文章中的具体关键节点/知识点/细节（5-10个）
- main_topic：文章主要讨论的主题
- secondary_topics：文章提到但不是主要讨论的主题（2-5个）
- key_entities：文章中的核心实体（品牌/成分/技术/机构等）"""

    text = call_kimi_api(prompt, timeout=90)
    
    if not text:
        return None
    
    # 提取 JSON
    import re
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except:
            return None
    
    return None

def main():
    """批量提取"""
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 检查是否有 structured_content 字段
    cursor.execute("PRAGMA table_info(articles)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'structured_content' not in columns:
        print("添加 structured_content 字段...")
        cursor.execute("ALTER TABLE articles ADD COLUMN structured_content TEXT")
        conn.commit()
    
    # 获取所有文章
    cursor.execute("SELECT id, title, summary FROM articles WHERE structured_content IS NULL OR structured_content = ''")
    articles = cursor.fetchall()
    
    total = len(articles)
    print(f"=== 开始批量提取 ===")
    print(f"总文章数: {total}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success_count = 0
    fail_count = 0
    
    for i, article in enumerate(articles, 1):
        article_id = article['id']
        title = article['title']
        summary = article['summary'] or ''
        
        print(f"[{i}/{total}] ID:{article_id} | {title[:50]}...")
        
        # 提取结构化内容
        structured = extract_structured_content(title, summary)
        
        if structured:
            # 存储到数据库
            cursor.execute(
                "UPDATE articles SET structured_content = ? WHERE id = ?",
                (json.dumps(structured, ensure_ascii=False), article_id)
            )
            conn.commit()
            success_count += 1
            print(f"  ✅ 成功 | 宏观: {structured.get('macro_narrative', '')[:50]}...")
        else:
            fail_count += 1
            print(f"  ❌ 失败")
        
        # 每 10 篇汇报一次
        if i % 10 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / i
            remaining = (total - i) * avg_time
            print(f"\n--- 进度: {i}/{total} ({i/total*100:.1f}%) | 成功: {success_count} | 失败: {fail_count} | 剩余: {remaining/60:.1f}分钟 ---\n")
        
        # 限速，避免 API 过载
        time.sleep(2)
    
    conn.close()
    
    print(f"\n=== 批量提取完成 ===")
    print(f"总文章数: {total}")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    start_time = time.time()
    main()