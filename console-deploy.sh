#!/bin/bash
# console-deploy.sh - ConoHa VPSコンソール用デプロイスクリプト

set -e

echo "🚀 Shifta ConoHa VPS コンソールデプロイ"
echo "========================================"

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}📋 このスクリプトをConoHa VPSコンソールで実行してください${NC}"
echo ""

# プロジェクトディレクトリ作成
echo -e "${BLUE}📂 プロジェクトディレクトリ作成...${NC}"
PROJECT_DIR="/var/www/shifta"
sudo mkdir -p $PROJECT_DIR
sudo chown $USER:$USER $PROJECT_DIR
cd $PROJECT_DIR

# システム更新
echo -e "${BLUE}📦 システム更新...${NC}"
sudo apt update
sudo apt install -y curl wget git unzip

# Dockerインストール
if ! command -v docker &> /dev/null; then
    echo -e "${BLUE}🐳 Docker インストール...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    
    # Docker Compose インストール
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    
    echo -e "${GREEN}✅ Docker インストール完了${NC}"
else
    echo -e "${GREEN}✅ Docker は既にインストール済み${NC}"
fi

# Githubからプロジェクト取得
echo -e "${BLUE}📥 プロジェクトファイル取得...${NC}"
if [ -d ".git" ]; then
    echo -e "${YELLOW}既存のGitリポジトリを更新...${NC}"
    git pull origin main
else
    echo -e "${YELLOW}Githubからクローン...${NC}"
    git clone https://github.com/minatoman/shifta-shift-management.git .
fi

# 環境変数ファイル作成
echo -e "${BLUE}⚙️ 環境変数設定...${NC}"
SECRET_KEY=$(openssl rand -base64 50 | tr -d "=" | tr "/" "_")
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=" | tr "/" "_")

cat > .env << EOF
# Auto-generated production environment
SECRET_KEY=$SECRET_KEY
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
DEBUG=False
ALLOWED_HOSTS=mednext.jp,www.mednext.jp,localhost,127.0.0.1,160.251.181.238
CSRF_TRUSTED_ORIGINS=https://mednext.jp,https://www.mednext.jp,http://160.251.181.238:8000
SECURE_SSL_REDIRECT=False
SERVER_IP=160.251.181.238
URL_PREFIX=
EOF

echo -e "${GREEN}✅ 環境変数ファイル作成完了${NC}"

# ディレクトリ作成
echo -e "${BLUE}📁 必要ディレクトリ作成...${NC}"
mkdir -p logs staticfiles media celerybeat-schedule
chmod 755 logs staticfiles media

# 既存コンテナ停止
echo -e "${BLUE}🛑 既存コンテナ停止...${NC}"
docker-compose -f docker-compose.standalone.yml down || true

# 古いイメージ削除
echo -e "${BLUE}🧹 古いイメージクリーンアップ...${NC}"
docker image prune -f || true

# イメージビルド
echo -e "${BLUE}🔨 Dockerイメージビルド...${NC}"
docker-compose -f docker-compose.standalone.yml build --no-cache

# コンテナ起動
echo -e "${BLUE}🚀 コンテナ起動...${NC}"
docker-compose -f docker-compose.standalone.yml up -d

# ヘルスチェック待機
echo -e "${BLUE}⏳ サービス起動待機...${NC}"
sleep 60

# データベースマイグレーション
echo -e "${BLUE}🗄️ データベースマイグレーション...${NC}"
docker-compose -f docker-compose.standalone.yml exec -T web python manage.py migrate

# 静的ファイル収集
echo -e "${BLUE}📁 静的ファイル収集...${NC}"
docker-compose -f docker-compose.standalone.yml exec -T web python manage.py collectstatic --noinput

# 管理者ユーザー作成
echo -e "${BLUE}👤 管理者ユーザー作成...${NC}"
docker-compose -f docker-compose.standalone.yml exec -T web python manage.py shell << 'PYTHON'
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@mednext.jp', 'shifta2025!')
    print('✅ 管理者ユーザー admin 作成完了（パスワード: shifta2025!）')
else:
    print('ℹ️  管理者ユーザー admin は既に存在します')
PYTHON

# 最終ステータス確認
echo -e "${BLUE}🔍 コンテナ状況確認...${NC}"
docker-compose -f docker-compose.standalone.yml ps

# ヘルスチェック
echo -e "${BLUE}🩺 ヘルスチェック...${NC}"
if curl -f http://localhost:8000/health/ &>/dev/null; then
    echo -e "${GREEN}✅ アプリケーション正常起動${NC}"
else
    echo -e "${YELLOW}⚠️  ヘルスチェック失敗 - ログを確認中...${NC}"
    docker-compose -f docker-compose.standalone.yml logs web | tail -20
fi

echo ""
echo -e "${GREEN}🎉 デプロイ完了！${NC}"
echo "=================="
echo -e "${YELLOW}🌐 アクセスURL:${NC}"
echo "   メインサイト: http://160.251.181.238:8000/"
echo "   管理画面: http://160.251.181.238:8000/admin/"
echo ""
echo -e "${YELLOW}👤 管理者ログイン:${NC}"
echo "   ユーザー名: admin"
echo "   パスワード: shifta2025!"
echo ""
echo -e "${YELLOW}📋 次の作業:${NC}"
echo "   1. ブラウザでアクセス確認"
echo "   2. SSL証明書設定（必要に応じて）"
echo "   3. 管理者パスワード変更"
echo "   4. ファイアウォール設定確認"

# ファイアウォール設定
echo -e "${BLUE}🔥 ファイアウォール設定...${NC}"
sudo ufw allow ssh
sudo ufw allow 8000
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

echo -e "${GREEN}🎊 全ての設定が完了しました！${NC}"
