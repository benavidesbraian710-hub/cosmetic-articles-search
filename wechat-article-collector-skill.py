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
# 屏幕绝对坐标（基于固定窗口位置）
# 已根据 1600x900 分辨率调整（2026-06-18更新）

# 前置流程：搜索公众号并进入账号界面
COORD_SEARCH_BOX = (933, 109)      # 搜索图标
COORD_PUBLISH_TIME = (891, 178)    # "指定发布时间"（标准位置）
COORD_PUBLISH_TIME_ALT = (891, 194) # "指定发布时间"（备选位置，向下偏移16px）
COORD_CONFIRM = (898, 314)         # "确定"按钮（标准位置）
COORD_CONFIRM_ALT = (898, 330)      # "确定"按钮（备选位置，向下偏移16px）
COORD_SORT = (891, 184)            # "综合排序"
COORD_LATEST = (1021, 239)         # "最新发布"

# 需要备选坐标的公众号列表（这些公众号的UI布局不同）
# 备选坐标：publish_time (891, 194), confirm (898, 330)
# 文章坐标向下偏移16px
ALT_COORDS_ACCOUNTS = ['非科学美妆传播', 'Fbeauty未来迹', '肤见未来实验室', '美妆内行人', 'Beauty Insider', '化妆品观察 品观']

# 搜索框（关键词搜索用）
COORD_KEYWORD_SEARCH = (672, 117)  # 搜索框

# 文章列表（标准位置）
ARTICLE_COORDS = [
    (902, 349),   # 第1篇
    (902, 476),   # 第2篇
    (902, 600),   # 第3篇
    (902, 729),   # 第4篇
    (869, 834),   # 第5篇
]

# 文章列表（备选位置，向下偏移16px）
ARTICLE_COORDS_ALT = [
    (902, 365),   # 第1篇
    (902, 492),   # 第2篇
    (902, 616),   # 第3篇
    (902, 745),   # 第4篇
    (869, 850),   # 第5篇
]

# 文章详情页操作
COORD_MORE_BTN = (1325, 51)        # 右上角"···"
COORD_COPY_LINK = (1210, 118)      # 复制链接（标准）
COORD_COPY_LINK_ALT = (1210, 134)  # 复制链接（备选，向下偏移16px）
COORD_CLOSE_ARTICLE = (1099, 51)   # 关闭文章页

COORDS = {
    'public_account_tab': (579, 303),    # 公众号标签
    'search_icon': (933, 109),            # 搜索图标
    'publish_time': (891, 178),           # 指定发布时间（标准）
    'publish_time_alt': (891, 194),       # 指定发布时间（备选）
    'confirm': (898, 314),                # 确定按钮（标准）
    'confirm_alt': (898, 330),            # 确定按钮（备选）
    'sort': (891, 184),                   # 综合排序
    'latest': (1021, 239),                # 最新发布
    'keyword_search': (672, 117),         # 搜索框
    'more_btn': (1325, 51),               # 右上角"···"
    'copy_link': (1210, 118),             # 复制链接（标准）
    'copy_link_alt': (1210, 134),         # 复制链接（备选）
    'close_article': (1099, 51),          # 关闭文章页
    'close_search': (459, 50),            # 关闭搜索窗口
    'close_account': (527, 54),           # 关闭账号窗口
}


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
    """激活微信窗口到最前台"""
    # 不激活微信，假设已手动启动
    time.sleep(1)
    print("  ✅ 微信已准备")
    
    time.sleep(0.5)


# ==================== 核心流程 ====================

def navigate_to_account(account_name: str):
    """导航到公众号账号界面"""
    print(f"\n=== 搜索公众号: {account_name} ===")
    
    activate_wechat()
    
    # 按ESC键关闭可能残留的窗口（2026-06-12修复）
    print("按ESC键关闭残留窗口...")
    press("esc")
    time.sleep(0.5)
    
    print("打开搜索框...")
    hotkey("cmd,f")
    time.sleep(0.5)
    
    print(f"粘贴'{account_name}'...")
    set_clipboard(account_name)
    hotkey("cmd,v")
    time.sleep(0.5)
    
    print("回车搜索...")
    press("return")
    time.sleep(2)
    
    print("尝试点击'公众号'标签...")
    x, y = COORDS['public_account_tab']
    click(x, y)
    time.sleep(1)
    
    print("✅ 进入账号界面")


