# 📰 AI朝刊 Discord 自動配信

Markdownのニュースレターを GitHub に push するだけで、Discord チャンネルに自動配信するボットです。

## 仕組み

```
news/2026-03-16.md を push
       ↓
GitHub Actions が検知
       ↓
Markdown をセクション分割
       ↓
Discord Webhook で Embed 形式送信
（字数制限なし・見やすいフォーマット）
```

## セットアップ手順

### 1. Discord Webhook を作成

1. Discord で配信先チャンネルの **設定（⚙️）** を開く
2. **連携サービス** → **ウェブフック** → **新しいウェブフック**
3. 名前を「AI朝刊」などに設定
4. **ウェブフック URL をコピー**

### 2. GitHub リポジトリに Secret を登録

1. リポジトリの **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** をクリック
3. 以下を登録：
   - Name: `DISCORD_WEBHOOK_URL`
   - Secret: コピーした Webhook URL

### 3. ニュースを配信する

```bash
# news フォルダに Markdown を追加して push するだけ
cp your_news.md news/2026-03-16.md
git add news/
git commit -m "AI朝刊 2026-03-16"
git push
```

→ 自動で Discord に配信されます。

### 手動配信

GitHub の **Actions** タブ → **AI朝刊 → Discord 自動配信** → **Run workflow** からファイルパスを指定して手動実行も可能です。

### 定期配信（オプション）

`.github/workflows/send-news.yml` 内の `schedule` セクションのコメントを外すと、毎朝6:30（JST）に自動配信されます。

## ファイル構成

```
.
├── .github/
│   └── workflows/
│       └── send-news.yml      # GitHub Actions ワークフロー
├── scripts/
│   └── send_to_discord.py     # Discord 送信スクリプト
├── news/
│   └── 2026-03-16.md          # ← ここにニュースを置く
└── README.md
```

## Discord での表示

- Embed 形式で見やすく表示（ダークテーマ対応）
- 長文は自動でセクション分割（字数制限なし）
- Embed 送信失敗時はファイル添付にフォールバック
