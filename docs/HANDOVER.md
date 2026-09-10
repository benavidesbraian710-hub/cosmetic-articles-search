# 项目移交手册（Project Handover Guide）

> 本文档面向接手本项目的开发者。读完本文档，你应该能：
> 1. 理解项目的当前架构
> 2. 在新电脑上重新部署整套系统
> 3. 知道日常运维怎么做
> 4. 知道哪里有坑，避免重复踩

---

## 0. 项目一句话

**化妆品行业公众号聚合网站**：每天自动采集 18 个公众号的文章，存到数据库，前端用纯静态页展示给用户。后端 API 提供智能找文（语义搜索 + LLM 精排）。

| 项 | 内容 |
|---|---|
| 主站 | https://www.cosmetic-search.com |
| 智能找文 API | https://api.cosmetic-search.com |
| 数据量 | 1717 篇文章 / 18 个公众号（2026-09-10） |
| 代码仓库 | https://github.com/benavidesbraian710-hub/cosmetic-articles-search |
| 最后移交日期 | 2026-09-10 |

---

## 1. 需要交接的账号和凭证

接手者需要拿到这些东西（建议用密码管理器归档）：

### 必须有的

| 账号 | 用途 | 备注 |
|---|---|---|
| **GitHub 账号** | 代码仓库推送权限（`benavidesbraian710-hub/cosmetic-articles-search`） | 需要 SSH key 或 PAT |
| **Vercel 账号** | 主站部署（连 GitHub 自动部署） | 域名 `cosmetic-search.com` 已绑定 |
| **Cloudflare 账号** | 隧道 `3479ca5e-467a-4227-b1a9-cf621d51cda6` | 隧道 ID 已硬编码 |
| **阿里云 DNS** | 域名 `cosmetic-search.com` | NS 服务器已切到 Cloudflare |
| **ECS 服务器** | IP `8.133.238.76`，root 账号 | SSH 密码或 key |

### Mac mini 上的本地文件

| 文件 | 路径 | 用途 |
|---|---|---|
| 数据库 | `~/openclaw/workspace/cosmetic-deploy/cosmetic_articles.db` | 31MB，核心数据 |
| 隧道配置 | `~/.cloudflared/config.yml` | 隧道入口规则 |
| 隧道凭据 | `~/.cloudflared/3479ca5e-...json` | Cloudflare 认证 |
| GitHub SSH key | `~/.ssh/id_rsa` | 代码推送 |
| ECS 凭据 | 脚本里硬编码 `sshpass -p 'Clarins202020'` | 不安全，建议改 SSH key |

---

## 2. 当前架构（2026-09-10）

```
用户浏览器
    │
    ├─── www.cosmetic-search.com ──→ Vercel CDN ──→ GitHub 仓库
    │                                                       │
    │                                                       │ (git push 自动部署)
    │                                                       ▼
    │                                                Mac mini (本地仓库)
    │                                                       │
    │                                                       │ export_data.py
    │                                                       ▼
    │                                                data.vXX.json (3.1MB)
    │                                                       │
    └─── api.cosmetic-search.com ──→ Cloudflare 隧道 ────→ Mac mini uvicorn
                                              │                │
                                              │                ├─→ cosmetic_articles.db
                                              │                └─→ LLM 精排 (Kimi K3)
                                              │
                                              └─→ (失败时 fallback 到 ECS:443)
                                                 ECS FastAPI (备用，数据可能陈旧)
```

### 各组件清单

| 组件 | 跑在哪里 | 状态 |
|---|---|---|
| 前端静态网站 | Vercel CDN | ✅ |
| 后端 API | Mac mini uvicorn + Cloudflare 隧道 | ✅（主） |
| 后端备用 API | ECS FastAPI (8.133.238.76:443) | ⚠️ 数据可能陈旧 |
| 数据库 | Mac mini SQLite (`cosmetic_articles.db`) | ✅ |
| 隧道客户端 | Mac mini cloudflared | ⚠️ 无 launchd 守护，重启后需手动启动 |
| 代码仓库 | GitHub（main + feature/new-arch 两个分支） | ✅ |

---

## 3. 日常运维 SOP

### 3.1 数据采集入库（每天一次）

**触发条件**：Nick 或老板从飞书发送 Excel 文件（公众号文章链接列表）

**执行步骤**（AI 自动完成）：

