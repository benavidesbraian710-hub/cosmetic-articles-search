# 架构与决策记录（Architecture & Decision Records）

> 本文档记录项目的核心架构、关键决策、以及决策背后的真实原因（特别是做错的决策）。
> 接手者读完后，应该能理解"为什么是这样"而不只是"这是什么"。

---

## 1. 当前架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    用户浏览器                                  │
└─────────────────────────────────────────────────────────────┘
       │                                          │
       │ ①访问主页                                  │ ②调用智能找文
       ▼                                          ▼
┌──────────────────────────┐         ┌──────────────────────────┐
│  Vercel CDN              │         │  Cloudflare 边缘           │
│  www.cosmetic-search.com │         │  api.cosmetic-search.com  │
└──────────────────────────┘         └──────────────────────────┘
       │                                          │
       │ git push 自动部署                         │ Cloudflare 隧道
       │                                          │ 客户端 PID 59252
       ▼                                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    Mac mini (M4, 16GB)                        │
│  ┌────────────────────────┐  ┌─────────────────────────────┐  │
│  │ 静态网站代码             │  │ uvicorn (PID 68638 已关)    │  │
│  │ - 7 个 HTML 文件        │  │ FastAPI + LLM 精排          │  │
│  │ - data.v92.json (3.1MB)│  │                             │  │
│  │ - stats.json           │  │                             │  │
│  │ - offer-rate/ 子页面    │  │                             │  │
│  └────────────────────────┘  └─────────────────────────────┘  │
│              │                              │                │
│              └──────────────┬───────────────┘                │
│                             ▼                                │
│              ┌─────────────────────────────┐                │
│              │ cosmetic_articles.db (31MB)  │                │
│              │ SQLite · 1717篇 · v92        │                │
│              └─────────────────────────────┘                │
│                             │                                │
│                             ▼ (每次 export_data.py 自动触发) │
│              ┌─────────────────────────────┐                │
│              │ sync_db_to_ecs.sh            │                │
│              │ SCP 数据库到 ECS              │                │
│              └─────────────────────────────┘                │
└──────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                              ┌──────────────────────────┐
                              │  ECS (8.133.238.76)      │
                              │  nginx + FastAPI 备用     │
                              │  数据可能陈旧（手动同步）  │
                              └──────────────────────────┘
