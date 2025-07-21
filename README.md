# Shifta - スマートフォン対応シフト管理システム

## 概要
Shiftaは、スマートフォンでの使いやすさを重視したシフト管理システムです。AI（数理最適化）を活用した自動シフト作成機能、スタッフ用モバイルインターフェース、管理者用PC管理画面を提供します。

## 主な機能

### スタッフ向け機能（スマートフォン最適化）
- **シフト希望提出**: タップ操作で簡単に希望を入力
- **マイスケジュール表示**: カレンダー/リスト表示の切り替え
- **休暇残数確認**: 有給休暇などの残数をリアルタイム表示
- **プロフィール管理**: 勤務条件や連絡先の更新
- **プッシュ通知**: 締切やスケジュール変更の通知

### 管理者向け機能（PC最適化）
- **AIシフト自動作成**: 数理最適化による最適なシフト生成
- **リアルタイム調整**: ドラッグ&ドロップでの直感的編集
- **スタッフ管理**: 勤務条件、能力評価の管理
- **レポート機能**: 勤務統計、コスト分析
- **システム設定**: 勤務パターン、休日設定の管理

### AI最適化機能
- **制約条件対応**: 最小人数、連続勤務制限など
- **スタッフ希望重視**: 希望度に基づく重み付け最適化
- **学習機能**: 過去の調整パターンから最適化改善
- **競合解決**: 希望が重複した場合の自動調整

## 技術スタック
- **Backend**: Django 4.2+, Python 3.8+
- **Frontend**: Bootstrap 5.3, JavaScript ES6+
- **Database**: PostgreSQL / SQLite
- **AI/Optimization**: PuLP（線形計画法）
- **Async Tasks**: Celery + Redis
- **Mobile**: Progressive Web App (PWA)

## クイックスタート

### 1. 自動インストール（推奨）
```powershell
# PowerShellで実行
.\install_shifta.ps1
```

### 2. 手動インストール
```bash
# 1. 仮想環境の作成
python -m venv shifta_env

# 2. 仮想環境の有効化（Windows）
shifta_env\Scripts\activate

# 3. 依存関係のインストール
pip install django>=4.2
pip install psycopg2-binary
pip install pulp
pip install celery[redis]
pip install django-crispy-forms
pip install pillow
pip install openpyxl
pip install reportlab

# 4. Djangoプロジェクトの作成
django-admin startproject shifta
cd shifta

# 5. アプリケーションの作成
python manage.py startapp schedule

# 6. 提供されたファイルをコピー
# - models.py → schedule/models.py
# - views.py → schedule/views.py
# - urls.py → schedule/urls.py
# - ai_scheduler.py → schedule/ai_scheduler.py
# - apps.py → schedule/apps.py
# - tasks.py → schedule/tasks.py
# - templates/ → schedule/templates/
```

### 3. 設定ファイルの更新
```python
# settings.py に以下を追加

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'schedule',  # Shiftaアプリ
]

# データベース設定（PostgreSQL使用の場合）
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'shifta_db',
        'USER': 'your_username',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# 国際化設定
LANGUAGE_CODE = 'ja'
TIME_ZONE = 'Asia/Tokyo'
USE_I18N = True
USE_TZ = True

# Celery設定（Redis使用）
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# メール設定
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'your-smtp-server.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'Shifta <noreply@yourcompany.com>'
```

### 4. データベースのセットアップ
```bash
# マイグレーションファイルの作成
python manage.py makemigrations schedule

# データベースの作成
python manage.py migrate

# スーパーユーザーの作成
python manage.py createsuperuser
```

### 5. 開発サーバーの起動
```bash
# Djangoサーバーの起動
python manage.py runserver

# 別ターミナルでCeleryワーカーの起動
celery -A shifta worker --loglevel=info

# 別ターミナルでCeleryビートの起動（定期タスク用）
celery -A shifta beat --loglevel=info
```

## 使用方法

### 初期設定
1. **管理者アカウントでログイン**: http://localhost:8000/django-admin/
2. **基本データの設定**:
   - 勤務タイプ（早番、遅番、夜勤など）
   - 休日タイプ（有給、特別休暇など）
   - 勤務スタイル（フルタイム、パートタイムなど）
3. **スタッフアカウントの作成**: 管理画面でユーザー作成とグループ割り当て

