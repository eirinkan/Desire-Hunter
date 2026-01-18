# Desire Hunter - プロジェクト設定

## Trello連携
作業完了時は、以下のTrelloカードにコメントで更新情報を投稿すること。

- **ボード**: https://trello.com/b/bVeqXVbm/コンサルティング
- **カード**: https://trello.com/c/gANOq4uE/1147-リサーチシステム
- **カードID**: gANOq4uE
- **APIキー**: (環境変数 TRELLO_API_KEY を参照)
- **トークン**: (環境変数 TRELLO_TOKEN を参照)

## プロジェクト概要
Desire Hunter - 欲求から製品を発見するWebアプリケーション

### 技術スタック
- **フレームワーク**: Next.js 16 (App Router)
- **言語**: TypeScript
- **スタイリング**: Tailwind CSS
- **ホスティング**: Vercel Pro
- **AI**: Gemini API (gemini-2.0-flash)
- **検索**: Serper API (Google検索)
- **スクレイピング**: Firecrawl API

### 本番URL
- https://desire-hunter.vercel.app

### ディレクトリ構造
```
frontend/
├── src/
│   ├── app/
│   │   ├── api/hunt/route.ts  # メインAPI
│   │   ├── page.tsx           # フロントエンドUI
│   │   ├── layout.tsx         # レイアウト
│   │   └── globals.css        # グローバルスタイル
│   └── lib/
│       ├── gemini.ts          # Gemini API クライアント
│       ├── serper.ts          # Serper API クライアント
│       └── firecrawl.ts       # Firecrawl API クライアント
└── .env.local                 # 環境変数（ローカル）
```
