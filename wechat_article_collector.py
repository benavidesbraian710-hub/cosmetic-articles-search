#!/usr/bin/env python3
"""
微信公众号文章链接采集器

用法:
    python3 collect.py '<JSON配置>'
    
示例:
    python3 collect.py '{"tasks":[{"account":"新智元","count":3}]}'
"""

import subprocess
import time
import json
import sys
import re
from datetime import datetime
from pathlib import Path


# ==================== 坐标配置 ====================

COORDS = {
    'public_account_tab': (579, 303),    # 公众号标签
    'search_icon': (933, 109),            # 搜索图标
    'publish_time': (891, 178),           # 指定发布时间
    'confirm': (898, 314),                # 确定按钮
    'sort': (891, 184),                   # 综合排序
    'latest': (1021, 239),                # 最新发布
    'keyword_search': (672, 117),         # 搜索框
    'more_btn': (1325, 51),               # 右上角"···"
    'copy_link': (1210, 118),             # 复制链接
    'close_article': (1099, 51),          # 关闭文章页
    'close_search': (459, 50),            # 关闭搜索窗口
    'close_account': (527, 55),           # 关闭账号窗口
}

ARTICLE_COORDS = [
    (902, 349),   # 第1篇
    (902, 476),   # 第2篇
    (902, 600),   # 第3篇
    (902, 729),   # 第4篇
]


# ==================== 工具函数 ====================

def click(x: int, y: int) -> bool:
    """屏幕绝对坐标点击"""
    cmd = f'peekaboo click --coords {x},{y} --global-coords'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0


def hotkey(keys: str) -> bool:
    """发送快捷键"""
    for app in ["微信", "WeChat"]:
        cmd = f'peekaboo hotkey --keys "{keys}" --app "{app}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return True
    cmd = f'peekaboo hotkey --keys "{keys}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0


def press(key: str) -> bool:
    """发送按键"""
    for app in ["微信", "WeChat"]:
        cmd = f'peekaboo press {key} --app "{app}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return True
    cmd = f'peekaboo press {key}'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0


def set_clipboard(text: str):
    """设置剪贴板"""
    subprocess.run('pbcopy', input=text.encode('utf-8'))
    time.sleep(0.2)


def get_clipboard() -> str:
    """获取剪贴板内容"""
    result = subprocess.run('pbpaste', capture_output=True, text=True)
    return result.stdout.strip()


def activate_wechat():
    """激活微信窗口"""
    subprocess.run(['open', '-a', 'WeChat'])
    time.sleep(1)


# ==================== 核心流程 ====================

def navigate_to_account(account_name: str):
    """导航到公众号账号界面（含预处理：如果已预先打开过，搜索后直接显示公众号，无需点击'账号'标签）"""
    print(f"\n=== 搜索公众号: {account_name} ===")
    
    activate_wechat()
    
    print("打开搜索框...")
    hotkey("cmd,f")
    time.sleep(1.0)
    
    print(f"粘贴'{account_name}'...")
    set_clipboard(account_name)
    hotkey("cmd,v")
    time.sleep(1.0)
    
    print("回车搜索...")
    press("return")
    time.sleep(2.5)
    
    print("尝试点击'公众号'标签...")
    x, y = COORDS['public_account_tab']
    clicked = click(x, y)
    time.sleep(1.5)
    
    print("✅ 进入账号界面")


def setup_filters():
    """设置筛选条件：指定发布时间 + 最新发布"""
    print("\n=== 设置筛选条件 ===")
    
    print("点击搜索图标...")
    click(*COORDS['search_icon'])
    time.sleep(1.0)
    
    print("点击'指定发布时间'...")
    click(*COORDS['publish_time'])
    time.sleep(0.8)
    
    print("点击'确定'...")
    click(*COORDS['confirm'])
    time.sleep(2.5)  # 等待筛选界面加载
    
    print("点击'综合排序'...")
    click(*COORDS['sort'])
    time.sleep(1.0)
    
    print("点击'最新发布'...")
    click(*COORDS['latest'])
    time.sleep(2.5)
    
    print("✅ 筛选完成")


def search_keyword(keyword: str):
    """关键词搜索"""
    print(f"\n=== 搜索关键词: {keyword} ===")
    
    print("点击搜索框...")
    click(*COORDS['keyword_search'])
    time.sleep(0.8)
    
    print(f"粘贴关键词...")
    set_clipboard(keyword)
    hotkey("cmd,v")
    time.sleep(0.8)
    
    print("回车搜索...")
    press("return")
    time.sleep(2.5)
    
    print("✅ 关键词搜索完成")


def get_article(index: int) -> str:
    """获取单篇文章链接"""
    if index >= len(ARTICLE_COORDS):
        print(f"❌ 文章序号{index+1}超出范围")
        return ""
    
    x, y = ARTICLE_COORDS[index]
    print(f"\n--- 获取第 {index+1} 篇文章 ({x}, {y}) ---")
    
    print("点击文章...")
    click(x, y)
    time.sleep(3.5)  # 等待文章页面加载
    
    print("点击'···'菜单...")
    click(*COORDS['more_btn'])
    time.sleep(2.0)
    
    print("点击'复制链接'...")
    click(*COORDS['copy_link'])
    time.sleep(1.0)
    
    link = get_clipboard()
    
    print("关闭文章页...")
    click(*COORDS['close_article'])
    time.sleep(3.5)  # 等待列表刷新稳定
    
    print(f"✅ 链接: {link}")
    return link
    
    # 验证链接是否有效
    if not link.startswith('http'):
        print(f"⚠️  剪贴板内容无效: {link}")
        print("尝试再次获取...")
        time.sleep(1.0)
        link = get_clipboard()
    
    if not link.startswith('http'):
        print(f"❌ 无法获取有效链接")
        link = ""
    
    print("关闭文章页...")
    click(*COORDS['close_article'])
    time.sleep(3)  # 等待列表刷新稳定
    
    print(f"✅ 链接: {link}")
    return link


