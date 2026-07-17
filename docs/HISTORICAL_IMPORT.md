# 過去JRAレース自動収集

## 目的

JRA公式の完了済みレース結果ページから、過去レースの事後データを収集し、Google Driveへ蓄積します。

この機能は、予測前データと事後データを混ぜないため、既存の `races.csv`、`horses.csv`、`bets.csv`、`results.csv` を変更しません。次の専用ファイルを作成します。

- `historical_races.csv`: 開催日、競馬場、距離、馬場、天候など
- `historical_runners.csv`: 着順、馬番、馬名、騎手、タイム、上がり、馬体重、人気など
- `historical_payouts.csv`: 券種、的中組合せ、100円当たり払戻
- `historical_import_errors.csv`: 取得・解析に失敗したURLと原因

## Colabでの実行

`notebooks/historical_import_colab.ipynb` を開き、1つのコードセルを実行します。既に保存されている `race_id` は `resume=True` により重複登録されません。

通常は `JRA_SEED_URLS = []` のまま実行します。JRA側の導線変更などで自動探索できない場合は、最近の完了済みレース結果URLを1件だけ指定します。

```python
JRA_SEED_URLS = [
    "https://www.jra.go.jp/JRADB/accessS.html?CNAME=...",
]
```

## 重要な制約

- 取得するのはレース後に確定した事実です。
- 調教点、パドック点、購入時オッズ、モデル確率、買い目は推測しません。
- 確定結果を予測特徴量へ直接混入させないでください。
- JRAへのアクセス間隔は既定で2.0秒です。短縮して高頻度アクセスしないでください。
- JRAページ構造が変更された場合、パーサー修正とfixtureテスト追加が必要です。

## API

```python
from keiba_ev.historical import import_recent_jra_races

summary = import_recent_jra_races(
    race_count=100,
    output_dir="/content/drive/MyDrive/keiba-ev-data",
    resume=True,
)
```
