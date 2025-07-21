#!/bin/bash
# direct-deploy.sh - GitHub不要の直接デプロイスクリプト

set -e

echo "🚀 Shifta 直接デプロイ（GitHub不要版）"
echo "========================================"

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# プロジェクトディレクトリ作成
echo -e "${BLUE}📂 プロジェクトディレクトリ作成...${NC}"
PROJECT_DIR="/var/www/shifta"
sudo mkdir -p $PROJECT_DIR
sudo chown $USER:$USER $PROJECT_DIR
cd $PROJECT_DIR

# システム更新
echo -e "${BLUE}📦 システム更新...${NC}"
sudo apt update
sudo apt install -y curl wget git unzip build-essential

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
    echo -e "${YELLOW}⚠️  Docker グループ設定のため、一度ログアウト・ログインが必要です${NC}"
    echo -e "${YELLOW}   再ログイン後、このスクリプトを再実行してください${NC}"
    exit 0
else
    echo -e "${GREEN}✅ Docker は既にインストール済み${NC}"
fi

# 基本ファイル作成
echo -e "${BLUE}📝 基本ファイル作成...${NC}"

# Dockerfile作成
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

# 作業ディレクトリ設定
WORKDIR /app

# システムパッケージインストール
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pythonパッケージインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコピー
COPY . .

# 静的ファイル・メディアディレクトリ作成
RUN mkdir -p /app/staticfiles /app/media /app/logs

# ポート公開
EXPOSE 8000

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# 起動コマンド
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
EOF

# requirements.txt作成
cat > requirements.txt << 'EOF'
Django==4.2.16
psycopg2-binary==2.9.9
redis==5.0.1
celery==5.3.4
django-celery-beat==2.5.0
django-redis==5.4.0
python-dotenv==1.0.0
gunicorn==21.2.0
whitenoise==6.6.0
Pillow==10.1.0
djangorestframework==3.14.0
django-cors-headers==4.3.1
django-extensions==3.2.3
EOF

# docker-compose.standalone.yml作成
cat > docker-compose.standalone.yml << 'EOF'
# docker-compose.standalone.yml - 簡易デプロイ用

services:
  # PostgreSQL データベース
  db:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_DB: shifta_db
      POSTGRES_USER: shifta_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-shifta_secure_pass456}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - shifta_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U shifta_user -d shifta_db"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Redis (キャッシュ・Celery用)
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - shifta_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Shifta Webアプリケーション
  web:
    build: .
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - DEBUG=False
      - ALLOWED_HOSTS=mednext.jp,www.mednext.jp,localhost,127.0.0.1,160.251.181.238
      - DATABASE_URL=postgresql://shifta_user:${POSTGRES_PASSWORD:-shifta_secure_pass456}@db:5432/shifta_db
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY:-your-very-secure-secret-key-change-in-production}
      - CSRF_TRUSTED_ORIGINS=https://mednext.jp,https://www.mednext.jp,http://160.251.181.238:8000
      - SECURE_SSL_REDIRECT=False
    volumes:
      - ./staticfiles:/app/staticfiles
      - ./media:/app/media
      - ./logs:/app/logs
    networks:
      - shifta_network
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Celery Worker
  celery:
    build: .
    restart: unless-stopped
    command: celery -A shifta worker -l info
    environment:
      - DEBUG=False
      - DATABASE_URL=postgresql://shifta_user:${POSTGRES_PASSWORD:-shifta_secure_pass456}@db:5432/shifta_db
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY:-your-very-secure-secret-key-change-in-production}
    volumes:
      - ./logs:/app/logs
    networks:
      - shifta_network
    depends_on:
      - db
      - redis

  # Celery Beat
  celery-beat:
    build: .
    restart: unless-stopped
    command: celery -A shifta beat -l info
    environment:
      - DEBUG=False
      - DATABASE_URL=postgresql://shifta_user:${POSTGRES_PASSWORD:-shifta_secure_pass456}@db:5432/shifta_db
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY:-your-very-secure-secret-key-change-in-production}
    volumes:
      - ./logs:/app/logs
      - ./celerybeat-schedule:/app/celerybeat-schedule
    networks:
      - shifta_network
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
  redis_data:

networks:
  shifta_network:
    driver: bridge
EOF

# 基本Django設定ファイル作成
mkdir -p shifta
cat > shifta/__init__.py << 'EOF'
EOF

cat > shifta/settings.py << 'EOF'
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'django_celery_beat',
    'shifts',
    'employees',
    'facilities',
    'schedules',
    'notifications',
    'analytics',
    'ai_optimization',
    'user_management',
    'mobile_ui',
    'external_integrations',
    'audit_logs',
    'reports',
    'settings_config',
    'health_monitoring',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'shifta.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'shifta.wsgi.application'

DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    import dj_database_url
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'shifta_db',
            'USER': 'shifta_user',
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'shifta_pass'),
            'HOST': 'db',
            'PORT': '5432',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ja'
TIME_ZONE = 'Asia/Tokyo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redis設定
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
    }
}

# Celery設定
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = TIME_ZONE

# セキュリティ設定
if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False').lower() == 'true'
    CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    
# CORS設定
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    "https://mednext.jp",
    "https://www.mednext.jp",
    "http://160.251.181.238:8000",
]

# ログ設定
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'shifta.log',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
EOF

cat > shifta/urls.py << 'EOF'
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({'status': 'healthy', 'service': 'shifta'})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check),
    path('api/', include('api.urls')),
    path('', include('shifts.urls')),
]
EOF

cat > shifta/wsgi.py << 'EOF'
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shifta.settings')
application = get_wsgi_application()
EOF

cat > shifta/celery.py << 'EOF'
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shifta.settings')

app = Celery('shifta')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
EOF

cat > manage.py << 'EOF'
#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shifta.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)
EOF
chmod +x manage.py

# 基本アプリ作成
for app in shifts employees facilities schedules notifications analytics ai_optimization user_management mobile_ui external_integrations audit_logs reports settings_config health_monitoring api; do
    echo -e "${YELLOW}📱 $app アプリ作成...${NC}"
    mkdir -p $app
    cat > $app/__init__.py << 'EOF'
EOF
    cat > $app/models.py << 'EOF'
from django.db import models

# 基本モデルはここに追加
EOF
    cat > $app/views.py << 'EOF'
from django.shortcuts import render
from django.http import JsonResponse

def index(request):
    return JsonResponse({'message': f'{__name__.split(".")[0]} module is working'})
EOF
    cat > $app/urls.py << 'EOF'
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
]
EOF
    cat > $app/admin.py << 'EOF'
from django.contrib import admin

# Register your models here.
EOF
    cat > $app/apps.py << EOF
from django.apps import AppConfig

class ${app^}Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = '$app'
EOF
done

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
mkdir -p logs staticfiles media celerybeat-schedule templates
chmod 755 logs staticfiles media

# requirements.txtにdj-database-url追加
echo "dj-database-url==2.1.0" >> requirements.txt

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
sleep 10
if curl -f http://localhost:8000/health/ &>/dev/null; then
    echo -e "${GREEN}✅ アプリケーション正常起動${NC}"
else
    echo -e "${YELLOW}⚠️  ヘルスチェック失敗 - ログを確認中...${NC}"
    docker-compose -f docker-compose.standalone.yml logs web | tail -20
fi

# ファイアウォール設定
echo -e "${BLUE}🔥 ファイアウォール設定...${NC}"
sudo ufw allow ssh
sudo ufw allow 8000
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

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

echo -e "${GREEN}🎊 全ての設定が完了しました！${NC}"
