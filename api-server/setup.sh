#!/bin/bash
# 阿里云ECS初始化脚本 - 一键部署 FastAPI + nginx + HTTPS
# 用法：bash setup.sh

set -e

REPO_URL="https://github.com/benavidesbraian710-hub/cosmetic-articles-search.git"
BRANCH="feature/new-arch"
APP_DIR="/opt/cosmetic-api"
DOMAIN="api.cosmetic-search.com"

echo "=== 1. 安装系统依赖 ==="
apt update -y
apt install -y python3 python3-pip python3-venv nginx git certbot python3-certbot-nginx curl

echo "=== 2. 创建API目录 ==="
mkdir -p $APP_DIR/data
cd $APP_DIR

echo "=== 3. 克隆代码 ==="
if [ ! -d ".git" ]; then
    git clone -b $BRANCH $REPO_URL /tmp/cosrepo
    cp -r /tmp/cosrepo/api-server/* $APP_DIR/
    rm -rf /tmp/cosrepo
else
    git pull origin $BRANCH
    # 重新同步代码
    git clone -b $BRANCH $REPO_URL /tmp/cosrepo
    cp -r /tmp/cosrepo/api-server/* $APP_DIR/
    rm -rf /tmp/cosrepo
fi

echo "=== 4. 创建Python虚拟环境 ==="
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "=== 5. 数据库（首次需从 Mac mini 推送） ==="
if [ ! -s "$APP_DIR/data/cosmetic_articles.db" ]; then
    echo "⚠️ 数据库为空，先创建空库占位（待 Mac mini 推送）"
    touch $APP_DIR/data/cosmetic_articles.db
    sqlite3 $APP_DIR/data/cosmetic_articles.db "CREATE TABLE IF NOT EXISTS articles (id INTEGER PRIMARY KEY);"
fi
chown -R www-data:www-data $APP_DIR

echo "=== 6. systemd 服务 ==="
cp $APP_DIR/cosmetic-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable cosmetic-api
systemctl restart cosmetic-api
sleep 2
systemctl status cosmetic-api --no-pager | head -5

echo "=== 7. nginx 配置 ==="
cp $APP_DIR/nginx-api.conf /etc/nginx/sites-available/$DOMAIN
ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "=== 8. HTTPS 证书 ==="
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@cosmetic-search.com || {
    echo "⚠️ 证书申请失败，请先在阿里云DNS添加 api A 记录指向本机IP后重试"
    echo "跳过HTTPS，仅HTTP可用"
}

echo "=== 9. 数据库自动同步（Git方式） ==="
cat > /etc/cron.d/cosmetic-db-sync << 'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# 每小时从 GitHub 拉取最新代码（含数据库从 Mac mini 推送）
0 * * * * root cd /opt/cosmetic-api && /usr/bin/git pull origin feature/new-arch >/var/log/cosmetic-pull.log 2>&1 && systemctl restart cosmetic-api
EOF
chmod 644 /etc/cron.d/cosmetic-db-sync

echo ""
echo "✅ 部署完成！"
echo ""
echo "下一步："
echo "  1. 阿里云DNS添加 api.cosmetic-search.com A 记录 → 本机公网IP"
echo "  2. 验证：curl http://api.cosmetic-search.com/api/health"
echo "  3. Mac mini 侧：数据库推送脚本（后续配置）"