#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重跑智能找文网站失败的文章摘要和关键词生成任务
- 从数据库读取缺少keywords的文章
- 实时抓取微信文章正文（urllib + 手机版微信UA）
- 通过openclaw agent CLI调用Kimi K3生成摘要和关键词
- 只更新数据库的summary和keywords字段
"""

import sqlite3
import urllib.request
import urllib.error
import json
import re
import time
import sys
import os
import ssl
import subprocess

# ============ 配置 ============
DB_PATH = "/Users/yuming.chen/.openclaw/workspace/cosmetic-deploy/cosmetic_articles.db"
LLM_MODEL = "kimi/kimi-k3"

# 手机版微信UA
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1 MicroMessenger/8.0.47"

BATCH_REPORT_INTERVAL = 10  # 每10篇汇报一次
FETCH_DELAY = 2  # 抓取间隔秒
LLM_DELAY = 2    # LLM调用间隔秒

# SSL上下文
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def fetch_wechat_article(url):
    """抓取微信文章正文 - 使用urllib + 手机版微信UA"""
    headers = {
        'User-Agent': MOBILE_UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://mp.weixin.qq.com/',
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        
        # 检查是否被拦截
        if '环境异常' in html or '访问过于频繁' in html or '操作频繁' in html:
            return None, "被微信拦截，需要验证"
        
        # 检查是否有正文区域
        if 'js_content' not in html:
            return None, "未找到正文区域(js_content)，可能被拦截或文章已删除"
        
        # 提取正文 - 微信文章正文在js_content div中
        content_match = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
        if not content_match:
            content_match = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>', html, re.DOTALL)
        
        if not content_match:
            return None, "正则提取正文失败"
        
        content_html = content_match.group(1)
        # 清理HTML标签
        content = re.sub(r'<script[^>]*>.*?</script>', '', content_html, flags=re.DOTALL)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'&nbsp;', ' ', content)
        content = re.sub(r'&[a-z]+;', ' ', content)
        content = re.sub(r'\s+', ' ', content).strip()
        # 清理微信特有的干扰文本
        content = re.sub(r'var\s+.*?=\s*.*?;', '', content)
        content = re.sub(r'function\s*\(\)\s*\{.*?\}', '', content)
        
        if len(content) < 50:
            return None, f"内容太短({len(content)}字)，可能抓取失败"
        
        # 截取前8000字（避免超出LLM上下文）
        return content[:8000], None
        
    except urllib.error.HTTPError as e:
        return None, f"HTTP错误: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return None, f"URL错误: {e.reason}"
    except Exception as e:
        return None, f"抓取异常: {str(e)}"


def call_kimi(title, content):
    """通过openclaw agent CLI调用Kimi K3生成摘要和关键词"""
    
    prompt = f"""请为以下化妆品行业文章生成摘要和关键词。

标题：{title}

正文内容：
{content}

请严格按以下格式输出（不要输出其他内容）：
【摘要】200-400字的文章摘要，概括核心内容和关键信息
【关键词】10-15个关键词，用逗号分隔，包括：核心成分/技术、品牌/公司、行业趋势、政策法规、产品类型等维度"""

    try:
        cmd = [
            "openclaw", "agent",
            "--local",
            "--agent", "main",
            "--model", LLM_MODEL,
            "--message", prompt,
            "--json",
            "--timeout", "120"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180  # 3分钟超时
        )
        
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "未知错误"
            return None, None, f"CLI调用失败(code={result.returncode}): {stderr[:200]}"
        
        # 解析JSON输出
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            return None, None, f"JSON解析失败: {e}, 输出: {result.stdout[:300]}"
        
        # 提取文本
        text = ""
        if 'payloads' in response:
            for p in response['payloads']:
                if p.get('text'):
                    text = p['text']
                    break
        elif 'result' in response and 'payloads' in response['result']:
            for p in response['result']['payloads']:
                if p.get('text'):
                    text = p['text']
                    break
        
        if not text:
            return None, None, f"未找到回复文本: {json.dumps(response, ensure_ascii=False)[:300]}"
        
        # 解析摘要
        summary_match = re.search(r'【摘要】\s*(.+?)(?=【关键词】|$)', text, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""
        
        # 解析关键词
        keywords_match = re.search(r'【关键词】\s*(.+?)$', text, re.DOTALL)
        keywords = keywords_match.group(1).strip() if keywords_match else ""
        
        # 清理关键词格式
        keywords = re.sub(r'[，、]', ',', keywords)
        keywords = re.sub(r'\s+', '', keywords)
        
        if not summary:
            return None, None, f"摘要解析失败，原始返回: {text[:300]}"
        
        return summary, keywords, None
            
    except subprocess.TimeoutExpired:
        return None, None, "CLI调用超时(180秒)"
    except Exception as e:
        return None, None, f"调用异常: {str(e)}"


def update_db(conn, article_id, summary, keywords):
    """只更新摘要和关键词，不存全文"""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE articles SET summary = ?, keywords = ? WHERE id = ?",
        (summary, keywords, article_id)
    )
    conn.commit()


def get_pending_articles(conn):
    """获取待处理文章"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, url FROM articles WHERE keywords IS NULL OR keywords = '' ORDER BY id"
    )
    return cursor.fetchall()


