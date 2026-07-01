# 化妆品文章检索系统 - 项目文档

**文档版本**: v1.2
**创建时间**: 2026-06-29 12:13
**最后更新**: 2026-07-01 12:24
**项目负责人**: Nick
**技术实现**: 搜搜 (Sōusou) - AI搜索猎犬

**当前版本**: Basic版本（V1）
**目标版本**: V3（详见产品设计方案）

---

## 一、项目概述

**项目名称**: 化妆品文章检索系统
**当前版本**: Basic版本（V1）
**网站地址**: https://www.cosmetic-search.com/
**GitHub仓库**: https://github.com/benavidesbraian710-hub/cosmetic-articles-search
**部署方式**: GitHub Pages 静态托管

**系统定位**: 
- **Basic版本（当前）**: 7×24小时监控化妆品行业公众号，自动采集文章，提供浏览和导出功能
- **V3版本（规划）**: 智能检索系统，支持关键词搜索、LLM摘要、智能排序

**项目路径**: ~/.openclaw/workspace/cosmetic-deploy/
**数据库路径**: ~/.openclaw/cosmetic_articles.db
**当前数据量**: 190篇文章，15个公众号
**数据范围**: 从发布时间开始至今的所有文章
**最后更新时间**: 2026-06-29 12:08

**版本演进计划**:
- V1（Basic）: 当前版本，支持浏览和导出
- V2（增强）: 添加检索功能、文章正文、LLM摘要
- V3（智能）: 智能检索、个性化推荐、多维度分析（详见产品设计方案）

---

## 二、版本说明

### Basic版本（V1）- 当前

**功能**:
- ✅ 公众号文章自动采集
- ✅ 文章浏览（按公众号分类）
- ✅ 文章勾选导出CSV
- ✅ 去重机制（URL唯一约束）

**限制**:
- ❌ 无搜索功能
- ❌ 无文章正文
- ❌ 无LLM摘要
- ❌ 无关键词提取
- ❌ 无智能排序

### V3版本（规划）

**文档**: ~/.openclaw/workspace/化妆品文章检索系统_产品设计方案_v1.2.md

**核心功能**:
1. 智能检索引擎（关键词召回 + LLM精排）
2. 文章摘要生成（LLM生成150-250字）
3. 关键词提取（8-15个关键词）
4. 多维度排序（时间、相关性、热度）
5. 个性化推荐
6. 高级筛选（公众号、时间范围、关键词）

**技术架构**:
- 后端: Flask + SQLite + FTS5
- 前端: React/Vue（待定）
- AI: LLM API（摘要、关键词、精排）
- 部署: 云服务器（待定）

---

## 三、系统架构（Basic版本）

