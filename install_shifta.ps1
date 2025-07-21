# --- Shifta 自動構築スクリプト ---
# スマートフォン対応のシフト管理システム

# 1. プロジェクトフォルダの作成
$projectName = "shifta_project"
Write-Host "🚀 Shiftaプロジェクトの構築を開始します..." -ForegroundColor Green

# 既存のフォルダがある場合は削除確認
if (Test-Path $projectName) {
    $confirm = Read-Host "$projectName フォルダが既に存在します。削除して続行しますか？ (y/N)"
    if ($confirm -eq 'y' -or $confirm -eq 'Y') {
        Remove-Item -Recurse -Force $projectName
        Write-Host "✅ 既存フォルダを削除しました。" -ForegroundColor Yellow
    } else {
        Write-Host "❌ 処理を中断しました。" -ForegroundColor Red
        exit
    }
}

New-Item -ItemType Directory -Name $projectName
Set-Location $projectName
Write-Host "✅ プロジェクトフォルダ '$projectName' を作成しました。" -ForegroundColor Green

# 2. Python仮想環境の構築と有効化
Write-Host "📦 Python仮想環境を構築中..." -ForegroundColor Blue
python -m venv .venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python仮想環境の作成に失敗しました。Pythonがインストールされているか確認してください。" -ForegroundColor Red
    exit
}

# Windows PowerShellでの仮想環境有効化
& .\.venv\Scripts\Activate.ps1
Write-Host "✅ Python仮想環境を有効化しました。" -ForegroundColor Green

# 3. 必要なライブラリのインストール
Write-Host "📚 必要なライブラリをインストール中..." -ForegroundColor Blue
$packages = @(
    "django>=4.2.0",
    "psycopg2-binary",  # PostgreSQL用
    "pulp",             # 数理最適化
    "celery[redis]",    # 非同期タスク処理
    "redis",            # Redis接続
    "python-dotenv",    # 環境変数管理
    "pillow",           # 画像処理
    "whitenoise",       # 静的ファイル配信
    "gunicorn"          # 本番環境用サーバー
)

foreach ($package in $packages) {
    pip install $package
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ $package のインストールに失敗しました。" -ForegroundColor Red
        exit
    }
}
Write-Host "✅ 必要なライブラリをインストールしました。" -ForegroundColor Green

# 4. Djangoプロジェクトとアプリケーションの作成
Write-Host "🏗️ Djangoプロジェクトを作成中..." -ForegroundColor Blue
django-admin startproject shifta .
python manage.py startapp schedule
Write-Host "✅ Djangoプロジェクトと'schedule'アプリを作成しました。" -ForegroundColor Green

# 5. プロジェクト設定ファイルの更新
Write-Host "⚙️ Djangoの設定を更新中..." -ForegroundColor Blue
$settings_content = @"
"""
Django settings for shifta project.
スマートフォン対応のシフト管理システム
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Security settings
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-development-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'schedule',  # Shiftaのメインアプリケーション
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # 静的ファイル配信
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
        'DIRS': [],
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

# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# カスタムユーザーモデル
AUTH_USER_MODEL = 'schedule.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'ja'
TIME_ZONE = 'Asia/Tokyo'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configuration (非同期タスク処理)
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'shifta.log',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'schedule': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Security settings for production
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_REDIRECT_EXEMPT = []
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
"@

$settings_content | Out-File -FilePath ".\shifta\settings.py" -Encoding utf8
Write-Host "✅ Django設定ファイルを更新しました。" -ForegroundColor Green

# 6. 環境変数ファイルの作成
$env_content = @"
# Shifta Environment Variables
DJANGO_SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
REDIS_URL=redis://localhost:6379/0
"@

$env_content | Out-File -FilePath ".\.env" -Encoding utf8
Write-Host "✅ 環境変数ファイル(.env)を作成しました。" -ForegroundColor Green

# 7. Celery設定ファイルの作成
$celery_content = @"
# shifta/celery.py
import os
from celery import Celery

# Django設定モジュールを指定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shifta.settings')

app = Celery('shifta')

# Django設定からCelery設定を読み込み
app.config_from_object('django.conf:settings', namespace='CELERY')

# 登録されたDjangoアプリのタスクを自動検出
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
"@

$celery_content | Out-File -FilePath ".\shifta\celery.py" -Encoding utf8

# 8. __init__.pyファイルの更新
$init_content = @"
# shifta/__init__.py
from .celery import app as celery_app

__all__ = ('celery_app',)
"@

$init_content | Out-File -FilePath ".\shifta\__init__.py" -Encoding utf8
Write-Host "✅ Celery設定を追加しました。" -ForegroundColor Green

Write-Host "🎉 Shiftaプロジェクトの基盤構築が完了しました！" -ForegroundColor Green
Write-Host ""
Write-Host "📋 次のステップ:" -ForegroundColor Yellow
Write-Host "  1. models.pyファイルを配置します"
Write-Host "  2. テンプレートファイルを作成します"
Write-Host "  3. ビューファイルを設定します"
Write-Host ""