### スタッフの使い方（スマートフォン）
1. **ログイン**: http://localhost:8000/schedule/auth/login/
2. **プロフィール設定**: 初回ログイン時に勤務条件を設定
3. **シフト希望提出**: 期間内に希望を選択・提出
4. **スケジュール確認**: 決定されたシフトを確認

### 管理者の使い方（PC）
1. **管理画面アクセス**: http://localhost:8000/schedule/admin/dashboard/
2. **期間設定**: 新しいスケジュール期間を作成
3. **AIシフト作成**: 「AI最適化実行」ボタンでシフト自動生成
4. **手動調整**: 必要に応じてドラッグ&ドロップで調整
5. **確定・通知**: シフト確定後、スタッフに自動通知

## ファイル構成
```
shifta/
├── install_shifta.ps1           # 自動インストールスクリプト
├── manage.py                    # Django管理コマンド
├── shifta/                      # プロジェクト設定
│   ├── settings.py             # Django設定
│   ├── urls.py                 # メインURL設定
│   └── wsgi.py                 # WSGI設定
└── schedule/                    # Shiftaアプリ
    ├── models.py               # データモデル定義
    ├── views.py                # ビュー（コントローラー）
    ├── urls.py                 # URL設定
    ├── ai_scheduler.py         # AI最適化エンジン
    ├── apps.py                 # アプリ設定
    ├── tasks.py                # 非同期タスク
    ├── admin.py                # Django管理画面設定
    ├── templates/              # HTMLテンプレート
    │   ├── base.html          # 基本テンプレート（モバイル対応）
    │   ├── admin_dashboard.html # 管理者ダッシュボード
    │   ├── shift_request.html  # シフト希望入力
    │   └── my_schedule.html    # スケジュール表示
    └── static/                 # 静的ファイル
        ├── css/               # スタイルシート
        ├── js/                # JavaScript
        └── images/            # 画像ファイル
```

## カスタマイズ

### 勤務パターンの追加
1. 管理画面で「勤務タイプ」に新しいパターンを追加
2. 開始時間、終了時間、必要人数などを設定
3. 色分けによる視覚的区別が可能

### AI最適化の調整
- `ai_scheduler.py`内のパラメータを調整
- 制約条件の追加・変更
- 目的関数の重み調整

### UI/UXのカスタマイズ
- `templates/`内のHTMLテンプレート編集
- `static/css/`内のスタイルシート調整
- ブランドカラーやロゴの変更

## API仕様

### スケジュール取得
```
GET /schedule/api/schedule/monthly/?year=2024&month=1
```

### シフト希望提出
```
POST /schedule/api/requests/bulk/
{
  "period_id": 1,
  "requests": [
    {"date": "2024-01-01", "job_type_id": 1, "preference": 5},
    {"date": "2024-01-02", "job_type_id": 2, "preference": 3}
  ]
}
```

### AI最適化実行
```
POST /schedule/api/admin/optimize/
{
  "period_id": 1,
  "options": {
    "prefer_consecutive": true,
    "balance_workload": true
  }
}
```

## トラブルシューティング

### よくある問題

**Q: AIの最適化が完了しない**
A: Celeryワーカーが起動しているか確認してください。ログで詳細なエラーを確認できます。

**Q: スマートフォンでレイアウトが崩れる**
A: キャッシュをクリアして再読み込みしてください。CSSの更新が反映されていない可能性があります。

**Q: 通知メールが送信されない**
A: settings.pyのメール設定を確認してください。開発環境ではコンソールバックエンドを使用できます。

### ログの確認
```bash
# Djangoログ
tail -f logs/django.log

# Celeryログ
tail -f logs/celery.log

# システムヘルスチェック
curl http://localhost:8000/health/
```

## 本番環境での運用

### セキュリティ設定
- `DEBUG = False`に設定
- `SECRET_KEY`を環境変数に移動
- HTTPS証明書の設定
- CSRFトークンの適切な処理

### パフォーマンス最適化
- Redis/Memcachedキャッシュの設定
- 静的ファイルのCDN配信
- データベースのインデックス最適化

### 監視・メンテナンス
- ログローテーションの設定
- 定期バックアップの自動化
- システムリソースの監視

## ライセンス
MIT License

## サポート
- 技術的な質問: GitHub Issues
- 機能要望: GitHub Discussions
- セキュリティ報告: security@yourcompany.com

## 更新履歴
- v1.0.0: 初期リリース
  - 基本的なシフト管理機能
  - AI自動最適化
  - スマートフォン対応UI
  - 管理者ダッシュボード
