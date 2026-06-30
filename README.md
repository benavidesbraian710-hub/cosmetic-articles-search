# Cosmetic Articles Search System

## 项目结构

```
cosmetic-deploy/
├── api/                    # Vercel Serverless Functions
│   ├── index.py           # 主入口（Flask应用）
│   ├── stats.py           # 统计API
│   ├── sources.py         # 公众号列表API
│   ├── articles.py        # 文章列表API
│   └── export.py          # 导出API
├── email-service/          # 新增：邮件自动化服务
│   ├── README.md
│   ├── mail-processor.js  # 邮件处理主脚本
│   ├── package.json
│   ├── requirements.txt
│   ├── docs/              # 文档
│   └── scripts/           # IMAP/SMTP 脚本
├── static/                 # 静态文件
│   ├── css/
│   ├── js/
│   └── images/
├── templates/              # HTML模板
│   ├── index.html         # Basic版本
│   ├── index_v1.html      # 完整版v1（历史版本）
│   └── index_v2.html      # 完整版v2（历史版本）
├── versions/               # 版本历史存档
│   ├── v1.0_basic/        # 当前版本
│   ├── v1.1_full/         # 完整版v1
│   └── v2.0_search/       # 检索版v2
├── vercel.json            # Vercel配置
├── requirements.txt       # Python依赖
└── README.md
```

## 新增功能：邮件自动化服务

系统现已支持通过邮件触发搜索请求：

### 使用方法
1. 发送邮件到: **cosmeticsearch@163.com**
2. 邮件主题: 搜索需求（如"搜索口红推荐"）
3. 系统会自动回复 Excel 格式的搜索结果

### 技术架构
```
用户邮件 → 163邮箱 → OpenClaw Gateway → 邮件处理 → 搜索 → Excel → 回复
```

### 配置说明
详见 `email-service/README.md`

---

## 版本管理策略

### 1. URL版本控制
- `/` - 当前最新版本（Basic）
- `/v1` - 完整版v1（保留）
- `/v2` - 检索版v2（保留）
- `/basic` - Basic版本（固定入口）

### 2. 部署历史
Vercel自动保留每次部署的历史版本，可以随时回滚。

## 部署步骤

### 新增：邮件服务部署

邮件服务部署在 OpenClaw Gateway 环境：

```bash
cd email-service
npm install
# 配置 .env 文件
# 启动定时任务（OpenClaw Cron）
```

详见 `email-service/docs/SETUP.md`

---

### Vercel 部署（原有）

### 1. 安装Vercel CLI
```bash
npm install -g vercel
```

### 2. 登录Vercel
```bash
vercel login
```

### 3. 部署
```bash
vercel --prod
```

### 4. 绑定自定义域名
在Vercel Dashboard中添加域名并配置DNS。

## 环境变量

在Vercel Dashboard中设置：
- `DB_PATH` - 数据库路径
- `SECRET_KEY` - 安全密钥

## 数据库说明

当前使用SQLite数据库，文件路径：
`~/.openclaw/cosmetic_articles.db`

部署到Vercel后需要：
1. 将数据库转换为PostgreSQL或MySQL
2. 或使用Vercel KV存储
3. 或定期同步数据库文件

## 后续迭代计划

### v1.1（计划中）
- 增加搜索功能
- 关键词筛选

### v1.2（计划中）
- 用户登录
- 收藏功能

### v2.0（规划中）
- AI智能推荐
- 数据分析报表
# 部署时间: Thu Jun 18 11:22:35 CST 2026
