# 163 邮箱自动化系统

> 基于 OpenClaw Gateway 的邮件自动化处理系统，支持智能轮询、需求解析、信息搜索和 Excel 生成。

## 📋 项目概述

这是一个部署在 OpenClaw Gateway 环境的邮件自动化系统，能够：
- 自动检查 163 邮箱新邮件
- 解析用户搜索需求
- 执行网络搜索
- 生成 Excel 结果文件
- 自动回复邮件

## 🏗️ 系统架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   用户发送邮件   │────▶│  163 邮箱服务器  │────▶│  OpenClaw      │
│   (任何邮箱)    │     │  (IMAP/SMTP)   │     │  Gateway 环境   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  用户收到回复    │◀────│  163 邮箱服务器  │◀────│  邮件处理脚本    │
│  (含 Excel 附件)│     │    (SMTP)      │     │  (Python/Node)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                                                  ┌─────────────────┐
                                                  │   搜索 + Excel  │
                                                  │   生成模块      │
                                                  └─────────────────┘
```

## 🔧 技术栈

- **IMAP 客户端**: `imapflow` (Node.js)
- **SMTP 客户端**: `nodemailer` (Node.js)
- **邮件处理**: Python 3
- **搜索功能**: web_search, web_fetch (OpenClaw 工具)
- **Excel 生成**: csv/xlsx (Python)
- **定时任务**: OpenClaw Cron (每 15 分钟)

## 📁 项目结构

```
email-service/
├── README.md                      # 项目说明
├── docs/
│   ├── SETUP.md                  # 部署指南
│   ├── ARCHITECTURE.md           # 架构文档
│   └── API.md                    # API 文档
├── scripts/
│   ├── config.js                 # 配置管理
│   ├── imap.js                   # IMAP 操作脚本
│   ├── smtp.js                   # SMTP 发送脚本
│   ├── test-imap.js              # IMAP 测试
│   ├── test-smtp.js              # SMTP 测试
│   ├── idle_imapflow.js          # IMAP IDLE 实验（不推荐）
│   └── idle_imap.js              # IMAP IDLE 实验（不推荐）
├── mail_processor.py             # 主处理脚本（Python）
├── requirements.txt              # Python 依赖
├── package.json                  # Node.js 依赖
└── .env.example                  # 环境变量模板
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装 Node.js 依赖
npm install

# 安装 Python 依赖
pip3 install -r requirements.txt
```

### 2. 配置邮箱

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件
IMAP_HOST=imap.163.com
IMAP_PORT=993
IMAP_USER=cosmeticsearch@163.com
IMAP_PASS=your_password
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=cosmeticsearch@163.com
SMTP_PASS=your_password
```

### 3. 测试连接

```bash
# 测试 IMAP
node scripts/test-imap.js

# 测试 SMTP
node scripts/test-smtp.js
```

### 4. 启动定时任务

系统已配置 OpenClaw Cron 任务，每 15 分钟自动执行：
- 任务名: `check-inbox-every-15min`
- 执行: `python3 ~/mail_processor.py`

## 📧 使用方式

### 发送邮件触发搜索

1. 发送邮件到: `cosmeticsearch@163.com`
2. 邮件主题: 搜索需求（如"搜索口红推荐"）
3. 邮件正文: 详细需求（可选）

### 系统处理流程

```
收到邮件
    ↓
解析需求类型（AI/芯片/化妆品/新闻等）
    ↓
提取关键词和时间范围
    ↓
执行网络搜索
    ↓
生成 Excel 文件
    ↓
回复邮件（含附件）
    ↓
标记邮件为已读
```

## ⚙️ 配置选项

### 轮询间隔

默认: **15 分钟**（推荐）

可选:
- 2 分钟（更快，但资源消耗更高）
- 5 分钟（平衡）
- 15 分钟（默认，资源友好）

### 搜索关键词映射

```python
KEYWORD_PATTERNS = {
    "AI": ["AI", "人工智能", "大模型", "LLM"],
    "quantum": ["量子", "quantum", "量子计算"],
    "chip": ["芯片", "chip", "半导体", "GPU"],
    "robotics": ["机器人", "robot", "具身智能"],
    "biotech": ["生物", "biotech", "基因"],
    "news": ["新闻", "news", "资讯"],
    "paper": ["论文", "paper", "arxiv"],
    "product": ["产品", "product", "发布"],
    "funding": ["融资", "funding", "投资"],
}
```

## 🔍 实时推送方案对比

| 方案 | 延迟 | 可靠性 | 资源消耗 | 适用性 |
|------|------|--------|----------|--------|
| IMAP IDLE | 实时 | ⚠️ 不稳定 | 高 | ❌ Gateway 不支持 |
| 2分钟轮询 | 2-4分钟 | ✅ 高 | 中 | ⚠️ 163 可能限制 |
| **5分钟轮询** | 5-10分钟 | ✅ 高 | 低 | ✅ 推荐 |
| **15分钟轮询** | 15-30分钟 | ✅ 高 | 很低 | ✅ **当前使用** |

## 📝 开发记录

### 2026-06-30

**已完成:**
- ✅ 163 邮箱 IMAP/SMTP 连接配置
- ✅ 邮件读取和发送功能测试
- ✅ Python 邮件处理脚本
- ✅ 需求解析逻辑（关键词识别）
- ✅ Excel 生成模块
- ✅ OpenClaw Cron 定时任务（15分钟）
- ✅ 项目文档和 README

**技术决策:**
- 选择轮询而非 IMAP IDLE（Gateway 环境限制）
- 15 分钟轮询间隔（平衡实时性和资源消耗）
- Python 处理邮件内容，Node.js 处理 IMAP/SMTP 协议

**待完成:**
- ⏳ 化妆品搜索关键词配置
- ⏳ 实际搜索和 Excel 生成逻辑
- ⏳ 错误处理和重试机制优化
- ⏳ 邮件模板美化

## 🤝 贡献

项目由 Nick 和搜搜 (Sōusou) 共同开发。

## 📄 许可证

MIT

---

> 🔍 搜搜 (Sōusou) - Nick 的专属 AI 搜索猎犬
> 7×24 小时监控全球前沿信息，让 Nick 永远领先一步。
