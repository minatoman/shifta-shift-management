# GitHub アップロード手順

## 現在の状況
✅ Gitリポジトリ初期化完了
✅ 全ファイルコミット完了
✅ .gitignore設定完了

## 次のステップ（GitHub Web上で実行）

### 1. GitHubでリポジトリ作成
1. https://github.com にアクセス
2. 右上の「+」→「New repository」をクリック
3. Repository名: `shifta-shift-management`
4. Description: `📱 Shifta - スマートフォン対応シフト管理システム（AI自動最適化機能付き）`
5. Public または Private を選択
6. 「Create repository」をクリック

### 2. ローカルからプッシュ（以下のコマンドを実行）

```bash
# GitHubリポジトリを追加（<your-username>を実際のユーザー名に変更）
git remote add origin https://github.com/<your-username>/shifta-shift-management.git

# ブランチ名をmainに変更
git branch -M main

# 初回プッシュ
git push -u origin main
```

### 3. GitHub認証が必要な場合
- Personal Access Token の作成が必要
- Settings → Developer settings → Personal access tokens → Tokens (classic)
- 「Generate new token」で repo 権限を付与

## リポジトリ構成

```
shifta-shift-management/
├── README.md                    # 完全な使用説明書
├── install_shifta.ps1          # 自動セットアップスクリプト
├── .gitignore                  # Git除外設定
├── shifta_models.py            # データベースモデル
├── ai_scheduler.py             # AI最適化エンジン
├── views.py                    # Django コントローラー
├── urls.py                     # URL設定
├── shifta_main_urls.py         # メインURL設定
├── apps.py                     # アプリ設定
├── tasks.py                    # 非同期処理タスク
├── base.html                   # モバイル基本テンプレート
├── admin_dashboard.html        # PC管理画面
├── shift_request.html          # スマホ希望入力画面
└── my_schedule.html            # スマホスケジュール画面
```

## 特徴的な機能

### 🎯 スマートフォン完全対応
- 44px以上のタッチターゲット
- プルトゥリフレッシュ
- ハプティックフィードバック
- オフライン対応

### 🤖 AI自動最適化
- PuLP数理最適化ライブラリ
- 制約条件自動処理
- スタッフ希望重み付け
- リアルタイム進捗表示

### ⚡ パフォーマンス
- Celery非同期処理
- Redis キャッシュ
- レスポンシブデザイン
- API最適化

### 🔒 セキュリティ
- Django認証システム
- CSRF保護
- 権限ベースアクセス制御
- セキュアな設定

## デモ用データ
- 基本的な勤務タイプ（早番、遅番、夜勤）
- 休日タイプ（有給、特別休暇）
- サンプルスタッフプロフィール
- テスト用シフトパターン

## 本番運用対応
- 環境変数による設定分離
- データベース最適化
- ログ設定
- エラーハンドリング
- 監視・アラート対応