```
┌─────────────────────────────────────────────────────────────────────┐
│                    化妆品文章检索系统 - Basic版本                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  【前端】GitHub Pages 静态网站                                       │
│  ├── 仓库: benavidesbraian710-hub/cosmetic-articles-search          │
│  ├── 文件: index.html + data.json (纯静态)                          │
│  ├── 功能: 左侧公众号列表 → 右侧文章表格 → 勾选导出CSV               │
│  └── 域名: cosmetic-search.com (已配置)                             │
│                                                                     │
│  【数据库】SQLite                                                    │
│  ├── 路径: ~/.openclaw/cosmetic_articles.db                          │
│  ├── 表结构: articles (id, wechat_name, title, url, publish_date)  │
│  └── 当前数据: 190篇文章，15个公众号                                  │
│                                                                     │
│  【采集层】坐标点击自动化 (wechat-article-collector skill)           │
│  ├── 工具: peekaboo (Mac屏幕坐标点击)                                │
│  ├── 路径: ~/.openclaw/workspace/wechat-collector/...              │
│  └── 输出: ~/Desktop/wechat_articles_YYYYMMDD_HHMMSS.csv            │
│                                                                     │
│  【入库脚本】collect_from_csv.py                                     │
│  ├── 路径: ~/.openclaw/workspace/cosmetic-deploy/                   │
│  ├── 功能: 读取CSV → 抓取文章信息 → 入库                            │
│  └── 去重: URL唯一约束，重复自动跳过                                 │
│                                                                     │
│  【导出脚本】export_data.py                                          │
│  ├── 路径: ~/.openclaw/workspace/cosmetic-deploy/                   │
│  └── 功能: 数据库 → data.json (GitHub Pages数据源)                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    化妆品文章检索系统                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  【前端】GitHub Pages 静态网站                                       │
│  ├── 仓库: benavidesbraian710-hub/cosmetic-articles-search          │
│  ├── 文件: index.html + data.json (纯静态)                          │
│  ├── 功能: 左侧公众号列表 → 右侧文章表格 → 勾选导出CSV               │
│  └── 域名: cosmetic-search.com (已配置)                             │
│                                                                     │
│  【数据库】SQLite                                                    │
│  ├── 路径: ~/.openclaw/cosmetic_articles.db                          │
│  ├── 表结构: articles (id, wechat_name, title, url, publish_date)  │
│  └── 当前数据: 190篇文章，15个公众号                                  │
│                                                                     │
│  【采集层】坐标点击自动化 (wechat-article-collector skill)           │
│  ├── 工具: peekaboo (Mac屏幕坐标点击)                                │
│  ├── 路径: ~/.openclaw/workspace/wechat-collector/...              │
│  └── 输出: ~/Desktop/wechat_articles_YYYYMMDD_HHMMSS.csv            │
│                                                                     │
│  【入库脚本】collect_from_csv.py                                     │
│  ├── 路径: ~/.openclaw/workspace/cosmetic-deploy/                   │
│  ├── 功能: 读取CSV → 抓取文章信息 → 入库                            │
│  └── 去重: URL唯一约束，重复自动跳过                                 │
│                                                                     │
│  【导出脚本】export_data.py                                          │
│  ├── 路径: ~/.openclaw/workspace/cosmetic-deploy/                   │
│  └── 功能: 数据库 → data.json (GitHub Pages数据源)                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 文件清单

### 核心文件（Basic版本）

| 文件 | 路径 | 说明 | 版本 |
|------|------|------|------|
| index.html | ~/.openclaw/workspace/cosmetic-deploy/index.html | 网站前端 | V1 |
| data.json | ~/.openclaw/workspace/cosmetic-deploy/data.json | 网站数据源 | V1 |
| export_data.py | ~/.openclaw/workspace/cosmetic-deploy/export_data.py | 导出数据库到JSON | V1 |
| collect_from_csv.py | ~/.openclaw/workspace/cosmetic-deploy/collect_from_csv.py | CSV入库脚本 | V1 |
| update.sh | ~/.openclaw/workspace/cosmetic-deploy/update.sh | 更新网站脚本 | V1 |
| auto_collect.py | ~/.openclaw/workspace/cosmetic-deploy/auto_collect.py | 自动采集+入库+推送 | V1 |
| auto_collect_all.py | ~/.openclaw/workspace/cosmetic-deploy/auto_collect_all.py | 全量自动采集 | V1 |
| PROJECT.md | ~/.openclaw/workspace/cosmetic-deploy/PROJECT.md | 项目文档 | V1 |

### 采集器文件

| 文件 | 路径 | 说明 | 版本 |
|------|------|------|------|
| collect.py | ~/.openclaw/workspace/wechat-collector/skills/wechat-article-collector/scripts/collect.py | 坐标点击采集器 | V1 |
| collect_relative.py | ~/.openclaw/workspace/wechat-collector/skills/wechat-article-collector/scripts/collect_relative.py | 相对坐标采集器(备用) | V1 |
| test_debug.py | ~/.openclaw/workspace/wechat-collector/skills/wechat-article-collector/scripts/test_debug.py | 调试脚本 | V1 |

### 产品设计方案

| 文件 | 路径 | 说明 | 版本 |
|------|------|------|------|
| 化妆品文章检索系统_产品设计方案_v1.2.md | ~/.openclaw/workspace/化妆品文章检索系统_产品设计方案_v1.2.md | V3版本产品设计方案 | V3 |

### 历史文件

| 文件 | 路径 | 说明 | 状态 |
|------|------|------|------|
| fix_all_times.py | ~/.openclaw/workspace/cosmetic-deploy/ | 修复发布时间脚本 | 历史 |
| collect_from_wechat_mac.py | ~/.openclaw/workspace/cosmetic-deploy/ | 旧版采集脚本 | 历史 |
| collect_and_save.py | ~/.openclaw/workspace/cosmetic-deploy/ | 旧版采集+入库 | 历史 |
| wechat_article_collector.py | ~/.openclaw/workspace/wechat-auto/ | 历史坐标版本 | 历史 |
| test_click.py | ~/.openclaw/workspace/wechat-auto/ | 历史测试脚本 | 历史 |
| test_full_workflow.py | ~/.openclaw/workspace/wechat-auto/ | 历史测试脚本 | 历史 |
| test_click_search_abs.py | ~/.openclaw/workspace/wechat-auto/ | 历史测试脚本 | 历史 |

---

## 数据库结构

### articles 表

```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wechat_name TEXT NOT NULL,      -- 公众号名称
    title TEXT NOT NULL,            -- 文章标题
    url TEXT UNIQUE NOT NULL,       -- 文章链接（唯一约束，自动去重）
    publish_date TEXT,              -- 发布时间
    content TEXT,                   -- 文章内容（目前为空）
    keywords TEXT,                  -- 关键词（JSON格式）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_html TEXT,              -- HTML内容（备用）
    images_json TEXT,               -- 图片列表（备用）
    image_count INTEGER DEFAULT 0,  -- 图片数量
    table_count INTEGER DEFAULT 0   -- 表格数量
);
```

### FTS5 全文索引（已创建但未使用）

```sql
CREATE VIRTUAL TABLE articles_fts USING fts5(
    title, content, content='articles', content_rowid='id'
);
```

---

## 公众号列表

### 当前15个公众号

| 公众号 | 文章数 | 坐标类型 | 备注 |
|--------|--------|---------|------|
| 非科学美妆传播 | 20 | 备选坐标 | 指定发布时间(891,194), 确定(898,330) |
| 妆研24小时 | 19 | 标准坐标 | |
| 妆合规 | 18 | 标准坐标 | |
| Fbeauty未来迹 | 18 | 备选坐标 | 指定发布时间(891,194), 确定(898,330) |
| 原料合规观察 | 17 | 标准坐标 | |
| 个护前沿 | 16 | 标准坐标 | |
| KEV美妆 | 16 | 标准坐标 | |
| 美业颜究院 | 14 | 标准坐标 | |
| 肤见未来实验室 | 10 | 备选坐标 | 指定发布时间(891,194), 确定(898,330) |
| 美妆内行人 | 9 | 备选坐标 | 指定发布时间(891,194), 确定(898,330) |
| 中国化妆品 | 8 | 标准坐标 | |
| 化妆品观察 品观 | 7 | 备选坐标 | 指定发布时间(891,194), 确定(898,330) |
| 个护前言 | 6 | 标准坐标 | |
| 上海日化协会 | 6 | 标准坐标 | |
| Beauty Insider | 6 | 备选坐标 | 指定发布时间(891,194), 确定(898,330) |

### 已删除的公众号

| 公众号 | 删除时间 | 原因 |
|--------|---------|------|
| 春雷社 | 2026-06-29 | Nick要求删除 |
| 言安堂 | 2026-06-29 | Nick要求删除 |
| i美妆头条 | 2026-06-29 | Nick要求删除 |
| 用户说了 | 2026-06-29 | Nick要求删除 |
| 聚美丽 | 2026-06-29 | Nick要求删除 |
| 青眼 | 2026-06-29 | Nick要求删除 |

---

## 坐标配置

### 标准坐标（9个公众号）

| 元素 | 坐标 | 说明 |
|------|------|------|
| 公众号标签 | (579, 303) | 搜索后点击"公众号" |
| 搜索图标 | (933, 109) | 打开筛选界面 |
| 指定发布时间 | (891, 178) | 筛选条件 |
| 确定按钮 | (898, 314) | 确认筛选 |
| 综合排序 | (891, 184) | 排序方式 |
| 最新发布 | (1021, 239) | 时间排序 |
| 搜索框 | (672, 117) | 关键词搜索 |
| 右上角"···" | (1325, 51) | 文章菜单 |
| 复制链接 | (1210, 118) | 复制文章链接 |
| 关闭文章页 | (1099, 51) | 返回列表 |
| 关闭搜索窗口 | (459, 50) | 关闭筛选 |
| 关闭账号窗口 | (527, 55) | 关闭公众号 |
| 文章1 | (902, 349) | 第1篇文章 |
| 文章2 | (902, 476) | 第2篇文章 |
| 文章3 | (902, 600) | 第3篇文章 |
| 文章4 | (902, 729) | 第4篇文章 |

### 备选坐标（6个公众号）

**UI布局不同，指定发布时间和确定按钮向下偏移16px，文章列表也向下偏移16px**

| 元素 | 标准坐标 | 备选坐标 | 偏移 |
|------|---------|---------|------|
| 指定发布时间 | (891, 178) | (891, 194) | +16px |
| 确定按钮 | (898, 314) | (898, 330) | +16px |
| 文章1 | (902, 349) | (902, 365) | +16px |
| 文章2 | (902, 476) | (902, 492) | +16px |
| 文章3 | (902, 600) | (902, 616) | +16px |
| 文章4 | (902, 729) | (902, 745) | +16px |

**使用备选坐标的公众号**：非科学美妆传播、Fbeauty未来迹、肤见未来实验室、美妆内行人、Beauty Insider、化妆品观察 品观

---

## 采集流程

### 完整更新流程

```
Step 1: 采集（坐标点击自动化）
├── 运行: python3 collect.py '{"tasks":[{"account":"公众号名","count":4}]}'
├── 工具: peekaboo 控制 Mac 鼠标点击微信界面
├── 输出: ~/Desktop/wechat_articles_YYYYMMDD_HHMMSS.csv
├── 注意: 需要微信Mac版在前台，不能操作鼠标键盘
└── 自动激活: auto_collect_all.py 会自动激活微信窗口（osascript + peekaboo focus）

