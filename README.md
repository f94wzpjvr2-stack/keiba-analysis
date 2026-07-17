# 競馬EVシステム：Colab × Codex ハイブリッド版

## 結論

最も有用な構成は、次の役割分担です。

- **GitHub**：ソースコードと変更履歴の正本
- **Codex**：機能追加、修正、テスト、レビュー
- **Google Colab**：レース当日の入力、計算、表の確認
- **Google Drive**：個人の予想・購入・結果データの永続保存
- **ChatGPT**：新聞画像、馬場、展開、パドックを解釈し、固定フォーマットの採点値を作る

コードと個人データを分離するのが重要です。コードはGitHub、レース履歴はGoogle Driveに置きます。

## 初回導入

### 1. GitHubリポジトリを作る

GitHubで空のリポジトリを作ります。このプロジェクトでは `keiba-analysis` を使います。

このフォルダ一式をリポジトリへアップロードして、mainブランチへ保存します。個人の購入履歴はアップロードしないでください。

### 2. Codexへ接続する

CodexでGitHubを接続し、作成したリポジトリを選択します。リポジトリ直下の `AGENTS.md` が、毎回の開発ルールとして読み込まれる前提です。

最初のCodex依頼例：

```text
このリポジトリを確認してください。AGENTS.mdに従い、
1. python -m pip install -e ".[dev]" を実行
2. python -m pytest -q を実行
3. 失敗があれば原因を修正
4. notebooks/keiba_colab.ipynb の導入手順とコードが一致しているか確認
5. 変更内容とテスト結果を報告
してください。
```

### 3. Colabノートブックを開く

GitHub上の `notebooks/keiba_colab.ipynb` をGoogle Colabで開きます。

ノートブックの最初の設定セルで、次を変更します。

```python
GITHUB_REPO = "f94wzpjvr2-stack/keiba-analysis"
GITHUB_BRANCH = "main"
PRIVATE_REPO = False
DRIVE_DATA_DIR = "/content/drive/MyDrive/keiba-ev-data"
```

その後、上から順番にセルを実行します。

## 日々の運用

### レース前

1. ChatGPTへ出馬表、調教、オッズ、馬体重、パドック、馬場を送る
2. ChatGPTから馬ごとの採点値をCSV形式で受け取る
3. Colabの `horses` DataFrameへ貼り付ける
4. ワイド・馬連・三連複オッズのテキストを該当セルへ貼り付ける
5. 能力順位、推定確率、EV順位、推奨買い目を確認する
6. モデル前提と情報不足を確認し、購入または見送る

### レース後

1. 着順を `results.csv` に記録
2. 実際の購入内容と払戻を `bets.csv` に記録
3. ROI集計を実行
4. ChatGPTへ予想・購入・結果を渡して検証
5. 単発事象ではなく、複数レースで再現した修正だけをCodexへ依頼

## 重要なモデル上の注意

- 初期版の勝率は、採点値をsoftmaxで変換する暫定モデルです。
- 馬連・ワイド・三連複の確率は、勝率を強さとして使うPlackett-Luce近似です。
- ワイドのオッズ幅は、原則として下限オッズを使って保守的にEVを計算します。
- 推定確率は事実ではありません。アルゴリズムバージョンと前提を必ず保存します。
- 予算は上限です。正のEVがなければ、全額を使い切りません。

## 開発コマンド

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
ruff check .
```

## keiba-ai v2

`keiba_ai` パッケージは、履歴データが十分に集まった後に機械学習モデルを検証するための追加機能です。

- Colab入口: `notebooks/keiba_ai_v2_colab.ipynb`
- ChatGPT入力補助: `CHATGPT_OUTPUT_PROMPT.txt`
- 学習スクリプト: `scripts/train_model.py`
- 学習データ目安: 200行以上
- 検証方法: 時系列分割のみ
- 禁止事項: レース結果、払戻、ROIなどのレース後情報を予測特徴量に使わない

通常運用は既存の `notebooks/keiba_colab.ipynb` を使い、v2は十分な記録が集まってから比較検証に使います。

## フォルダ構成

```text
keiba-hybrid-system-v1/
├── AGENTS.md
├── README.md
├── CODEX_PROMPTS.md
├── MANUAL.md
├── config/default.json
├── data/templates/
├── notebooks/keiba_colab.ipynb
├── scripts/check_project.py
├── scripts/train_model.py
├── src/keiba_ai/
├── src/keiba_ev/
└── tests/
```