def setup_filters(account_name: str = ""):
    """设置筛选条件：指定发布时间 + 最新发布"""
    print("\n=== 设置筛选条件 ===")
    
    # 判断使用标准坐标还是备选坐标
    use_alt = account_name in ALT_COORDS_ACCOUNTS
    publish_time_coord = COORDS['publish_time_alt'] if use_alt else COORDS['publish_time']
    confirm_coord = COORDS['confirm_alt'] if use_alt else COORDS['confirm']
    
    if use_alt:
        print(f"  使用备选坐标（{account_name} 的UI布局不同）")
    
    print("点击搜索图标...")
    click(*COORDS['search_icon'])
    time.sleep(0.5)
    
    print("点击'指定发布时间'...")
    click(*publish_time_coord)
    time.sleep(0.3)
    
    print("点击'确定'...")
    click(*confirm_coord)
    time.sleep(3)  # 等待筛选界面加载（2026-06-09修复：2秒→3秒）
    
    print("点击'综合排序'...")
    click(*COORDS['sort'])
    time.sleep(0.5)
    
    print("点击'最新发布'...")
    click(*COORDS['latest'])
    time.sleep(2)
    
    print("✅ 筛选完成")


def search_keyword(keyword: str):
    """关键词搜索"""
    print(f"\n=== 搜索关键词: {keyword} ===")
    
    print("点击搜索框...")
    click(*COORDS['keyword_search'])
    time.sleep(0.3)
    
    print(f"粘贴关键词...")
    set_clipboard(keyword)
    hotkey("cmd,v")
    time.sleep(0.3)
    
    print("回车搜索...")
    press("return")
    time.sleep(2)
    
    print("✅ 关键词搜索完成")