Step 2: 入库（collect_from_csv.py）
├── 读取 CSV 中的文章链接
├── urllib 抓取文章 HTML（使用微信移动端UA）
├── 从 HTML 中提取真实标题和发布时间
├── 检查URL是否已存在（去重）
└── 写入数据库: ~/.openclaw/cosmetic_articles.db

Step 3: 导出（export_data.py）
├── 读取数据库所有文章
├── 生成 data.json（包含 stats + sources + articles_by_source）
└── 输出: ~/.openclaw/workspace/cosmetic-deploy/data.json

Step 4: 推送（Git）
├── git add data.json
├── git commit -m "更新说明"
├── git push origin main
└── GitHub Pages 自动部署

Step 5: 网站显示
└── 用户访问 https://www.cosmetic-search.com/
    → 加载 data.json → 显示公众号列表和文章表格
```

### 一键采集命令

```bash
# 单个公众号
python3 collect.py '{"tasks":[{"account":"原料合规观察","count":4}]}'

# 多个公众号
python3 collect.py '{"tasks":[{"account":"公众号1","count":4},{"account":"公众号2","count":4}]}'

# 自然语言
python3 collect.py '获取原料合规观察最新4篇文章'
```

---

## 关键问题记录

### 问题1: 坐标偏差（已解决）

**现象**: 不同公众号的"指定发布时间"和"确定"按钮位置不同

**原因**: 部分公众号搜索结果页面有额外的UI元素，导致下方按钮整体下移16px

**解决**: 创建备选坐标列表，根据公众号自动选择正确坐标

**使用备选坐标的公众号**: 非科学美妆传播、Fbeauty未来迹、肤见未来实验室、美妆内行人、Beauty Insider、化妆品观察 品观

### 问题2: curl被微信拦截（已解决）

**现象**: 使用curl抓取文章时返回"环境异常"页面

**原因**: 微信反爬机制，非浏览器User-Agent会被拦截

**解决**: 
- 使用 urllib 替代 curl
- 使用微信移动端 User-Agent: `Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.0`

### 问题3: 发布时间错误（已解决）

**现象**: 部分文章显示采集当天日期而不是真实发布时间

**原因**: 
- 微信文章页面使用 JavaScript 动态加载时间
- curl 无法执行 JS，抓不到 #publish_time 元素
- 获取失败时 fallback 使用 datetime.now()

**解决**: 
- 从 HTML 中的 s1s_context_info 提取 URL编码的 JSON 时间戳
- 4种提取方法：URL编码时间戳、已解码JSON时间戳、页面元素、页面所有日期

### 问题4: 标题显示为默认标题（已解决）

**现象**: 入库后标题显示为"公众号名 文章"而不是真实标题

**原因**: curl被拦截，无法获取真实标题

**解决**: 使用 urllib + 微信移动端UA，可以正确获取标题

### 问题5: 全量采集超时（已解决）

**现象**: 采集15个公众号时进程被系统终止

**原因**: 系统对长时间运行进程有限制

**解决**: 分批采集，每次8个公众号，设置超时1200秒（20分钟）

### 问题6: 微信窗口未自动激活（已解决 - 2026-07-01）

**现象**: auto_collect_all.py 运行时微信窗口未在前台，导致采集失败（妆研24小时、非科学美妆传播等公众号采集失败）

**原因**: 
- collect.py 有 activate_wechat() 函数，但 auto_collect_all.py 直接调用 collect.py 时不会触发该函数
- 项目文档只写了"需要微信Mac版在前台"，没有说明自动激活机制

**解决**: 
- 在 auto_collect_all.py 的 collect_account() 函数开头添加微信激活代码
- 使用 osascript 激活 WeChat + peekaboo focus 聚焦窗口 + 等待3秒

**代码变更**:
```python
def collect_account(account: str, count: int = 4) -> bool:
    # 先激活微信窗口
    print("激活微信窗口...")
    subprocess.run([
        'osascript', '-e',
        'tell application "WeChat" to activate'
    ], capture_output=True)
    time.sleep(2)
    
    # 使用 peekaboo 聚焦窗口
    for app_name in ["WeChat", "微信"]:
        result = subprocess.run(
            f'peekaboo focus --app "{app_name}"',
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  已聚焦到: {app_name}")
            break
    time.sleep(1)
    
    # ... 原有采集代码
```

**文档更新**: 
- 采集流程中增加"自动激活"说明
- 添加问题6记录

**更新记录**: 2026-07-01 修复并更新文档

### 问题7: CSV文件堆积桌面（已解决 - 2026-07-01）

**现象**: 每次采集完一个公众号就生成一个CSV文件放在桌面，文件堆积

**原因**: collect.py 设计为输出CSV文件，auto_collect_all.py 再读取CSV入库

**解决**: 
- 创建 auto_collect_all_v2.py：直接采集 → 抓取文章信息 → 入库，跳过CSV中间步骤
- 保留 auto_collect_all.py 作为兼容版本（支持CSV模式）
- 新流程:
  ```
  采集文章链接 → 直接抓取标题和日期 → 直接入库SQLite → 导出data.json → 推送GitHub
  ```

**文件变更**:
- 新增: `auto_collect_all_v2.py` - 直接入库版本
- 保留: `auto_collect_all.py` - CSV兼容版本（import_csv函数改为可选）

**更新记录**: 2026-07-01

### 问题6: 微信窗口未自动激活（已解决 - 2026-07-01）

**现象**: auto_collect_all.py 运行时微信窗口未在前台，导致采集失败（妆研24小时、非科学美妆传播等公众号采集失败）

**原因**: 
- collect.py 有 activate_wechat() 函数，但 auto_collect_all.py 直接调用 collect.py 时不会触发该函数
- 项目文档只写了"需要微信Mac版在前台"，没有说明自动激活机制

**解决**: 
- 在 auto_collect_all.py 的 collect_account() 函数开头添加微信激活代码
- 使用 osascript 激活 WeChat + peekaboo focus 聚焦窗口 + 等待3秒

**代码变更**:
```python
def collect_account(account: str, count: int = 4) -> bool:
    # 先激活微信窗口
    print("激活微信窗口...")
    subprocess.run([
        'osascript', '-e',
        'tell application "WeChat" to activate'
    ], capture_output=True)
    time.sleep(2)
    
    # 使用 peekaboo 聚焦窗口
    for app_name in ["WeChat", "微信"]:
        result = subprocess.run(
            f'peekaboo focus --app "{app_name}"',
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  已聚焦到: {app_name}")
            break
    time.sleep(1)
    
    # ... 原有采集代码
```

**文档更新**: 
- 采集流程中增加"自动激活"说明
- 添加问题6记录

**更新记录**: 2026-07-01 修复并更新文档

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | 纯静态 HTML + JavaScript (ES5兼容) | 无框架，纯原生 |
| 数据 | SQLite → JSON (data.json) | 静态数据源 |
| 部署 | GitHub Pages | 静态托管 |
| 采集 | wechat-article-collector (Mac版, peekaboo) | 坐标点击自动化 |
| 入库 | Python3 + urllib + sqlite3 | 抓取+存储 |
| 版本控制 | Git | GitHub仓库 |

---

## 重要配置

### 微信移动端 User-Agent（绕过反爬）

```
Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.0
```

### 关键请求头

```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://mp.weixin.qq.com/',
}
```

---

## 七、关键问题记录（详细版）

### 问题1: 坐标偏差（已解决）

**现象**: 不同公众号的"指定发布时间"和"确定"按钮位置不同

**原因**: 部分公众号搜索结果页面有额外的UI元素（如提示条、广告等），导致下方按钮整体下移16px

**影响公众号**: 非科学美妆传播、Fbeauty未来迹、肤见未来实验室、美妆内行人、Beauty Insider、化妆品观察 品观

**解决过程**:
1. 2026-06-29 发现部分公众号采集失败
2. Nick指出是"指定发布时间"和"确定"按钮坐标有偏差
3. 测试确认标准坐标(891,178)和(898,314)不适合这些公众号
4. 发现备选坐标(891,194)和(898,330)可以正确点击
5. 创建ALT_COORDS_ACCOUNTS列表，自动根据公众号选择坐标
6. 同时发现文章列表也需要向下偏移16px

**代码实现**:
```python
# 需要备选坐标的公众号列表
ALT_COORDS_ACCOUNTS = ['非科学美妆传播', 'Fbeauty未来迹', '肤见未来实验室', '美妆内行人', 'Beauty Insider', '化妆品观察 品观']

# 标准坐标
COORDS = {
    'publish_time': (891, 178),
    'confirm': (898, 314),
}

# 备选坐标
COORDS_ALT = {
    'publish_time': (891, 194),  # 向下偏移16px
    'confirm': (898, 330),        # 向下偏移16px
}
```

### 问题2: curl被微信拦截（已解决）

**现象**: 使用curl抓取文章时返回"环境异常"页面，无法获取标题和发布时间

**错误信息**: 
```html
<div class="page-err">
    <h2>环境异常</h2>
    <p>当前操作环境异常，请完成验证</p>
</div>
```

**原因**: 微信反爬机制，检测User-Agent。非浏览器UA会被拦截

**解决过程**:
1. 2026-06-18 发现curl无法获取文章信息
2. 尝试多种User-Agent（Windows Chrome、Mac Safari等）均失败
3. 发现使用微信移动端UA可以绕过拦截
4. 将curl改为urllib，并设置正确的headers

**关键代码**:
```python
import urllib.request

headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://mp.weixin.qq.com/',
}

