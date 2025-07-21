# 🚀 ConoHa VPS 即座デプロイ手順

## 📋 準備完了状況
- **サーバーIP**: `160.251.181.238` ✅
- **ドメイン**: `mednext.jp` → サーバーIP ✅  
- **ポート開放**: 22, 80, 443, 8800 ✅
- **VPS仕様**: メモリ1GB/CPU2Core ✅

## 🖥️ ConoHa VPSコンソールでのデプロイ

### 手順1: ConoHa VPSコンソールにアクセス
1. ConoHa管理画面にログイン
2. 「VPS」→「vps-2025-03-29-12-31」をクリック
3. 「コンソール」ボタンをクリック
4. rootでログイン

### 手順2: 以下のコマンドを1行ずつ実行

```bash
# 1. 作業ディレクトリに移動
cd /root

# 2. デプロイスクリプトをダウンロード
curl -O https://raw.githubusercontent.com/minatoman/shifta-shift-management/main/direct-deploy.sh

# 3. 実行権限付与
chmod +x direct-deploy.sh

# 4. デプロイ実行
./direct-deploy.sh
```

### 手順3: GitHub利用版（推奨）
GitHub接続が可能な場合：
```bash
# GitHub版デプロイスクリプトをダウンロード
curl -O https://raw.githubusercontent.com/minatoman/shifta-shift-management/main/console-deploy.sh
chmod +x console-deploy.sh
./console-deploy.sh
```

## 🔄 GitHub不要版（フォールバック）
GitHubに接続できない場合は `direct-deploy.sh` を使用。
このスクリプトは必要なファイルをすべて自動生成します。

## ⏱️ デプロイ所要時間
- **システム更新**: 2-3分
- **Docker インストール**: 3-5分  
- **アプリケーションビルド**: 5-10分
- **データベース初期化**: 1-2分
- **合計**: 約15-20分

## 🎯 完了後の確認

### 1. アクセステスト
```bash
# サーバー内でのテスト
curl http://localhost:8000/health/

# 外部からのテスト（別のPCから）
curl http://160.251.181.238:8000/health/
```

### 2. ブラウザでアクセス
- **メインサイト**: http://160.251.181.238:8000/
- **管理画面**: http://160.251.181.238:8000/admin/
- **ヘルスチェック**: http://160.251.181.238:8000/health/

### 3. 管理者ログイン
- **ユーザー名**: `admin`
- **パスワード**: `shifta2025!`

## 📱 ドメインアクセス設定

### 現在の状況
- `mednext.jp` は既に `160.251.181.238` に向いている ✅
- HTTP アクセス: http://mednext.jp:8000/ (ポート8000必要)

### HTTPS/SSL設定（オプション）
```bash
# Traefik版に切り替え（SSL自動取得）
cd /var/www/shifta
docker-compose -f docker-compose.production.yml up -d
```

## 🛠️ トラブルシューティング

### Docker権限エラー
```bash
# Dockerグループに追加後、再ログイン
sudo usermod -aG docker $USER
exit
# 再度ログインしてスクリプト実行
```

### ポートアクセスエラー
```bash
# ファイアウォール確認
sudo ufw status

# ポート開放
sudo ufw allow 8000
sudo ufw reload
```

### コンテナ状態確認
```bash
cd /var/www/shifta
docker-compose -f docker-compose.standalone.yml ps
docker-compose -f docker-compose.standalone.yml logs web
```

### データベース接続エラー
```bash
# PostgreSQL ログ確認
docker-compose -f docker-compose.standalone.yml logs db

# データベース再起動
docker-compose -f docker-compose.standalone.yml restart db
```

## 🔧 運用コマンド

### ログ確認
```bash
cd /var/www/shifta

# アプリケーションログ
docker-compose logs web

# 全サービスログ
docker-compose logs

# リアルタイムログ
docker-compose logs -f web
```

### サービス再起動
```bash
# 全サービス再起動
docker-compose restart

# 個別サービス再起動
docker-compose restart web
docker-compose restart db
```

### アップデート
```bash
cd /var/www/shifta

# コード更新（GitHub版の場合）
git pull origin main

# 再ビルド・再起動
docker-compose down
docker-compose up -d --build

# マイグレーション実行
docker-compose exec web python manage.py migrate
```

## 📞 サポート

### 問題発生時の情報収集
```bash
# システム情報
uname -a
docker --version
docker-compose --version

# ディスク使用量
df -h

# メモリ使用量
free -h

# ポート使用状況
netstat -tulpn | grep :8000
```

### よくある問題と解決策

1. **「Permission denied」エラー**
   ```bash
   sudo chown -R $USER:$USER /var/www/shifta
   ```

2. **「Port already in use」エラー**
   ```bash
   sudo lsof -i :8000
   sudo killall docker-compose
   ```

3. **「Database connection failed」エラー**
   ```bash
   docker-compose restart db
   sleep 30
   docker-compose restart web
   ```

## 🎉 完了チェックリスト

- [ ] ConoHa VPSコンソールにアクセス済み
- [ ] デプロイスクリプト実行完了
- [ ] http://160.251.181.238:8000/ でアクセス可能
- [ ] 管理画面ログイン成功
- [ ] ヘルスチェック API応答確認
- [ ] ファイアウォール設定完了
- [ ] 管理者パスワード変更（推奨）

すべてチェックが完了したら、**Shiftaシステムの本番運用開始** です！🎊
