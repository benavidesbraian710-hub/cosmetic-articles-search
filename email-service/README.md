# 化妆品文章邮件查询系统

> 基于 Node.js + IMAP IDLE + SQLite 的实时邮件自动化系统，支持自然语言查询和 Excel 批量查询。

## 📋 项目概述

部署在 OpenClaw Gateway 环境的邮件自动化系统，能够：
- **IMAP IDLE 实时监听** 163 邮箱新邮件（秒级响应）
- 解析用户搜索需求（自然语言 / Excel 附件）
- 从 **SQLite 数据库** 本地查询化妆品文章
- 生成 Excel 结果文件
- **原线程回复** 邮件（带 `inReplyTo` + `references`）

## 🏗️ 系统架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   用户发送邮件   │────▶│  163 邮箱服务器  │────▶│  IMAP IDLE      │
│  (任何邮箱)      │     │  (IMAP/SMTP)   │     │  实时监听        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  用户收到回复    │◀────│  163 邮箱服务器  │◀────│  mail-processor │
│  (含 Excel 附件)│     │    (SMTP)      │     │    (Node.js)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                                                  ┌─────────────────┐
                                                  │  SQLite 查询    │
                                                  │  + Excel 生成   │
                                                  └─────────────────┘
```

## 🔧 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| IMAP 客户端 | `imapflow` | IMAP IDLE 实时监听 |
| SMTP 客户端 | `nodemailer` | 发送回复邮件 |
| 邮件解析 | `mailparser` | 解析邮件正文和附件 |
| 数据库 | `sqlite3` | 本地 SQLite 查询 |
| Excel 生成 | `xlsx` | 解析和生成 Excel |
| 日志 | 自定义 `logger.js` | 结构化文件日志 |
| 进程管理 | `pm2` | 常驻运行 |

## 📁 项目结构

```
email-service/
├── README.md                      # 项目说明（本文档）
├── mail-processor.js              # 主处理脚本（Node.js，~980行）
├── mail-processor-once.js         # 单次运行版本（测试用）
├── logger.js                      # 结构化日志模块
├── package.json                   # Node.js 依赖
├── package-lock.json
├── requirements.txt               # Python 依赖（历史遗留，未使用）
├── .env                           # 环境变量（IMAP/SMTP 密码）
├── .gitignore
├── logs/                          # 日志文件目录
│   ├── app.log                    # 应用日志
│   └── error.log                  # 错误日志
├── docs/                          # 文档目录
│   ├── SETUP.md                   # 部署指南（历史）
│   ├── ARCHITECTURE.md            # 架构文档（历史）
│   └── API.md                     # API 文档（历史）
├── scripts/                       # 历史脚本（未使用）
│   ├── config.js
│   ├── imap.js
│   ├── smtp.js
│   ├── test-imap.js
│   ├── test-smtp.js
│   ├── idle_imapflow.js
│   └── idle_imap.js
├── REPLY_DUPLICATE_FIX.md         # 重复发送修复记录
├── REPLY_THREAD_PLAN.md           # 原线程回复方案
├── UPDATE_STATUS.md               # 更新状态记录
└── search_result_*.csv            # 历史搜索结果文件
```

## 🚀 部署与运行

### 1. 环境准备

```bash
cd email-service
npm install
```

依赖包：
- `imapflow` - IMAP 协议
- `nodemailer` - SMTP 发送
- `mailparser` - 邮件解析
- `sqlite3` - SQLite 数据库
- `xlsx` - Excel 读写
- `dotenv` - 环境变量

### 2. 配置环境变量

```bash
# .env 文件
IMAP_USER=cosmeticsearch@163.com
IMAP_PASS=your_163_password
SMTP_USER=cosmeticsearch@163.com
SMTP_PASS=your_163_password
```

> ⚠️ 163 邮箱需开启 IMAP/SMTP 服务，并使用**授权码**而非登录密码。

### 3. 启动（pm2 常驻）

```bash
pm2 start mail-processor.js --name mail-processor
pm2 save
```

### 4. 查看状态

```bash
pm2 status
pm2 logs mail-processor
```

## 📧 使用方式

### 方式一：自然语言查询

1. 发送邮件到：`cosmeticsearch@163.com`
2. 邮件主题：搜索需求（如"搜索防晒相关文章"）
3. 系统解析需求 → 查询数据库 → 回复 Excel 附件

### 方式二：Excel 批量查询

1. 发送邮件到：`cosmeticsearch@163.com`
2. 邮件主题：任意
3. 附件：Excel 文件，包含两列：
   - 第 2 列（B列）：公众号名称
   - 第 3 列（C列）：时间范围（如"2025-06-01 至 2025-06-30"）
4. 系统解析 Excel → 批量查询 → 回复汇总 Excel

### 系统处理流程

```
收到邮件
    ↓