req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=20) as response:
    html = response.read().decode('utf-8')
```

### 问题3: 发布时间错误（已解决）

**现象**: 部分文章显示采集当天日期（如2026-06-18）而不是真实发布时间

**根本原因链**:
```
微信文章页面
    ↓
publish_time 是 JavaScript 动态渲染的
    ↓
curl 是静态HTTP请求，无法执行 JavaScript
    ↓
所以 curl 抓到的 HTML 中 #publish_time 元素为空
    ↓
微信反爬机制：非浏览器UA会返回"环境异常"页面
    ↓
即使使用微信移动端UA，有时仍会被拦截
    ↓
采集脚本在时间获取失败时，fallback 使用 datetime.now()
    ↓
结果：文章显示的是采集时间，不是真实发布时间
```

**已修复的文章（2026-06-18）**:
| 文章标题 | 错误时间 | 正确时间 | 修复方法 |
|---------|---------|---------|---------|
| 5月31日（今天）17点开播！ | 2026-06-18 | 2026-05-31 | 方法1: s1s_context_info |
| 618第二波预售定金红包 | 2026-06-18 | 2026-06-10 | 方法1: s1s_context_info |
| 首届国际再生与衰老医学大会 | 2026-06-18 | 2026-06-10 | 方法1: s1s_context_info |
| 中国化妆品监督抽检数据汇总报告 | 2026-06-18 | 2026-06-10 | 方法1: s1s_context_info |
| 第十八届全球化学品法规论坛 | 2026-06-18 | 2026-06-09 | 方法1: s1s_context_info |
| 国家药监局发布年报 | 2026-06-18 | 2026-06-11 | 方法1: s1s_context_info |

**4种时间提取方法**:
```python
# 方法1: 从 s1s_context_info 中提取URL编码的JSON时间戳
m = re.search(r'publish_time%22%3A(\d{10})', html)

