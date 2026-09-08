#!/usr/bin/env python3
"""
化妆品文章网站监控脚本
功能：检测网站可用性、数据完整性、数据新鲜度、数据质量
问题：通过企业微信Webhook发送告警
"""

import urllib.request
import json
import time
import os
import sys
from datetime import datetime, timedelta

# ===== 配置 =====
SITE_URL = "https://www.cosmetic-search.com"
CHECK_INTERVAL = 30 * 60  # 30分钟检查一次
TEAMS_WEBHOOK = None  # 企业微信Webhook地址，留空则只打印不发送

# 告警阈值
MIN_ARTICLES = 1600
MAX_ARTICLES = 2000
EXPECTED_SOURCES = 18
MAX_ARTICLE_AGE_DAYS = 7  # 最新文章不应超过7天

# 白名单公众号
WHITELISTED_SOURCES = {
    '亿邦动力', '个护前沿', '财经早餐', '化妆品观察 品观', '中国化妆品',
    'WWD 国际时尚特讯', 'Fbeauty未来迹', '妆研24小时', '肤见未来实验室',
    '化妆品财经在线', '非科学美妆传播', '铱星云商', 'Vogue Business',
    '妆合规', '原料合规观察', 'KEV美妆', '上海日化协会', '美业颜究院'
}

