# one-click-deploy.ps1 - コノハVPS ワンクリックデプロイ（PowerShell版）

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerIP,
    
    [string]$ServerUser = "root",
    
    [string]$ProjectDir = "/var/www/shifta"
)

Write-Host "🚀 Shifta ConoHa VPS ワンクリックデプロイ" -ForegroundColor Blue
Write-Host "================================================="

Write-Host "📋 デプロイ設定:" -ForegroundColor Yellow
Write-Host "  サーバーIP: $ServerIP"
Write-Host "  ユーザー: $ServerUser"
Write-Host "  プロジェクトディレクトリ: $ProjectDir"
Write-Host ""

# SSH接続テスト
Write-Host "🔌 SSH接続テスト..." -ForegroundColor Blue
try {
    ssh -o ConnectTimeout=10 -o BatchMode=yes "$ServerUser@$ServerIP" "echo 'SSH接続成功'" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "SSH接続失敗"
    }
    Write-Host "✅ SSH接続成功" -ForegroundColor Green
} catch {
    Write-Host "❌ SSH接続に失敗しました" -ForegroundColor Red
    Write-Host "   以下を確認してください:"
    Write-Host "   1. SSHキーが正しく設定されているか"
    Write-Host "   2. サーバーIPが正しいか"
    Write-Host "   3. ユーザー名が正しいか"
    exit 1
}

# プロジェクトファイルの準備
Write-Host "📦 プロジェクトファイル準備中..." -ForegroundColor Blue

# ランダムパスワード生成（PowerShell版）
function New-RandomString {
    param([int]$Length = 32)
    $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    $random = 1..$Length | ForEach-Object {Get-Random -Maximum $chars.length}
    return ($random | ForEach-Object {$chars[$_]}) -join ''
}

$secretKey = New-RandomString -Length 50
$postgresPassword = New-RandomString -Length 32

# 環境変数ファイル作成
$envContent = @"
# Auto-generated production environment
SECRET_KEY=$secretKey
POSTGRES_PASSWORD=$postgresPassword
DEBUG=False
ALLOWED_HOSTS=mednext.jp,www.mednext.jp,localhost,127.0.0.1,$ServerIP
CSRF_TRUSTED_ORIGINS=https://mednext.jp,https://www.mednext.jp,http://$ServerIP`:8000
SECURE_SSL_REDIRECT=False
SERVER_IP=$ServerIP
URL_PREFIX=
"@

$envContent | Out-File -FilePath ".env.deploy" -Encoding UTF8
Write-Host "✅ 環境変数ファイル作成完了" -ForegroundColor Green

# rsyncがない場合の代替手段（PowerShell + SSH）
Write-Host "📤 ファイル転送中..." -ForegroundColor Blue

# 除外するファイル・ディレクトリのパターン（参考）
# $excludePatterns = @(
#     ".git*",
#     "__pycache__*", 
#     "*.pyc",
#     ".venv*",
#     "venv*",
#     "node_modules*",
#     "staticfiles*",
#     "media*",
#     "logs*",
#     ".env"
# )

# リモートディレクトリ作成
ssh "$ServerUser@$ServerIP" "mkdir -p $ProjectDir"

# ファイル転送（PowerShell版）
Write-Host "ファイルをコピー中..." -ForegroundColor Yellow

# tarで圧縮してから転送（効率的）
$tempArchive = "shifta-deploy-$(Get-Date -Format 'yyyyMMdd-HHmmss').tar.gz"

# Windows Subsystem for Linux (WSL) または Git Bashが利用可能な場合
if (Get-Command wsl -ErrorAction SilentlyContinue) {
    Write-Host "WSLを使用してファイル転送..." -ForegroundColor Yellow
    wsl tar --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' --exclude='venv' --exclude='node_modules' --exclude='staticfiles' --exclude='media' --exclude='logs' --exclude='.env' -czf "/tmp/$tempArchive" .
    wsl scp "/tmp/$tempArchive" "$ServerUser@$ServerIP`:$ProjectDir/"
    ssh "$ServerUser@$ServerIP" "cd $ProjectDir && tar -xzf $tempArchive && rm $tempArchive"
    wsl rm "/tmp/$tempArchive"
} else {
    # SCPを使用した個別ファイル転送（フォールバック）
    Write-Host "SCPを使用してファイル転送..." -ForegroundColor Yellow
    scp -r * "$ServerUser@$ServerIP`:$ProjectDir/"
}

# 環境変数ファイルも転送
scp ".env.deploy" "$ServerUser@$ServerIP`:$ProjectDir/.env"
Write-Host "✅ ファイル転送完了" -ForegroundColor Green

# サーバーでのデプロイ実行
Write-Host "🔧 サーバーでのデプロイ実行..." -ForegroundColor Blue

$deployScript = @'
set -e

cd /var/www/shifta

echo "📂 ディレクトリ権限設定..."
sudo chown -R $USER:$USER /var/www/shifta
mkdir -p logs staticfiles media celerybeat-schedule
chmod 755 logs staticfiles media

# Dockerの確認・インストール
if ! command -v docker &> /dev/null; then
    echo "🐳 Docker インストール中..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    
    # Docker Compose インストール
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
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
echo "   メインサイト: http://SERVER_IP_PLACEHOLDER:8000/"
echo "   管理画面: http://SERVER_IP_PLACEHOLDER:8000/admin/"
echo ""
echo "👤 管理者ログイン:"
echo "   ユーザー名: admin"
echo "   パスワード: shifta2025!"
'@

# SERVER_IP_PLACEHOLDERを実際のIPに置換
$deployScript = $deployScript -replace "SERVER_IP_PLACEHOLDER", $ServerIP

# スクリプトをリモートで実行
$deployScript | ssh "$ServerUser@$ServerIP" 'bash -s'

# ローカルファイルクリーンアップ
Remove-Item ".env.deploy" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "🎊 デプロイ完了！" -ForegroundColor Green
Write-Host "================================="
Write-Host "🌐 アクセスURL:" -ForegroundColor Yellow
Write-Host "   http://$ServerIP`:8000/"
Write-Host "   http://$ServerIP`:8000/admin/"
Write-Host ""
Write-Host "👤 管理者ログイン:" -ForegroundColor Yellow
Write-Host "   ユーザー名: admin"
Write-Host "   パスワード: shifta2025!"
Write-Host ""
Write-Host "📋 次の作業:" -ForegroundColor Yellow
Write-Host "   1. mednext.jp ドメインを $ServerIP に向ける"
Write-Host "   2. SSL証明書の設定"
Write-Host "   3. 管理者パスワードの変更"
Write-Host "   4. ファイアウォール設定 (ポート 8000, 22)"

# ブラウザで開く
Write-Host ""
$response = Read-Host "🖥️  ブラウザでサイトを開きますか？ (y/n)"
if ($response -match "^[yY]") {
    Start-Process "http://$ServerIP`:8000/"
}