# 方法2: 从已解码的JSON中提取时间戳
m = re.search(r'"publish_time"\s*:\s*(\d{10})', html)

# 方法3: 从页面元素获取（JS渲染后的）
m = re.search(r'id="publish_time"[^>]*>(.*?)</em>', html, re.DOTALL)

# 方法4: 从页面中提取所有日期，使用第一个合理的日期
dates = re.findall(r'(\d{4}-\d{2}-\d{2})', html)
```

### 问题4: 标题显示为默认标题（已解决）

**现象**: 入库后标题显示为"公众号名 文章"而不是真实标题

**原因**: curl被拦截，无法获取真实标题，fallback使用默认标题

**解决**: 使用 urllib + 微信移动端UA，可以正确获取标题

**关键代码**:
```python
def fetch_article_info(url: str) -> dict:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G960U)...MicroMessenger/8.0.0',
        # ...
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        html = response.read().decode('utf-8')
    
    # 解析标题
    title_match = re.search(r'<h1[^>]*class="rich_media_title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL)
    if title_match:
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
    
    return {"title": title, "publish_date": publish_date}
```

### 问题5: 全量采集超时（已解决）

**现象**: 采集15个公众号时进程被系统终止（SIGTERM）

**原因**: 系统对长时间运行进程有限制（默认600秒超时）

**解决**: 分批采集，每次8个公众号，设置超时1200秒（20分钟）

**分批策略**:
```python
# 第一批：8个公众号
python3 collect.py '{"tasks":[{"account":"妆研24小时","count":4},...]}'  # timeout=1200

# 第二批：7个公众号  
python3 collect.py '{"tasks":[{"account":"美妆内行人","count":4},...]}'  # timeout=1200
```

### 问题6: 剪贴板内容不正确（已解决）

**现象**: 点击"复制链接"后，剪贴板内容还是公众号名称而不是文章链接

**原因**: 
1. 点击"复制链接"的坐标不准确
2. 或者"···"菜单没有正确弹出

**解决**: 
1. 校准"复制链接"按钮坐标为(1210, 118)
2. 增加等待时间从0.5秒到1.5秒
3. 添加重试机制，最多尝试3次

### 问题7: 数据库字段不匹配（已解决）

**现象**: collect_from_csv.py 导入时提示 "no such column: source"

**原因**: 数据库表使用 `wechat_name` 字段，但脚本中使用 `source`

**解决**: 修改脚本中的字段名
```python
# 修改前
cursor.execute("INSERT INTO articles (title, url, source, ...) VALUES (?, ?, ?, ...)")

# 修改后
cursor.execute("INSERT INTO articles (title, url, wechat_name, ...) VALUES (?, ?, ?, ...)")
```

---

## 八、技术栈（详细版）

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 操作系统 | macOS | - | 开发环境 |
| 前端 | HTML5 + CSS3 + JavaScript | ES5兼容 | 无框架，纯原生 |
| 数据格式 | JSON | - | 静态数据源 |
| 数据库 | SQLite | 3.x | 本地存储 |
| 编程语言 | Python | 3.x | 采集+入库+导出 |
| 采集工具 | peekaboo | v3.2.1 | Mac屏幕坐标点击 |
| 版本控制 | Git | - | GitHub仓库 |
| 部署平台 | GitHub Pages | - | 静态托管 |
| 域名 | cosmetic-search.com | - | 已配置 |

---

## 九、重要配置（详细版）

### 9.1 微信移动端 User-Agent（绕过反爬）

```
Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.0
```

### 9.2 关键请求头

```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://mp.weixin.qq.com/',
}
```

### 9.3 数据库配置

```python
DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"
```

### 9.4 采集器配置

```python
COLLECTOR_PATH = Path.home() / ".openclaw/workspace/wechat-collector/skills/wechat-article-collector/scripts/collect.py"
```

### 9.5 GitHub仓库配置

```bash
# 仓库地址
https://github.com/benavidesbraian710-hub/cosmetic-articles-search.git

