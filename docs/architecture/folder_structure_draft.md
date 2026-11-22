# フォルダ構成

## 目次

- [フォルダ構成](#フォルダ構成)
  - [目次](#目次)
  - [1. 目的](#1-目的)
  - [2. 想定フォルダ構成](#2-想定フォルダ構成)
  - [3. 各フォルダの役割](#3-各フォルダの役割)
  - [4. 運用ルール案](#4-運用ルール案)
  - [5. 今後の検討ポイント](#5-今後の検討ポイント)

## 1. 目的

- プロジェクト全体の見通しを良くし、迷わず配置できる構成を決める。
- フロントエンド、バックエンド、ドキュメント、インフラ設定の責務を分離する。
- 将来の機能追加やチーム開発を想定して、保守しやすい構造にする。

## 2. 想定フォルダ構成

```text
DetailManagement/
├── frontend/                    # Flutter Web(PWA)
│   ├── lib/
│   │   ├── core/                # 共通処理(APIクライアント、定数、ユーティリティ)
│   │   ├── features/            # 機能単位モジュール(statements, categories, authなど)
│   │   └── main.dart
│   ├── test/                    # 単体・ウィジェットテスト
│   └── pubspec.yaml
│
├── backend/                     # FastAPI
│   ├── app/
│   │   ├── api/                 # ルーター定義
│   │   ├── services/            # 業務ロジック(分類、通知、集計)
│   │   ├── models/              # ORMモデル
│   │   ├── schemas/             # Pydanticスキーマ
│   │   └── core/                # 設定、認証、DB接続
│   ├── tests/                   # API・サービスのテスト
│   ├── requirements.txt
│   └── main.py
│
├── docs/                        # 設計・仕様ドキュメント
│   ├── requirements/            # 要件定義
│   ├── api/                     # API仕様
│   ├── screens/                 # 画面仕様
│   ├── db/                      # DB設計
│   └── architecture/            # システム構成/構造方針
│
├── scripts/                     # 補助スクリプト(データ投入、ローカル検証など)
├── memo/                        # 運用メモ・バックログ・インフラ比較など
├── infra/                       # デプロイ・環境設定(将来。本番は現状 Render+Supabase)
├── .env.example                 # 環境変数テンプレート
└── README.md                    # 起動方法と全体ガイド
```

## 3. 各フォルダの役割

| フォルダ | 役割 | 主な中身 |
|----------|------|----------|
| `frontend` | ユーザーが触るUI層 | 画面、状態管理、API呼び出し |
| `backend` | 明細取込・分類・集計・通知を担うAPI層 | FastAPIルーター、サービス、モデル |
| `docs` | 仕様と設計の正本 | 要件、API、画面、DB、構成方針 |
| `scripts` | 手作業を減らす運用補助 | 初期データ投入、定期実行補助 |
| `infra` | 実行基盤の設定管理 | Render/Supabase関連の設定（必要時） |

## 4. 運用ルール案

- 新規機能は `frontend/lib/features/<feature>` と `backend/app/api|services` をセットで追加する。
- 仕様変更時は、実装だけでなく `docs` も同一PRで更新する。
- 機密情報は `.env` に保持し、共有用には `.env.example` のみ更新する。
- 暫定スクリプトは `scripts/tmp` に置き、恒久化する際に用途別へ移動する。

## 5. 今後の検討ポイント

- `backend` の実フォルダを現状（`routers`, `models.py` など）から段階的に `app` 構成へ寄せるか。
- CIで `frontend` と `backend` のテストを分離実行するワークフロー設計。
- `docs` の命名規則（`*_specification.md` / `*_design.md`）の統一。
- 将来、モノレポ管理ツール導入が必要か（現時点では不要）。
