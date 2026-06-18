# 自动部署到 Vercel 指南

## 第一步：在 Vercel 创建项目（只需一次）

1. 访问 https://vercel.com/new
2. 导入 GitHub 仓库 `cosmetic-articles-search`
3. 点击 Deploy
4. 部署完成后，进入 Project Settings

## 第二步：获取 Vercel 配置信息

在 Vercel Project Settings → General 页面，找到：
- **Project ID** (例如：`prj_xxxxxxxx`)
- **Org ID** (在 Vercel Team 设置中找到，或个人用户ID)

## 第三步：在 GitHub 添加 Secrets

1. 访问 GitHub 仓库设置页面：
   ```
   https://github.com/benavidesbraian710-hub/cosmetic-articles-search/settings/secrets/actions
   ```

2. 点击 **New repository secret**，添加以下 3 个 secrets：

   | Name | Value | 获取方式 |
   |------|-------|----------|
   | `VERCEL_TOKEN` | 你的 Vercel Token | https://vercel.com/account/tokens |
   | `VERCEL_ORG_ID` | 你的 Vercel Org ID | Vercel Project Settings → General |
   | `VERCEL_PROJECT_ID` | 你的 Project ID | Vercel Project Settings → General |

### 获取 VERCEL_TOKEN：
1. 访问 https://vercel.com/account/tokens
2. 点击 **Create Token**
3. 输入名称：`github-actions`
4. 点击 **Create**
5. 复制 Token 值

## 第四步：完成！

添加完 3 个 secrets 后，每次推送代码到 GitHub 会自动部署到 Vercel。

## 手动触发部署

如果需要手动部署，可以在 GitHub 仓库页面：
1. 点击 **Actions** 标签
2. 选择 **Deploy to Vercel**
3. 点击 **Run workflow**

## 查看部署状态

- GitHub Actions: https://github.com/benavidesbraian710-hub/cosmetic-articles-search/actions
- Vercel Dashboard: https://vercel.com/dashboard
