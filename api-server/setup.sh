#!/bin/bash
# 阿里云ECS初始化脚本 - 由AI远程执行
# 用法：bash setup.sh

set -e

echo "=== 1. 安装系统依赖 ==="
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx git certbot python3-certbot-nginx

echo "=== 2. 创建API目录 ==="
mkdir -p /opt/cosmetic-api/data
cd /opt/cosmetic-api

echo "=== 3. 克隆代码（首次执行需手动 git clone，后续用 git pull） ==="
if [ ! -d ".git" ]; then
    git clone https://github.com/benavidesbraian710-hub/cosmetic-articles-search.git /tmp/repo
    cp -r /tmp/repo/api-server/* /opt/cosmetic-api/
    rm -rf /tmp/repo
else
    git pull
fi

echo "=== 4. 创建Python虚拟环境 ==="
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== 5. 下载数据库（从Mac mini推送或GitHub） ==="
if [ ! -f "/opt/cosmetic-api/data/cosmetic_articles.db" ]; then
    echo "⚠️ 数据库不存在，请运行 sync_db.sh 拉取"
    touch /opt/cosmetic-api/data/cosmetic_articles.db
fi

echo "=== 6. 安装systemd服务 ==="
cp cosmetic-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable cosmetic-api
systemctl restart cosmetic-api
systemctl status cosmetic-api --no-pager

echo "=== 7. 配置nginx ==="
cp nginx-api.conf /etc/nginx/sites-available/api.cosmetic-search.com
ln -sf /etc/nginx/sites-available/api.cosmetic-search.com /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

echo "=== 8. 申请HTTPS证书 ==="
certbot --nginx -d api.cosmetic-search.com --non-interactive --agree-tos -m nick@cosmetic-search.com || echo "⚠️ 证书申请失败，请稍后手动执行 certbot --nginx -d api.cosmetic-search.com"

echo "=== 9. 添加数据库同步定时任务 ==="
cat > /etc/cron.d/cosmetic-db-sync << 'EOF'
# 每小时从GitHub拉取最新数据库
0 * * * * www-data cd /opt/cosmetic-api/data && git -C /opt/cosmetic-api pull origin main && systemctl restart cosmetic-api
EOF
chmod 644 /etc/cron.d/cosmetic-db-sync

echo "✅ 部署完成！访问 https://api.cosmetic-search.com/api/health 验证"