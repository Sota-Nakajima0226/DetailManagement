# マスターデータ初期投入

このディレクトリには初期マスターデータの JSON を配置しています。

- `users.json`
- `categories.json`
- `classification_rules.json`
- `fixed_expenses.json`

登録は以下のスクリプトを実行してください。

```bash
cd backend
python scripts/seed_master_data.py
```

## 補足

- `classification_rules.json` / `fixed_expenses.json` は `category_name` でカテゴリを指定します。
- `users.json` は `id`（UUID文字列）を必須にしています。
- 登録時に `categories` から `category_id` を解決して保存します。
- スクリプトは冪等に動作し、同一キーの既存レコードは更新されます。