```
1. 读取飞书附件（本地 inbound 目录）
2. 合并多个 Excel → 去重
3. 与数据库比对 → 确认净新增文章
4. 批量抓取文章正文（requests + 手机 UA）
5. 字段校验：标题非空、日期 YYYY-MM-DD、白名单公众号
6. 入库 cosmetic_articles.db
7. 跑 export_data.py → 自动同步 ECS
8. git commit + push → Vercel 自动部署
9. 汇报：净增 X 篇 → vXX → 1717 篇
```

**手动触发**（紧急情况）：
```bash
cd ~/openclaw/workspace/cosmetic-deploy
python3 export_data.py  # 手动重新导出+同步
```

### 3.2 数据同步 ECS

**自动化**：每次 `export_data.py` 运行后会**自动**调用 `api-server/sync_db_to_ecs.sh`，无需手动操作。

**手动触发**（同步失败时）：
```bash
bash ~/openclaw/workspace/cosmetic-deploy/api-server/sync_db_to_ecs.sh
```

**预期输出**：
```
📦 本地数据库: 1717 篇
📤 传输到 ECS
🔄 备份旧库 + 替换 + 重启服务
🔍 验证: 本地 1717 = ECS 1717
✅ 同步成功
```

### 3.3 检查智能找文是否正常

```bash
# 1. 健康检查
curl https://api.cosmetic-search.com/api/health
# 预期: {"status":"ok","timestamp":"..."}

# 2. 统计检查
curl https://api.cosmetic-search.com/api/stats
# 预期: total_articles >= 1700, date_range.end 是最近日期

# 3. 实际搜索
curl -X POST https://api.cosmetic-search.com/api/search \
    -H 'Content-Type: application/json' \
    -d '{"query":"抗衰老","limit":3}'
```

### 3.4 检查网站是否正常

```bash
curl -o /dev/null -w '%{http_code}\n' https://www.cosmetic-search.com
# 预期: 200

curl -sS https://www.cosmetic-search.com/stats.json | python3 -m json.tool
# 预期: stats.total_articles >= 1700
```

---

## 4. 新电脑部署步骤（迁移手册）

### Step 1: 安装基础环境

```bash
# macOS 用 Homebrew
brew install python@3.9
brew install cloudflared
brew install sshpass  # 用于 ECS SSH（不安全，建议改 SSH key）

# Python 依赖
pip3 install openpyxl requests fastapi uvicorn pydantic
```

### Step 2: 复制项目代码

```bash
# 从 GitHub 克隆
git clone git@github.com:benavidesbraian710-hub/cosmetic-articles-search.git \
    ~/openclaw/workspace/cosmetic-deploy

# 把数据库复制过去（从旧电脑）
scp old-mac:~/openclaw/workspace/cosmetic-deploy/cosmetic_articles.db \
    ~/openclaw/workspace/cosmetic-deploy/
```

### Step 3: 配置 Cloudflare 隧道

```bash
# 创建配置目录
mkdir -p ~/.cloudflared

# 复制隧道配置和凭据
scp old-mac:~/.cloudflared/config.yml ~/.cloudflared/
scp old-mac:~/.cloudflared/3479ca5e-*.json ~/.cloudflared/
scp old-mac:~/.cloudflared/cert.pem ~/.cloudflared/

# 验证隧道连接
cloudflared tunnel info 3479ca5e-467a-4227-b1a9-cf621d51cda6
```

### Step 4: 启动后端 API

```bash
# 前台启动（调试用）
cd ~/openclaw/workspace/cosmetic-deploy
python3 -m uvicorn api-server.main:app --host 0.0.0.0 --port 8000

# 后台启动 + launchd 守护（生产用）
# 创建 ~/Library/LaunchAgents/com.cosmetic.api.plist
# 内容参考 docs/ARCHITECTURE.md 附录
launchctl load ~/Library/LaunchAgents/com.cosmetic.api.plist
```

### Step 5: 启动隧道客户端

```bash
# 前台启动（调试用）
cloudflared tunnel run 3479ca5e-467a-4227-b1a9-cf621d51cda6

# 后台启动 + launchd 守护（生产用）
# 创建 ~/Library/LaunchAgents/com.cloudflare.tunnel.plist
launchctl load ~/Library/LaunchAgents/com.cloudflare.tunnel.plist
```

### Step 6: 验证