```

---

## 2. 各组件职责

### 2.1 前端（Vercel CDN）
- **位置**：Vercel 全球边缘节点
- **域名**：`www.cosmetic-search.com`（主）、`cosmetic-preview.vercel.app`（预览）
- **代码来源**：GitHub `cosmetic-articles-search` 仓库
- **分支策略**：
  - `main` → 主站（生产，稳定）
  - `feature/new-arch` → 预览站（新视觉验证）
- **部署触发**：git push 到 GitHub → Vercel 自动 build → CDN 分发
- **核心文件**：
  - `index.html` / `articles.html` / `find.html` / `report.html` / `service.html` / `submit.html` / `admin.html`
  - `data.vXX.json`（最新文章数据，3.1MB）
  - `stats.json`（首页统计专用，~2KB）
  - `smart-search-data.json`（智能找文专用）
  - `offer-rate/`（Offer Rate 子页面，220 张图片 + data.json）

### 2.2 后端 API（智能找文）
- **位置**：Mac mini uvicorn（当前）+ ECS（备用）
- **框架**：FastAPI + SQLite + Kimi K3 LLM
- **检索架构**：意图锚定检索
  1. LLM 意图解析（用户查询 → 关键词四层分层）
  2. FTS5 锚点检索（SQLite 全文搜索 + BM25）
  3. LLM 精排（按相关度排序，给出具体匹配理由）
- **核心端点**：
  - `GET  /api/health` → 健康检查
  - `GET  /api/stats` → 统计信息（文章数、公众号数、日期范围）
  - `POST /api/search` → 智能搜索（body: `{query, limit, offset}`）
  - `GET  /api/articles/{id}` → 文章详情
- **入口**：Cloudflare 命名隧道 → Mac mini localhost:8000

### 2.3 数据库
- **类型**：SQLite 3
- **位置**：Mac mini `~/openclaw/workspace/cosmetic-deploy/cosmetic_articles.db`
- **大小**：~31MB（1717 篇文章）
- **表结构**：
  ```sql
  CREATE TABLE articles (
      id INTEGER PRIMARY KEY,
      title TEXT NOT NULL,
      content TEXT,
      publish_date TEXT NOT NULL,    -- YYYY-MM-DD 格式
      wechat_name TEXT NOT NULL,     -- 必须属于 18 个白名单公众号之一
      url TEXT UNIQUE NOT NULL,
      keywords TEXT,                  -- JSON 数组
      images_json TEXT,               -- JSON 数组
      summary TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
- **同步策略**：每次 `export_data.py` 运行后自动 SCP 到 ECS

### 2.4 数据采集
- **流程**：RPA 采集 → Excel → AI 入库
- **采集方式**：新电脑 RPA 每日自动抓取 18 个公众号文章链接
- **传输方式**：Excel 文件通过飞书 / 本地 inbound 目录传到 Mac mini
- **入库工具**：`batch_add_0806.py`（带反爬 UA + 字段硬校验）

---

## 3. 关键决策记录

### 3.1 ⚠️ 决策失败案例：后端 API 从 Mac mini 迁到 ECS（2026-08-27）

#### 决策内容
将智能找文 API 从 Mac mini 本地迁移到阿里云 ECS 服务器。

#### 当时的理由
- "Mac mini 是私人电脑不可靠（休眠/重启/离开实习）"
- "ECS 24x7 更专业"
- "未来调用量大要提前规划"
- "配合 Cloudflare 命名隧道切换，架构更现代"

#### 实际结果（**错误**）
- ECS 服务起来了，但**数据库从未成功同步**
- 智能找文**连续 14 天返回陈旧数据**（1507 篇 / 09-02）
- 每月仍花 ECS 钱
- 用户看不到正确的搜索结果（要么 530、要么旧数据）

#### 真实问题根因
1. **数据同步脚本 `sync_db_to_ecs.sh` 试图 git push 数据库文件，但 `cosmetic_articles.db` 被 `.gitignore` 忽略了**，所以每天跑、每天都没真正推数据
2. **没做前置验证就迁移**——应该先验证"Mac mini 方案到底能不能扛住"
3. **用"未来可能"代替"实际现在"做容量规划**——实际日均调用才几十次，根本不需要 ECS

#### 复盘教训
- **零维护优先 > 链路短 > 架构优雅**——这次选了"架构优雅"，付出代价
- **"完成"必须包含"功能真的在跑"**——ECS 服务起来了 ≠ 智能找文能用
- **"功能存在" ≠ "功能真的在跑"**——必须实测才能下结论

#### 补救方案（2026-09-10）
1. cloudflared 隧道改回指向 Mac mini 本地 uvicorn
2. 写新的 `sync_db_to_ecs.sh`（用 SCP 而不是 git，避免 gitignore 问题）
3. export_data.py 末尾自动调用同步脚本
4. 决定：Mac mini 为主、ECS 为备用（数据可能陈旧）

#### 接手者建议
**保持现状**，不要轻易再迁回 ECS。除非以下情况：
- Mac mini 真的扛不住（日均调用破千）
- Nick 离开实习，电脑无法延续
- 接手者明确要求

### 3.2 ✅ 决策正确案例：版本号自动递增（2026-07-02）

#### 决策内容
数据库每次更新后，`export_data.py` 自动扫描已有 `data.vXX.json` 取最大编号+1。

#### 原因
避免硬编码版本号导致的"忘了改"问题。

#### 实际效果
- 从 v2 自动递增到 v92（90 天）
- 每次 HTML 引用都更新到最新版本号
- 浏览器缓存强制失效

### 3.3 ✅ 决策正确案例：入库硬校验（2026-08-10）

#### 决策内容
入库脚本增加字段硬校验：标题非空、日期 YYYY-MM-DD、公众号必须在白名单。

#### 原因
解决反爬脏数据问题（07-29 标题空白、08-04 日期缺失、08-05 双空 等多次发作）。

#### 实际效果
- 反爬失败时跳过而不是写入脏数据
- 失败列表记录供人工补录
- 数据质量稳定提升

---

## 4. 已知的待优化项

### 4.1 仓库清理
- 57 个历史 `data.vXX.json` 占 200MB+
- 220 个 Offer Rate 图片占 40MB
- 早期废弃 Python 脚本（fix_*.py, retry_*.py）
- api-server/ 和 email-service/ 两个无关目录（74MB）

**建议**：保留最近 5 个 data.vXX.json，其余 git rm（不实际执行，先列出方案等确认）

### 4.2 Mac mini 单点故障
- cloudflared 无 launchd 守护，重启后隧道断开
- uvicorn 无 launchd 守护，同上
- 数据库无定时备份

**建议**：写 launchd plist 加入守护进程（参考附录 A）

### 4.3 ECS 角色模糊
- ECS 服务在跑但只承担备份角色
- 数据库手动同步（依赖 export_data.py）
- 没有自动化兜底

**建议**：保留现状直到有明确需求

### 4.4 飞书附件传输断点
- 飞书 API 没有合适的下载凭证通道
- 5+ 次断点事故

**建议**：维持现状（"本地目录直读" 模式已稳定）

---

## 5. 附录 A: launchd plist 模板

### Mac mini uvicorn 守护

文件位置：`~/Library/LaunchAgents/com.cosmetic.api.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cosmetic.api</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/yuming.chen/.openclaw/workspace/cosmetic-api</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/cosmetic-api.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/cosmetic-api.error.log</string>
</dict>
</plist>
```

### Mac mini cloudflared 守护

文件位置：`~/Library/LaunchAgents/com.cloudflare.tunnel.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflare.tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
        <string>3479ca5e-467a-4227-b1a9-cf621d51cda6</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/cloudflared.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/cloudflared.error.log</string>
</dict>
</plist>
```

**加载命令**：
```bash
launchctl load ~/Library/LaunchAgents/com.cosmetic.api.plist
launchctl load ~/Library/LaunchAgents/com.cloudflare.tunnel.plist
```

**卸载命令**：
```bash
launchctl unload ~/Library/LaunchAgents/com.cosmetic.api.plist
launchctl unload ~/Library/LaunchAgents/com.cloudflare.tunnel.plist
```

---

## 6. 附录 B: 关键命令速查

| 任务 | 命令 |
|---|---|
| 启动 API（前台） | `cd ~/openclaw/workspace/cosmetic-deploy && python3 -m uvicorn api-server.main:app --host 0.0.0.0 --port 8000` |
| 启动隧道（前台） | `cloudflared tunnel run 3479ca5e-467a-4227-b1a9-cf621d51cda6` |
| 手动导出+同步 | `cd ~/openclaw/workspace/cosmetic-deploy && python3 export_data.py` |
| 手动同步 ECS | `bash ~/openclaw/workspace/cosmetic-deploy/api-server/sync_db_to_ecs.sh` |
| 检查 API 健康 | `curl https://api.cosmetic-search.com/api/health` |
| 检查网站 | `curl -o /dev/null -w '%{http_code}' https://www.cosmetic-search.com` |
| SSH ECS | `ssh root@8.133.238.76` （用 sshpass 或 key） |
| 重启 ECS 服务 | `ssh root@8.133.238.76 'systemctl restart cosmetic-api'` |
| 看 ECS 备份 | `ssh root@8.133.238.76 'ls -la /opt/cosmetic-api/data/'` |

---

## 7. 决策日志时间线

| 日期 | 决策 | 状态 |
|---|---|---|
| 2026-06-17 | v1.2 设计方案（关键词+摘要检索） | ✅ 落地 |
| 2026-07-02 | export_data.py 版本号自动递增 | ✅ |
| 2026-08-06 | 项目迁移到新电脑（精简打包 3.9MB） | ✅ |
| 2026-08-10 | 入库硬校验（标题/日期/白名单） | ✅ |
| 2026-08-17 | 红白品牌风视觉定稿 | ✅ |
| 2026-08-19 | 智能选文报告 + 定制化深度报告双功能 | ✅ |
| 2026-08-24 | 智能找文 API 上 FastAPI + SQLite | ✅ |
| 2026-08-26 | 意图锚定检索 + LLM 精排 | ✅ |
| 2026-08-27 | ⚠️ 后端 API 迁 ECS（数据库未同步成功） | ❌ 失败 |
| 2026-08-28 | Cloudflare 命名隧道 DNS 切换完成 | ✅ |
| 2026-09-01 | Offer Rate 网页发布上线 | ⚠️ 老板反馈待澄清 |
| 2026-09-10 | ECS 同步机制修复（sync_db_to_ecs.sh） | ✅ |
| 2026-09-10 | Mac mini uvicorn 关闭，API 主流量走 Mac mini + Cloudflare 隧道 | ✅ |
| 2026-09-10 | 移交文档（HANDOVER.md + ARCHITECTURE.md）发布 | ✅ |

---

**最后更新**：2026-09-10 by Nick & AI