# 本地路径
~/.openclaw/workspace/cosmetic-deploy/

# 分支
main
```

---

## 十、更新记录（详细版）

| 时间 | 操作 | 结果 | 备注 |
|------|------|------|------|
| 2026-06-18 | 创建项目 | 初始版本 | 化妆品文章检索系统Basic版本 |
| 2026-06-18 | 修复发布时间 | 修复6篇文章 | 使用s1s_context_info提取时间戳 |
| 2026-06-18 | 调整坐标 | 适配1600x900 | 基于之前调整过的坐标 |
| 2026-06-29 | 删除6个公众号 | 删除20篇文章 | 春雷社、言安堂、i美妆头条、用户说了、聚美丽、青眼 |
| 2026-06-29 | 修复坐标偏差 | 添加备选坐标 | 支持6个特殊公众号 |
| 2026-06-29 | 修复curl拦截 | 使用urllib | 微信移动端UA绕过反爬 |
| 2026-06-29 | 修复数据库字段 | source→wechat_name | 匹配表结构 |
| 2026-06-29 | 全量采集第一批 | 8个公众号，32篇 | 新增26篇，跳过6篇 |
| 2026-06-29 | 全量采集第二批 | 7个公众号，24篇 | 新增13篇，跳过11篇 |
| 2026-06-29 | 修复Beauty Insider | 添加备选坐标 | 成功采集4篇 |
| 2026-06-29 | 最终入库 | 新增2篇 | 总文章数190篇 |
| 2026-06-29 | 推送网站 | GitHub Pages | 数据更新完成 |

---

## 版本演进说明

### 当前版本: Basic版本（V1）

**功能特性**:
- 公众号文章自动采集（坐标点击）
- 文章浏览（按公众号分类）
- 文章勾选导出CSV
- 去重机制（URL唯一约束）

**限制**:
- 无搜索功能
- 无文章正文
- 无LLM摘要
- 无关键词提取
- 无智能排序

**数据范围**:
- 从发布时间开始至今的所有文章
- 当前15个公众号，190篇文章
- 后续会根据用户需求增加公众号

### V2版本（规划）

**目标**: 增强功能，添加检索和正文

**功能**:
- [ ] 文章正文抓取
- [ ] 基础检索功能（关键词匹配）
- [ ] LLM摘要生成
- [ ] 关键词提取
- [ ] 高级筛选（时间范围、公众号）

**技术栈**:
- 后端: Flask + SQLite + FTS5
- 前端: 增强版HTML/JS
- AI: LLM API

### V3版本（规划）

**目标**: 智能检索系统

**文档**: 化妆品文章检索系统_产品设计方案_v1.2.md

**核心功能**:
1. 智能检索引擎（关键词召回 + LLM精排）
2. 文章摘要生成（LLM生成150-250字）
3. 关键词提取（8-15个关键词）
4. 多维度排序（时间、相关性、热度）
5. 个性化推荐
6. 高级筛选（公众号、时间范围、关键词）

**技术架构**:
- 后端: Flask + SQLite + FTS5
- 前端: React/Vue（待定）
- AI: LLM API（摘要、关键词、精排）
- 部署: 云服务器（待定）

**数据库扩展**:
- content: 文章正文
- summary: LLM生成的摘要
- keywords: 提取的关键词（JSON）
- 全文索引: FTS5（title + content）

---

## 十一、待办事项（优先级排序）

### P0 - 紧急
- [ ] 配置定时自动采集（Cron Job）
- [ ] 添加文章正文抓取（当前content字段为空）

### P1 - 重要
- [ ] 实现LLM摘要和关键词生成（产品设计方案要求）
- [ ] 开发检索引擎（Flask + FTS5）
- [ ] 部署Web界面（单条检索+批量检索）

### P2 - 一般
- [ ] 添加更多数据源（如RSS、API等）
- [ ] 优化前端界面（响应式、搜索高亮等）
- [ ] 添加文章分类和标签系统

### P3 - 未来
- [ ] 实现用户登录和收藏功能
- [ ] 添加文章推荐算法
- [ ] 支持多语言（英文、日文等）

---

## 十二、联系人

- **项目负责人**: Nick
- **技术实现**: 搜搜 (Sōusou) - AI搜索猎犬
- **项目路径**: ~/.openclaw/workspace/cosmetic-deploy/
- **数据库路径**: ~/.openclaw/cosmetic_articles.db
- **GitHub仓库**: https://github.com/benavidesbraian710-hub/cosmetic-articles-search
- **网站地址**: https://www.cosmetic-search.com/

---

## 十三、附录

### 附录A: 常用命令

```bash
# 采集单个公众号
python3 ~/.openclaw/workspace/wechat-collector/skills/wechat-article-collector/scripts/collect.py '{"tasks":[{"account":"原料合规观察","count":4}]}'