def get_article(index: int, account_name: str = "") -> str:
    """获取单篇文章链接"""
    # 根据公众号选择正确的文章坐标
    use_alt = account_name in ALT_COORDS_ACCOUNTS
    article_coords = ARTICLE_COORDS_ALT if use_alt else ARTICLE_COORDS
    
    if index >= len(article_coords):
        print(f"❌ 文章序号{index+1}超出范围")
        return ""
    
    x, y = article_coords[index]
    print(f"\n--- 获取第 {index+1} 篇文章 ({x}, {y}) ---")
    
    print("点击文章...")
    click(x, y)
    time.sleep(3)  # 等待文章页面加载
    
    print("点击'···'菜单...")
    click(*COORDS['more_btn'])
    time.sleep(1.5)
    
    print("点击'复制链接'...")
    
    # 重试机制：最多尝试3次，每次尝试不同的坐标
    link = ""
    copy_coords = [
        COORDS['copy_link'],      # 标准坐标
        COORDS['copy_link_alt'],  # 备选坐标1
        (1210, 150),              # 备选坐标2
    ]
    
    for attempt in range(3):
        # 选择坐标
        coord = copy_coords[attempt % len(copy_coords)]
        print(f"  尝试坐标: {coord}")
        click(*coord)
        time.sleep(1.5)
        
        link = get_clipboard()
        
        # 验证链接是否有效
        if link and link.startswith('http'):
            print(f"  ✅ 成功获取链接 (尝试{attempt+1})")
            break
        else:
            print(f"  ⚠️  剪贴板内容无效: '{link[:50]}...' (尝试{attempt+1}/3)")
            if attempt < 2:
                print("  等待后重试...")
                time.sleep(2)
    
    if not link or not link.startswith('http'):
        print(f"  ❌ 无法获取链接，跳过此文章")
        # 关闭文章页
        click(*COORDS['close_article'])
        time.sleep(3)
        return ""
    
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
    setup_filters(account)
    
    # 3. 关键词搜索（如果有）
    if keyword:
        search_keyword(keyword)
    
    # 4. 获取文章
    links = []
    for i in range(count):
        link = get_article(i, account)
        if link and link.startswith('http'):
            links.append({
                'account': account,
                'keyword': keyword,
                'index': i + 1,
                'link': link,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            print(f"⚠️  第 {i+1} 篇文章链接获取失败，跳过")
    
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
    
    # 模式1: 获取/搜索 + 公众号 + 最新/的 + 数量
    # 匹配: "获取妆合规最新4篇文章" 或 "获取妆合规的4篇文章"
    pattern1 = r'(?:获取|搜索)\s*(.+?)(?:最新|的)?\s*(\d+)\s*篇'
    matches = re.findall(pattern1, text)
    
    for account, count in matches:
        # 清理公众号名称
        account = account.strip()
        # 移除可能的"最新"残留
        account = re.sub(r'最新\d+.*$', '', account).strip()
        
        task = {
            'account': account,
            'keyword': '',
            'count': int(count) if count.strip() else 1
        }
        tasks.append(task)
    
    # 模式2: 先获取...再获取...
    pattern2 = r'先获取(.+?)(?:最新|的)?\s*(\d*)篇.*再获取(.+?)(?:最新|的)?\s*(\d*)篇'
    matches = re.findall(pattern2, text)
    
    for account1, count1, account2, count2 in matches:
        # 清理公众号名称
        account1 = re.sub(r'最新\d+.*$', '', account1.strip()).strip()
        account2 = re.sub(r'最新\d+.*$', '', account2.strip()).strip()
        
        tasks.append({
            'account': account1,
            'keyword': '',
            'count': int(count1) if count1 else 1
        })
        tasks.append({
            'account': account2,
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
        skip_csv = config.get('skip_csv', False)  # 是否跳过CSV导出
    except json.JSONDecodeError:
        # 尝试自然语言解析
        tasks = parse_natural_language(input_text)
        skip_csv = False
    
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
    
    # 执行所有任务（批量采集）
    all_results = {}
    for i, task in enumerate(tasks):
        account = task['account']
        count = task['count']
        
        print(f"\n{'='*50}")
        print(f"[{i+1}/{len(tasks)}] 采集: {account} ({count}篇)")
        print(f"{'='*50}")
        
        # 激活微信
        activate_wechat()
        
        # 搜索并进入公众号
        if not navigate_to_account(account):
            print(f"❌ 搜索失败: {account}")
            all_results[account] = []
            continue
        
        # 获取文章链接
        links = get_article_links(count)
        all_results[account] = links
        
        print(f"✅ 完成: {account} - 获取 {len(links)} 个链接")
        for link in links:
            print(f"  ✅ 链接: {link}")
        
        # 关闭当前公众号窗口，准备下一个
        if i < len(tasks) - 1:
            close_account_page()
            time.sleep(1)
    
    # 导出 CSV（除非 skip_csv=True）
    if not skip_csv:
        print("\n" + "=" * 50)
        print("导出 CSV...")
        
        # 转换为旧格式
        all_results_list = []
        for account, links in all_results.items():
            for link in links:
                all_results_list.append({
                    'account': account,
                    'link': link,
                    'title': '',
                    'publish_date': ''
                })
        
        output_path = export_csv(all_results_list)
        
        print("\n" + "=" * 50)
        print(f"✅ 完成！共获取 {len(all_results_list)} 篇文章")
        print(f"📁 CSV: {output_path}")
    else:
        # 只输出链接，不导出CSV
        print("\n" + "=" * 50)
        print("📊 批量采集完成")
        print("=" * 50)
        for account, links in all_results.items():
            print(f"\n{account}: {len(links)} 篇")
            for link in links:
                print(f"  ✅ 链接: {link}")
        
        # 输出JSON格式结果
        print(f"\n📋 JSON结果:")
        print(json.dumps(all_results, ensure_ascii=False, indent=2))
        print(f"✅ 完成！共获取 {len(all_results)} 篇文章")
        for item in all_results:
            print(f"✅ 链接: {item['link']}")
        print("📁 跳过CSV导出（skip_csv=True）")


if __name__ == "__main__":
    main()
