#!/bin/bash
# one-click-deploy.sh - コノハVPS ワンクリックデプロイ

set -e

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Shifta ConoHa VPS ワンクリックデプロイ${NC}"
echo "================================================="

# 引数チェック
if [ $# -lt 1 ]; then
    echo -e "${RED}❌ 使用方法: $0 <サーバーIP> [ユーザー名]${NC}"
    echo "例: $0 123.456.789.0"
    echo "例: $0 123.456.789.0 ubuntu"
    exit 1
fi

SERVER_IP=$1
SERVER_USER=${2:-root}
PROJECT_DIR="/var/www/shifta"

echo -e "${YELLOW}📋 デプロイ設定:${NC}"
echo "  サーバーIP: $SERVER_IP"
echo "  ユーザー: $SERVER_USER"
echo "  プロジェクトディレクトリ: $PROJECT_DIR"
echo ""

# SSH接続テスト
echo -e "${BLUE}🔌 SSH接続テスト...${NC}"
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes $SERVER_USER@$SERVER_IP "echo 'SSH接続成功'" 2>/dev/null; then
    echo -e "${RED}❌ SSH接続に失敗しました${NC}"
    echo "   以下を確認してください:"
    echo "   1. SSHキーが正しく設定されているか"
    echo "   2. サーバーIPが正しいか"
    echo "   3. ユーザー名が正しいか"
    exit 1
fi
echo -e "${GREEN}✅ SSH接続成功${NC}"

# プロジェクトファイルの準備
echo -e "${BLUE}📦 プロジェクトファイル準備中...${NC}"

# 環境変数ファイル作成
cat > .env.deploy << EOF
# Auto-generated production environment
SECRET_KEY=$(openssl rand -base64 50 | tr -d "=" | tr "/" "_")
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=" | tr "/" "_")
DEBUG=False
ALLOWED_HOSTS=mednext.jp,www.mednext.jp,localhost,127.0.0.1,$SERVER_IP
CSRF_TRUSTED_ORIGINS=https://mednext.jp,https://www.mednext.jp,http://$SERVER_IP:8000
SECURE_SSL_REDIRECT=False
SERVER_IP=$SERVER_IP
URL_PREFIX=
EOF

echo -e "${GREEN}✅ 環境変数ファイル作成完了${NC}"

# ファイル転送
echo -e "${BLUE}📤 ファイル転送中...${NC}"
rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='staticfiles' \
    --exclude='media' \
    --exclude='logs' \
    --exclude='.env' \
    ./ $SERVER_USER@$SERVER_IP:$PROJECT_DIR/

# 環境変数ファイルも転送
scp .env.deploy $SERVER_USER@$SERVER_IP:$PROJECT_DIR/.env

echo -e "${GREEN}✅ ファイル転送完了${NC}"

# サーバーでのデプロイ実行
echo -e "${BLUE}🔧 サーバーでのデプロイ実行...${NC}"
ssh $SERVER_USER@$SERVER_IP << EOF
set -e

cd $PROJECT_DIR

echo "📂 ディレクトリ権限設定..."
sudo chown -R \$USER:\$USER $PROJECT_DIR
mkdir -p logs staticfiles media celerybeat-schedule
chmod 755 logs staticfiles media

# Dockerの確認・インストール
if ! command -v docker &> /dev/null; then
    echo "🐳 Docker インストール中..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker \$USER
    
    # Docker Compose インストール
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    
    echo "⚠️  Docker インストール完了。システム再起動後に再度実行してください。"
    exit 1
fi

# 既存コンテナ停止
echo "🛑 既存コンテナ停止中..."
docker-compose -f docker-compose.standalone.yml down || true

# 古いイメージ削除（容量節約）
echo "🧹 古いイメージクリーンアップ..."
docker image prune -f || true

# イメージビルド
echo "🔨 Dockerイメージビルド中..."
docker-compose -f docker-compose.standalone.yml build --no-cache

# コンテナ起動
echo "🚀 コンテナ起動中..."
docker-compose -f docker-compose.standalone.yml up -d

# ヘルスチェック待機
echo "⏳ サービス起動待機中..."
sleep 60

# データベースマイグレーション
echo "🗄️ データベースマイグレーション..."
docker-compose -f docker-compose.standalone.yml exec -T web python manage.py migrate

# 静的ファイル収集
echo "📁 静的ファイル収集..."
docker-compose -f docker-compose.standalone.yml exec -T web python manage.py collectstatic --noinput

# 管理者ユーザー作成
echo "👤 管理者ユーザー作成..."
docker-compose -f docker-compose.standalone.yml exec -T web python manage.py shell << 'PYTHON'
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@mednext.jp', 'shifta2025!')
    print('✅ 管理者ユーザー admin 作成完了（パスワード: shifta2025!）')
else:
    print('ℹ️  管理者ユーザー admin は既に存在します')
PYTHON

# 最終ステータス確認
echo "🔍 コンテナ状況確認..."
docker-compose -f docker-compose.standalone.yml ps

# ヘルスチェック
echo "🩺 ヘルスチェック..."
if curl -f http://localhost:8000/health/ &>/dev/null; then
    echo "✅ アプリケーション正常起動"
else
    echo "⚠️  ヘルスチェック失敗 - ログを確認してください"
    docker-compose -f docker-compose.standalone.yml logs web | tail -20
fi

echo ""
echo "🎉 デプロイ完了！"
echo "=================="
echo "🌐 アクセスURL:"
echo "   メインサイト: http://$SERVER_IP:8000/"
echo "   管理画面: http://$SERVER_IP:8000/admin/"
echo ""
echo "👤 管理者ログイン:"
echo "   ユーザー名: admin"
echo "   パスワード: shifta2025!"
echo ""
echo "📋 次の作業:"
echo "   1. ドメイン設定 (mednext.jp → $SERVER_IP)"
echo "   2. SSL証明書設定"
echo "   3. 管理者パスワード変更"
echo "   4. ファイアウォール設定"
EOF

# ローカルファイルクリーンアップ
rm -f .env.deploy

echo ""
echo -e "${GREEN}🎊 デプロイ完了！${NC}"
echo "================================="
echo -e "${YELLOW}🌐 アクセスURL:${NC}"
echo "   http://$SERVER_IP:8000/"
echo "   http://$SERVER_IP:8000/admin/"
echo ""
echo -e "${YELLOW}👤 管理者ログイン:${NC}"
echo "   ユーザー名: admin"
echo "   パスワード: shifta2025!"
echo ""
echo -e "${YELLOW}📋 次の作業:${NC}"
echo "   1. mednext.jp ドメインを $SERVER_IP に向ける"
echo "   2. SSL証明書の設定"
echo "   3. 管理者パスワードの変更"
echo "   4. ファイアウォール設定 (ポート 8000, 22)"

# ブラウザで開く（Windowsの場合）
if command -v cmd.exe &> /dev/null; then
    echo ""
    echo -e "${BLUE}🖥️  ブラウザでサイトを開きますか？ (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        cmd.exe /c start http://$SERVER_IP:8000/
    fi
fi
