# 🚀 Shifta ConoHa VPS デプロイガイド

## ワンクリックデプロイ手順

### 1. 必要な準備
- ConoHa VPSサーバー（Ubuntu 20.04以上推奨）
- SSHキー設定済み
- サーバーのIPアドレス

### 2. デプロイ実行

#### Windows PowerShell の場合:
```powershell
.\one-click-deploy.ps1 -ServerIP "あなたのサーバーIP"
```

#### Git Bash / WSL の場合:
```bash
chmod +x one-click-deploy.sh
./one-click-deploy.sh あなたのサーバーIP
```

### 3. 完了後のアクセス

- **メインサイト**: http://サーバーIP:8000/
- **管理画面**: http://サーバーIP:8000/admin/
- **管理者アカウント**: admin / shifta2025!

## 手動デプロイ手順

### Step 1: サーバー準備
```bash
# Dockerインストール
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose インストール
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# プロジェクトディレクトリ作成
sudo mkdir -p /var/www/shifta
sudo chown $USER:$USER /var/www/shifta
```

### Step 2: ファイル転送
```bash
# ローカルからサーバーへファイル転送
rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='staticfiles' \
    ./ root@サーバーIP:/var/www/shifta/
```

### Step 3: 環境変数設定
```bash
# サーバーで実行
cd /var/www/shifta

# 環境変数ファイル作成
cat > .env << EOF
SECRET_KEY=$(openssl rand -base64 50)
POSTGRES_PASSWORD=$(openssl rand -base64 32)
DEBUG=False
ALLOWED_HOSTS=mednext.jp,www.mednext.jp,localhost,127.0.0.1,サーバーIP
CSRF_TRUSTED_ORIGINS=https://mednext.jp,https://www.mednext.jp,http://サーバーIP:8000
SECURE_SSL_REDIRECT=False
SERVER_IP=サーバーIP
URL_PREFIX=
EOF
```

### Step 4: アプリケーション起動
```bash
# Docker コンテナ起動
docker-compose -f docker-compose.standalone.yml up -d --build

# データベースマイグレーション
docker-compose -f docker-compose.standalone.yml exec web python manage.py migrate

# 静的ファイル収集
docker-compose -f docker-compose.standalone.yml exec web python manage.py collectstatic --noinput

# 管理者ユーザー作成
docker-compose -f docker-compose.standalone.yml exec web python manage.py createsuperuser
```

## ドメイン設定（mednext.jp/shifta）

### 1. DNS設定
```
A レコード: mednext.jp → サーバーIP
A レコード: www.mednext.jp → サーバーIP
```

### 2. Traefik SSL設定（推奨）
```bash
# Traefik版で起動（SSL自動取得）
docker-compose -f docker-compose.production.yml up -d --build
```

### 3. Nginx リバースプロキシ設定
```nginx
server {
    listen 80;
    server_name mednext.jp www.mednext.jp;
    
    location /shifta/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## セキュリティ設定

### 1. ファイアウォール設定
```bash
# UFW設定
sudo ufw allow ssh
sudo ufw allow 8000
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

### 2. 管理者パスワード変更
```bash
# 管理画面から変更、またはコマンドで変更
docker-compose -f docker-compose.standalone.yml exec web python manage.py changepassword admin
```

### 3. 環境変数更新
```bash
# SECRET_KEY と POSTGRES_PASSWORD を本番環境用に更新
nano .env
docker-compose restart
```

## 運用・メンテナンス

### ログ確認
```bash
# アプリケーションログ
docker-compose logs web

# データベースログ
docker-compose logs postgres

# 全サービスログ
docker-compose logs
```

### バックアップ
```bash
# データベースバックアップ
docker-compose exec postgres pg_dump -U shifta_user shifta_db > backup_$(date +%Y%m%d).sql

# 静的ファイルバックアップ
tar -czf staticfiles_backup_$(date +%Y%m%d).tar.gz staticfiles/ media/
```

### アップデート
```bash
# 最新コードを取得
git pull origin main

# コンテナ再ビルド・再起動
docker-compose down
docker-compose up -d --build

# マイグレーション実行
docker-compose exec web python manage.py migrate
```

## トラブルシューティング

### 1. コンテナが起動しない
```bash
# ログ確認
docker-compose logs

# コンテナ状態確認
docker-compose ps

# 個別サービス再起動
docker-compose restart web
```

### 2. データベース接続エラー
```bash
# PostgreSQL ログ確認
docker-compose logs postgres

# データベース接続テスト
docker-compose exec web python manage.py dbshell
```

### 3. 静的ファイルが表示されない
```bash
# 静的ファイル再収集
docker-compose exec web python manage.py collectstatic --noinput

# Nginx 設定確認
docker-compose logs nginx
```

### 4. SSL証明書エラー
```bash
# Traefik ログ確認
docker-compose logs traefik

# Let's Encrypt 証明書状態確認
docker-compose exec traefik traefik version
```

## サポート

問題が発生した場合は以下を確認:

1. **サーバーリソース**: CPU、メモリ、ディスク容量
2. **ネットワーク**: ポート開放、DNS設定
3. **ログファイル**: エラーメッセージの詳細確認
4. **環境変数**: 設定値の確認

### ヘルスチェック URL
- アプリケーション: http://サーバーIP:8000/health/
- 管理画面: http://サーバーIP:8000/admin/
- API: http://サーバーIP:8000/api/