IMAP IDLE 实时触发
    ↓
解析邮件（自然语言 / Excel 附件）
    ↓
提取关键词、公众号、时间范围
    ↓
SQLite 数据库本地查询
    ↓
生成 Excel 文件
    ↓
原线程回复邮件（inReplyTo + references）
    ↓
标记邮件为已读（防止重复处理）
```

## ⚙️ 关键配置

### 数据库路径

```javascript
// mail-processor.js 第 53 行
CONFIG.dbPath = path.join(require('os').homedir(), '.openclaw/cosmetic_articles.db');
```

> ⚠️ **注意**：2026-07-10 数据库已迁移到新路径 `~/.openclaw/workspace/cosmetic-deploy/cosmetic_articles.db`，但邮件系统配置仍为旧路径。当前运行正常是因为旧路径有软链接或数据同步。

### IMAP IDLE + NOOP 心跳

```javascript
// 每 2 分钟发送 NOOP 保持连接
setInterval(() => {
  client.idle();
  client.noop();
}, 2 * 60 * 1000);
```

解决 163 邮箱 3 分 21 秒静默断开问题。

### 原线程回复

```javascript
mailOptions.inReplyTo = originalMessageId;
mailOptions.references = [originalMessageId];
```

确保回复邮件出现在原邮件线程中。

## 🔍 查询逻辑

### 自然语言查询

- 提取关键词（如"防晒"、"口红"）
- 模糊匹配文章标题
- 按时间倒序排列
- 返回全部匹配结果（无数量限制）

### Excel 批量查询

- 解析每行的公众号名称和时间范围
- 支持相对时间（"近一周"、"近一月"）
- 支持绝对时间（"2025-06-01 至 2025-06-30"）
- 汇总所有查询结果到一个 Excel

## 📝 修复记录

### 2026-07-06
- **原线程回复**：添加 `inReplyTo` + `references` 头
- **重复发送修复**：先标记已读再处理，防止网络延迟导致重复

### 2026-07-07
- **IMAP NOOP 心跳**：每 2 分钟发送 NOOP，解决 163 邮箱 3 分 21 秒静默断开
- 根治 pm2 108 次异常重启问题

### 2026-07-03 ~ 07-06
- Excel 附件解析从"大模型解析"改为"代码直接解析"（更稳定）
- 修复列索引错误（第 2 列公众号名、第 3 列时间范围）
- 去除回复中的数量限制信息

## 📝 开发记录

### 初始版本（2026-06-30）
- 基于 Python `mail_processor.py` + OpenClaw Cron 轮询
- 15 分钟轮询间隔
- 通用网络搜索（web_search/web_fetch）

### 当前版本（2026-07-08 后）
- 纯 Node.js 实现 `mail-processor.js`
- IMAP IDLE 实时监听（秒级响应）
- SQLite 本地查询（无需网络搜索）
- pm2 常驻运行（非 Cron）

## 🤝 维护

- **负责人**: Nick
- **技术支持**: 搜搜 (Sōusou)
- **邮箱**: cosmeticsearch@163.com

---

> 🔍 搜搜 (Sōusou) - Nick 的专属 AI 搜索猎犬
> 7×24 小时监控全球前沿信息，让 Nick 永远领先一步。