def main():
    print("=" * 60)
    print("智能找文 - 摘要和关键词重跑任务")
    print("流程: 按链接实时抓取全文 → Kimi K3生成摘要/关键词 → 只存摘要和关键词")
    print("=" * 60)
    
    print(f"\n🤖 模型: {LLM_MODEL}")
    print(f"📂 数据库: {DB_PATH}")
    
    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    articles = get_pending_articles(conn)
    total = len(articles)
    
    print(f"📊 待处理文章: {total} 篇")
    print("-" * 60)
    
    if total == 0:
        print("✅ 所有文章都已有摘要和关键词，无需处理")
        conn.close()
        return
    
    # 统计
    success_count = 0
    fetch_fail_count = 0
    llm_fail_count = 0
    errors = []
    
    start_time = time.time()
    
    for idx, (article_id, title, url) in enumerate(articles, 1):
        print(f"\n[{idx}/{total}] ID={article_id}")
        print(f"  标题: {title[:60]}")
        
        # Step 1: 抓取文章
        print(f"  ⏳ 抓取文章...", end=" ", flush=True)
        content, fetch_err = fetch_wechat_article(url)
        
        if fetch_err:
            print(f"❌ {fetch_err}")
            fetch_fail_count += 1
            errors.append({"id": article_id, "title": title, "stage": "fetch", "error": fetch_err})
            time.sleep(FETCH_DELAY)
            continue
        
        print(f"✅ 获取 {len(content)} 字")
        time.sleep(FETCH_DELAY)
        
        # Step 2: 调用LLM
        print(f"  ⏳ 生成摘要和关键词...", end=" ", flush=True)
        summary, keywords, llm_err = call_kimi(title, content)
        
        if llm_err:
            print(f"❌ {llm_err}")
            llm_fail_count += 1
            errors.append({"id": article_id, "title": title, "stage": "llm", "error": llm_err})
            time.sleep(LLM_DELAY)
            continue
        
        # Step 3: 更新数据库
        update_db(conn, article_id, summary, keywords)
        success_count += 1
        kw_preview = keywords[:80] if keywords else "(无)"
        print(f"✅ 摘要 {len(summary)} 字 | 关键词: {kw_preview}")
        
        time.sleep(LLM_DELAY)
        
        # 每10篇汇报
        if idx % BATCH_REPORT_INTERVAL == 0:
            elapsed = time.time() - start_time
            speed = idx / elapsed * 60 if elapsed > 0 else 0
            remaining = (total - idx) / (idx / elapsed) if idx > 0 and elapsed > 0 else 0
            print(f"\n{'='*60}")
            print(f"📊 进度报告 [{idx}/{total}] ({idx/total*100:.0f}%)")
            print(f"  ✅ 成功: {success_count} | ❌ 抓取失败: {fetch_fail_count} | ❌ LLM失败: {llm_fail_count}")
            print(f"  ⏱️ 已用时: {elapsed/60:.1f}分钟 | 速度: {speed:.1f}篇/分钟 | 预计剩余: {remaining/60:.1f}分钟")
            print(f"{'='*60}")
    
    # 最终报告
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"🏁 任务完成!")
    print(f"  总文章: {total}")
    print(f"  ✅ 成功: {success_count}")
    print(f"  ❌ 抓取失败: {fetch_fail_count}")
    print(f"  ❌ LLM失败: {llm_fail_count}")
    print(f"  ⏱️ 总用时: {elapsed/60:.1f} 分钟")
    
    if errors:
        print(f"\n📋 失败记录 ({len(errors)} 条):")
        for err in errors:
            print(f"  - ID={err['id']} [{err['stage']}] {err['title'][:40]}: {err['error'][:60]}")
    
    print(f"{'='*60}")
    
    conn.close()


if __name__ == "__main__":
    main()
