# qtrader — 暗号資産 L/S マーケットニュートラル・ボット

暗号資産の USDT 建て無期限先物(Perpetual)を対象に、クロスセクショナル・モメンタムで
ロング/ショートのドルニュートラル・ポートフォリオを組む戦略の研究・実行基盤です。

「理論 → データ → シグナル → バックテスト → ペーパートレード → ライブ」と段階的に進めます。
現在は **バックテストまで** 実装済みです。

## ドキュメント

| ファイル | 内容 |
|---|---|
| [docs/theory.md](docs/theory.md) | 戦略の理論的根拠・収益源の分解・過学習防止の原則 |
| [docs/backtest_design.md](docs/backtest_design.md) | バックテスト仕様(バイアス対策・コストモデル・評価指標) |
| [docs/research_log.md](docs/research_log.md) | 実験記録(ボツ案も含め全て記録する) |

## セットアップ

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## 使い方

### 1. データ取得(Binance USDT-M 公開 API、API キー不要)

```bash
python scripts/fetch_data.py --days 730
```

`data/ohlcv/*.parquet`(1時間足)と `data/funding/*.parquet`(ファンディングレート履歴)に保存されます。
再実行すると増分のみ取得します。

ネットワークが使えない環境での開発・動作確認用に、合成データ生成も用意しています
(**プラミング検証専用**。合成データのバックテスト結果に収益性の意味はありません):

```bash
python scripts/fetch_data.py --synthetic
```

### 2. バックテスト

```bash
python scripts/run_backtest.py --config config/base.yaml
```

指標テーブル(コスト後 Sharpe、最大DD、ターンオーバー、対BTCβ など)と
エクイティカーブが `data/results/` に出力されます。

### 3. テスト

```bash
pytest
```

## 設定

すべて [config/base.yaml](config/base.yaml) で管理します(ユニバース数、ルックバック、分位幅、
リバランス頻度、手数料・スリッページ率、ホールドアウト比率)。

## リポジトリ構成

```
src/qtrader/
├── config.py        # YAML設定の読込
├── data/            # Binance公開APIクライアント・parquet保存・ユニバース構築・品質チェック
├── signals/         # シグナル(プラグイン型)。momentum.py がクロスセクショナル・モメンタム
├── portfolio/       # スコア → ドルニュートラルなウェイト行列
└── backtest/        # ベクトル化バックテスト・コスト/ファンディング・評価指標・レポート
scripts/             # fetch_data.py / run_backtest.py
tests/               # pytest(合成データによる既知解テスト・ルックアヘッド回帰テスト)
```

## 今後の工程(未実装)

1. **ウォークフォワード検証 + パラメータ感度分析** — 合格基準(例: コスト後 Sharpe > 1.0、
   最大DD < 20%、パラメータ近傍で成績が安定)を満たすまで実運用に進まない
2. **ペーパートレード** — Broker 抽象 + PaperBroker。cron 定期実行で 2〜4 週間運用し、
   バックテストとの乖離を突合
3. **ライブ実行** — ccxt 発注、レバレッジ上限、キルスイッチ、ポジション照合。極小資金から
4. **運用** — 日次レポート、乖離モニタリング

## 免責

本リポジトリは学習・研究目的です。実資金での運用は自己責任で行ってください。
バックテストの成績は将来の収益を保証しません。