```bash
# 1. API 健康
curl https://api.cosmetic-search.com/api/health
# 预期: 200

# 2. 网站首页
curl -o /dev/null -w '%{http_code}\n' https://www.cosmetic-search.com
# 预期: 200

# 3. 数据库条数
python3 -c "
import sqlite3
db = sqlite3.connect('~/openclaw/workspace/cosmetic-deploy/cosmetic_articles.db')
cur = db.cursor()
cur.execute('SELECT COUNT(*) FROM articles')
print('文章数:', cur.fetchone()[0])
"

# 4. ECS 同步
bash ~/openclaw/workspace/cosmetic-deploy/api-server/sync_db_to_ecs.sh
# 预期: 同步成功
```

---

## 5. 已知问题和坑

### 5.1 飞书附件传输断点

**问题**：通过飞书发送的 Excel 文件经常传输失败（断点 5 次以上）。

**临时方案**：Nick 或 AI 把文件直接放到 Mac mini 桌面或 `/Users/yuming.chen/.openclaw/media/inbound/` 目录。

**根因未解**：飞书 API 没有合适的下载凭证通道。

### 5.2 数据版本号硬编码顽疾

**问题**：`stats.json?` 等静态文件用版本号 `?v=YYYYMMDD` 强制刷新，但**多处 HTML 仍硬编码旧版本号**，浏览器缓存导致用户看不到最新数据。

**临时方案**：每次 `export_data.py` 会自动更新所有 HTML 文件中的版本号。

**根治方案**：见 ARCHITECTURE.md 第 3 节。

### 5.3 反爬拦截

**问题**：微信对数据中心 IP 有频率限制，每批入库总有 1-3 篇文章被抓取失败（反爬 418/403）。

**临时方案**：换手机版 User-Agent 重新抓取（成功率高）。

**根治方案**：未实施。建议接入付费代理池或微信官方 API。

### 5.4 历史 data.vXX.json 文件膨胀

**问题**：57 个历史 data.vXX.json 文件累积 ~200MB，占仓库 80%+ 体积。

**临时方案**：当前保留，未来清理。

**根治方案**：见 ARCHITECTURE.md 第 4 节。

---

## 6. 紧急联系 / 故障恢复

### 智能找文 530 错误
1. 检查 Mac mini 上 uvicorn 是否在跑：`lsof -nP -iTCP:8000 -sTCP:LISTEN`
2. 如果没跑：手动启动 `python3 -m uvicorn api-server.main:app --host 0.0.0.0 --port 8000`
3. 检查 cloudflared：`cloudflared tunnel info 3479ca5e-...`
4. 重启隧道：`pkill cloudflared; cloudflared tunnel run 3479ca5e-... &`

### 网站打不开
1. 看 Vercel Dashboard 部署日志
2. 检查 GitHub 最近 commit 是否 push 成功
3. 看 `stats.json` 是否能直接访问

### 数据库不同步
1. 手动跑：`bash api-server/sync_db_to_ecs.sh`
2. 检查 ECS 是否可 SSH：`ssh root@8.133.238.76`
3. 看 ECS 服务状态：`ssh root@8.133.238.76 'systemctl status cosmetic-api'`

---

## 7. 后续待办（移交时已知未完成的）

1. ⚠️ Mac mini 的 cloudflared 没 launchd 守护 → 电脑重启后隧道会断
2. ⚠️ Mac mini 的 uvicorn 没 launchd 守护 → 同上
3. ⚠️ ECS 数据库同步只有手动/入库触发，没有定时兜底
4. ⚠️ 飞书定时推送 `cosmetic-site-monitor` 飞书权限缺失，每天报告发不出去
5. ⚠️ GitHub 仓库 232MB，需清理历史 data.vXX.json
6. ⚠️ 老板对 Offer Rate 页面"好像不是这个主页"的反馈待澄清

---

## 8. 文档索引

| 文档 | 内容 |
|---|---|
| `docs/HANDOVER.md`（本文）| 移交手册 + 迁移步骤 + 日常运维 |
| `docs/ARCHITECTURE.md` | 架构图 + 决策记录 + ECS 教训 |
| `docs/ISSUES.md` | 历史问题清单 |
| `README.md` | 项目入口 |
| `CHANGELOG.md` | 变更日志 |
| `化妆品文章智能检索系统_设计文档_v3.2.md` | 智能找文设计文档 |

---

**最后更新**：2026-09-10 by Nick & AI
