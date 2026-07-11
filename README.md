# Cosmetic Articles Search System

化妆品文章检索系统 - 7×24小时监控化妆品行业公众号，自动采集文章，提供浏览、导出和邮件查询服务。

## 项目概述

| 项目 | 内容 |
|------|------|
| **网站** | https://www.cosmetic-search.com/ |
| **GitHub** | https://github.com/benavidesbraian710-hub/cosmetic-articles-search |
| **部署** | Vercel 静态托管（GitHub 自动部署 + Deploy Hook） |
| **当前数据** | 293篇文章，12个公众号 |
| **数据范围** | 2026-06-15 及之后的文章 |
| **最后更新** | 2026-07-10 |

## 项目结构

```
cosmetic-deploy/
├── index.html              # 网站前端（纯静态）
├── data.json               # 当前数据源（软链接到最新版本）
├── data.v15.json           # 版本15数据源（293篇，当前）
├── data.v14.json           # 版本14数据源
├── ...                     # 历史版本
├── cosmetic_articles.db    # SQLite数据库
├── export_data.py          # 导出数据库到JSON
├── today_pipeline.py       # 全链路自动化：采集→入库→导出→推送→部署
├── collect_from_csv.py     # CSV入库脚本
├── auto_collect.py         # 自动采集+入库+推送
├── auto_collect_all.py     # 全量自动采集
├── auto_collect_all_v2.py  # 全量采集（带Deploy Hook）
├── collect.py              # 坐标点击采集器（微信文章采集）
├── email-service/          # 邮件自动化服务
│   ├── README.md           # 邮件服务文档
│   ├── mail-processor.js   # 邮件处理主脚本（Node.js + IMAP IDLE）
│   ├── logger.js           # 结构化日志
│   ├── package.json        # Node.js依赖
│   ├── logs/               # 日志文件
│   └── ...                 # 历史文件和文档
├── PROJECT.md              # 项目详细文档
├── README.md               # 本文档
└── ...                     # 其他工具和脚本
```

## 核心功能

### 1. 网站浏览
- 左侧公众号列表，右侧文章表格
- 按公众号分类浏览
- 勾选导出 CSV

### 2. 邮件查询
- 发送邮件到 **cosmeticsearch@163.com**
- 自然语言查询：邮件主题写搜索需求（如"搜索防晒相关文章"）
- Excel 批量查询：附件上传 Excel（B列公众号名，C列时间范围）
- 系统自动回复 Excel 格式的搜索结果

### 3. 自动采集
- 坐标点击自动化采集微信公众号文章
- 事前过滤：只保留 2026-06-15 及之后的文章
- 自动去重：URL 唯一约束
- 全链路自动化：采集 → 入库 → 导出 → 推送 GitHub → 触发 Vercel 部署

## 部署方式

### Vercel 静态托管

```bash
# 推送代码到 GitHub，Vercel 自动部署
git add data.vN.json index.html
git commit -m "data: update to vN"
git push origin main

# 触发 Deploy Hook（硬编码在 today_pipeline.py 中）
```

### 邮件服务（pm2 常驻）

```bash
cd email-service
npm install
pm2 start mail-processor.js --name mail-processor
pm2 save
```

## 环境变量

### 邮件服务（email-service/.env）
```
IMAP_USER=cosmeticsearch@163.com
IMAP_PASS=your_163_password
SMTP_USER=cosmeticsearch@163.com
SMTP_PASS=your_163_password
```

## 公众号列表（12个）

| 公众号 | 文章数 | 坐标类型 |
|--------|--------|---------|
| 个护前沿 | 54 | 标准坐标 |
| 化妆品观察 品观 | 44 | 备选坐标 |
| 中国化妆品 | 40 | 标准坐标 |
| 妆研24小时 | 27 | 标准坐标 |
| Fbeauty未来迹 | 26 | 备选坐标 |
| 非科学美妆传播 | 25 | 备选坐标 |
| 妆合规 | 23 | 标准坐标 |
| 肤见未来实验室 | 18 | 备选坐标 |
| 原料合规观察 | 17 | 标准坐标 |
| KEV美妆 | 10 | 标准坐标 |
| 美业颜究院 | 6 | 标准坐标 |
| 上海日化协会 | 3 | 标准坐标 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 纯静态 HTML + JavaScript (ES5兼容) |
| 数据 | SQLite → JSON (data.vN.json，版本递增) |
| 部署 | Vercel（GitHub 自动部署 + Deploy Hook） |
| 采集 | peekaboo 坐标点击自动化 |
| 入库 | Python3 + urllib + sqlite3 |
| 邮件 | Node.js + IMAP IDLE + SQLite 本地查询 |
| 版本控制 | Git |

## 重要规则

1. **数据时效性**：只保留 2026-06-15 及之后的文章（事前过滤）
2. **采集超时**：必须保持 1800 秒，不得擅自修改
3. **采集确认**：采集前必须确认 12 个公众号目标名单
4. **版本递增**：每次导出递增 data.vN.json 版本号，强制 Vercel 重新构建
5. **数据库路径**：`~/.openclaw/workspace/cosmetic-deploy/cosmetic_articles.db`

## 维护

- **负责人**: Nick
- **技术支持**: 搜搜 (Sōusou)
- **邮箱**: cosmeticsearch@163.com

---

> 🔍 搜搜 (Sōusou) - Nick 的专属 AI 搜索猎犬
> 7×24 小时监控全球前沿信息，让 Nick 永远领先一步。