def close_windows():
    """关闭搜索窗口和账号窗口"""
    print("\n=== 关闭窗口 ===")
    
    print("关闭搜索窗口...")
    click(*COORDS['close_search'])
    time.sleep(0.5)
    
    print("关闭账号窗口...")
    click(*COORDS['close_account'])
    time.sleep(0.5)
    
    print("✅ 窗口已关闭")


# ==================== 任务执行 ====================

def execute_task(task: dict) -> list:
    """
    执行单个任务
    
    Args:
        task: {
            "account": "公众号名称",
            "keyword": "关键词（可选）",
            "count": 获取数量
        }
    
    Returns:
        文章链接列表
    """
    account = task['account']
    keyword = task.get('keyword', '')
    count = task.get('count', 1)
    
    # 1. 导航到公众号
    navigate_to_account(account)
    
    # 2. 设置筛选
    setup_filters()
    
    # 3. 关键词搜索（如果有）
    if keyword:
        search_keyword(keyword)
    
    # 4. 获取文章
    links = []
    for i in range(count):
        link = get_article(i)
        if link:
            links.append({
                'account': account,
                'keyword': keyword,
                'index': i + 1,
                'link': link,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
    
    # 5. 关闭窗口
    close_windows()
    
    return links


# ==================== CSV 导出 ====================

def export_csv(results: list, output_path: str = None):
    """导出结果到 CSV"""
    import csv
    
    if not output_path:
        desktop = Path.home() / 'Desktop'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = desktop / f'wechat_articles_{timestamp}.csv'
    
    # 表头
    headers = ['公众号', '关键词', '序号', '链接', '采集时间']
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for item in results:
            writer.writerow([
                item['account'],
                item['keyword'] or '-',
                item['index'],
                item['link'],
                item['time']
            ])
    
    print(f"\n✅ CSV 已保存: {output_path}")
    return output_path


# ==================== 自然语言解析 ====================

def parse_natural_language(text: str) -> list:
    """
    解析自然语言为任务列表
    
    支持格式:
    - "获取新智元最新3篇文章"
    - "搜索新智元关于openclaw的2篇文章"
    - "获取原料合规观察的1篇文章"
    - "先获取新智元5篇，再获取原料合规观察3篇"
    """
    tasks = []
    
    # 模式1: 获取/搜索 + 公众号 + 关键词 + 数量
    pattern1 = r'(?:获取|搜索)\s*([^\s]+)\s*(?:关于|搜索)?\s*([^\d\s]*)\s*(?:的)?\s*(\d*)\s*篇'
    matches = re.findall(pattern1, text)
    
    for account, keyword, count in matches:
        task = {
            'account': account.strip(),
            'keyword': keyword.strip() or '',
            'count': int(count) if count.strip() else 1
        }
        tasks.append(task)
    
    # 模式2: 先获取...再获取...
    pattern2 = r'先获取([^\d]+)(\d*)篇.*再获取([^\d]+)(\d*)篇'
    matches = re.findall(pattern2, text)
    
    for account1, count1, account2, count2 in matches:
        tasks.append({
            'account': account1.strip(),
            'keyword': '',
            'count': int(count1) if count1 else 1
        })
        tasks.append({
            'account': account2.strip(),
            'keyword': '',
            'count': int(count2) if count2 else 1
        })
    
    return tasks


# ==================== 主函数 ====================

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print(f"  python3 {sys.argv[0]} '<JSON配置>'")
        print(f"  python3 {sys.argv[0]} '获取新智元最新3篇文章'")
        print()
        print("示例 JSON:")
        print('  \'{"tasks":[{"account":"新智元","count":3}]}\'')
        sys.exit(1)
    
    input_text = sys.argv[1]
    
    # 尝试解析 JSON
    try:
        config = json.loads(input_text)
        tasks = config.get('tasks', [])
    except json.JSONDecodeError:
        # 尝试自然语言解析
        tasks = parse_natural_language(input_text)
    
    if not tasks:
        print("❌ 无法解析输入，请检查格式")
        sys.exit(1)
    
    print("=" * 50)
    print("微信公众号文章采集")
    print("=" * 50)
    print(f"\n共 {len(tasks)} 个任务:")
    for i, task in enumerate(tasks, 1):
        keyword = task.get('keyword', '')
        keyword_str = f" 关键词:{keyword}" if keyword else ''
        print(f"  {i}. {task['account']}  {task['count']}篇{keyword_str}")
    
    # 执行所有任务
    all_results = []
    for task in tasks:
        results = execute_task(task)
        all_results.extend(results)
    
    # 导出 CSV
    print("\n" + "=" * 50)
    print("导出 CSV...")
    output_path = export_csv(all_results)
    
    print("\n" + "=" * 50)
    print(f"✅ 完成！共获取 {len(all_results)} 篇文章")
    print(f"📁 CSV: {output_path}")


if __name__ == "__main__":
    main()