# ===== 工具函数 =====
def log(msg, level="INFO"):
    """日志输出"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def send_wechat_alert(title, content):
    """发送企业微信告警"""
    if not TEAMS_WEBHOOK:
        log("未配置企业微信Webhook，跳过通知", "WARN")
        return True
    
    try:
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"### 🚨 {title}\n\n{content}\n\n<font color='comment'>报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</font>"
            }
        }
        
        req = urllib.request.Request(
            TEAMS_WEBHOOK,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if result.get('errcode') == 0:
                log("企业微信告警发送成功", "INFO")
                return True
            else:
                log(f"企业微信告警发送失败: {result}", "ERROR")
                return False
    except Exception as e:
        log(f"企业微信告警发送异常: {e}", "ERROR")
        return False


def check_site_availability():
    """检查网站可用性"""
    try:
        start = time.time()
        req = urllib.request.Request(SITE_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed = (time.time() - start) * 1000
            status = resp.status
            if status == 200:
                log(f"✓ 网站可用 (HTTP {status}, 耗时 {elapsed:.0f}ms)", "INFO")
                return True, None
            else:
                msg = f"网站返回异常状态码: HTTP {status}"
                log(msg, "ERROR")
                return False, msg
    except urllib.error.HTTPError as e:
        msg = f"网站HTTP错误: {e.code} {e.reason}"
        log(msg, "ERROR")
        return False, msg
    except Exception as e:
        msg = f"网站不可达: {e}"
        log(msg, "ERROR")
        return False, msg


def fetch_data_json():
    """获取并解析data.json"""
    try:
        # 先获取articles.html确定当前数据版本
        req = urllib.request.Request(
            f"{SITE_URL}/articles.html",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8')
        
        import re
        match = re.search(r'data\.v(\d+)\.json', html)
        if not match:
            return None, "无法从页面提取数据版本号"
        
        version = match.group(1)
        data_url = f"{SITE_URL}/data.v{version}.json"
        log(f"当前数据版本: v{version}", "INFO")
        
        # 获取数据
        req = urllib.request.Request(
            data_url,
            headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            import gzip
            content = gzip.decompress(resp.read())
            data = json.loads(content.decode('utf-8'))
        
        return data, None
        
    except json.JSONDecodeError as e:
        return None, f"JSON解析失败: {e}"
    except Exception as e:
        return None, f"获取数据失败: {e}"


def check_data_integrity(data):
    """检查数据完整性"""
    issues = []
    
    # 检查stats
    stats = data.get('stats', {})
    total = stats.get('total_articles', 0)
    sources = stats.get('source_count', 0)
    
    log(f"数据统计: {total} 篇文章, {sources} 个公众号", "INFO")
    
    # 文章数量检查
    if total < MIN_ARTICLES:
        issues.append(f"文章数量过低: {total} < {MIN_ARTICLES}")
    elif total > MAX_ARTICLES:
        issues.append(f"文章数量异常高: {total} > {MAX_ARTICLES}")
    
    # 公众号数量检查
    if sources != EXPECTED_SOURCES:
        issues.append(f"公众号数量异常: {sources} ≠ {EXPECTED_SOURCES}")
    
    # 检查articles结构
    articles = data.get('articles', {})
    if not articles:
        issues.append("文章数据为空")
        return issues
    
    # 检查每个公众号是否在白名单
    invalid_sources = []
    for src in articles.keys():
        if src not in WHITELISTED_SOURCES:
            invalid_sources.append(src)
    
    if invalid_sources:
        issues.append(f"发现非白名单公众号: {', '.join(invalid_sources)}")
    
    # 检查wechat_name为空的文章
    empty_wechat_count = 0
    for src, arts in articles.items():
        if src == '' or src == '其他':
            empty_wechat_count += len(arts)
    
    if empty_wechat_count > 0:
        issues.append(f"发现 {empty_wechat_count} 篇文章wechat_name为空或为'其他'")
    
    return issues


def check_data_freshness(data):
    """检查数据新鲜度"""
    issues = []
    
    stats = data.get('stats', {})
    date_range = stats.get('date_range', {})
    latest = date_range.get('latest') or date_range.get('end')
    
    if latest:
        try:
            latest_date = datetime.strptime(latest[:10], '%Y-%m-%d')
            age = (datetime.now() - latest_date).days
            
            log(f"最新文章日期: {latest} (距今 {age} 天)", "INFO")
            
            if age > MAX_ARTICLE_AGE_DAYS:
                issues.append(f"数据过于陈旧: 最新文章日期为 {latest}，已超过 {MAX_ARTICLE_AGE_DAYS} 天")
        except Exception as e:
            issues.append(f"日期解析异常: {latest} - {e}")
    
    return issues


def run_health_check():
    """执行健康检查"""
    log("=" * 50, "INFO")
    log("开始网站健康检查", "INFO")
    
    all_issues = []
    
    # 1. 检查网站可用性
    ok, msg = check_site_availability()
    if not ok:
        all_issues.append(f"**网站不可用**: {msg}")
        send_wechat_alert("网站不可用", msg)
        return False
    
    # 2. 获取数据
    data, msg = fetch_data_json()
    if not data:
        all_issues.append(f"**数据获取失败**: {msg}")
        send_wechat_alert("数据获取失败", msg)
        return False
    
    # 3. 检查数据完整性
    integrity_issues = check_data_integrity(data)
    all_issues.extend(integrity_issues)
    
    # 4. 检查数据新鲜度
    freshness_issues = check_data_freshness(data)
    all_issues.extend(freshness_issues)
    
    # 5. 汇总结果
    if all_issues:
        log("=" * 50, "INFO")
        log("⚠️  发现以下问题:", "WARN")
        for issue in all_issues:
            log(f"  - {issue}", "WARN")
        
        content = "\n".join([f"- {issue}" for issue in all_issues])
        send_wechat_alert("网站数据异常", content)
        return False
    else:
        log("✓ 所有检查通过，数据正常", "INFO")
        return True


def main():
    """主函数"""
    log("化妆品文章网站监控脚本启动", "INFO")
    log(f"检查间隔: {CHECK_INTERVAL // 60} 分钟", "INFO")
    
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # 单次执行（用于测试）
        run_health_check()
    else:
        # 循环执行
        while True:
            run_health_check()
            log(f"等待 {CHECK_INTERVAL // 60} 分钟后进行下次检查...", "INFO")
            time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    main()