# 导入CSV到数据库
python3 ~/.openclaw/workspace/cosmetic-deploy/collect_from_csv.py ~/Desktop/wechat_articles_YYYYMMDD_HHMMSS.csv

# 导出数据库到JSON
python3 ~/.openclaw/workspace/cosmetic-deploy/export_data.py

# 推送网站更新
cd ~/.openclaw/workspace/cosmetic-deploy
git add data.json
git commit -m "更新说明"
git push origin main

# 查看数据库统计
sqlite3 ~/.openclaw/cosmetic_articles.db "SELECT COUNT(*) as total, COUNT(DISTINCT wechat_name) as sources FROM articles;"

# 查看公众号列表
sqlite3 ~/.openclaw/cosmetic_articles.db "SELECT wechat_name, COUNT(*) as count FROM articles GROUP BY wechat_name ORDER BY count DESC;"
```

### 附录B: 产品设计方案

**文档路径**: ~/.openclaw/workspace/化妆品文章检索系统_产品设计方案_v1.2.md

**核心功能**:
1. 数据库表结构（含summary, keywords, content）
2. FTS5全文索引（支持title+content检索）
3. 文章摘要生成（入库时LLM生成150-250字）
4. 关键词提取（LLM提取8-15个关键词）
5. 检索引擎（关键词召回+LLM精排）
6. Web界面（单条检索+批量检索）
7. 定时自动采集

**当前实现状态**:
- ✅ 数据库表结构
- ✅ FTS5全文索引
- ❌ LLM摘要生成
- ❌ 关键词提取
- ❌ 检索引擎
- ❌ Web界面（检索功能）
- ❌ 定时自动采集

### 附录C: 历史文件清单

| 文件 | 路径 | 说明 | 状态 |
|------|------|------|------|
| fix_all_times.py | ~/.openclaw/workspace/cosmetic-deploy/ | 修复发布时间脚本 | 历史 |
| collect_from_wechat_mac.py | ~/.openclaw/workspace/cosmetic-deploy/ | 旧版采集脚本 | 历史 |
| collect_and_save.py | ~/.openclaw/workspace/cosmetic-deploy/ | 旧版采集+入库 | 历史 |
| wechat_article_collector.py | ~/.openclaw/workspace/wechat-auto/ | 历史坐标版本 | 历史 |
| test_click.py | ~/.openclaw/workspace/wechat-auto/ | 历史测试脚本 | 历史 |
| test_full_workflow.py | ~/.openclaw/workspace/wechat-auto/ | 历史测试脚本 | 历史 |
| test_click_search_abs.py | ~/.openclaw/workspace/wechat-auto/ | 历史测试脚本 | 历史 |
| test_debug.py | ~/.openclaw/workspace/wechat-collector/.../scripts/ | 调试脚本 | 当前可用 |
| collect_relative.py | ~/.openclaw/workspace/wechat-collector/.../scripts/ | 相对坐标采集器 | 备用 |
| auto_collect.py | ~/.openclaw/workspace/cosmetic-deploy/ | 自动采集+入库+推送 | 当前可用 |
| auto_collect_all.py | ~/.openclaw/workspace/cosmetic-deploy/ | 全量自动采集 | 当前可用 |

---

**文档版本**: v1.1
**创建时间**: 2026-06-29 12:13
**最后更新**: 2026-06-29 12:19
**项目负责人**: Nick
**技术实现**: 搜搜 (Sōusou) - AI搜索猎犬

**声明**: 本文档包含化妆品文章检索系统的所有关键信息，包括但不限于系统架构、配置参数、问题记录、解决方案等。任何对系统的修改都应更新此文档。
