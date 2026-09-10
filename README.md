# kabutan-screener

株探（kabutan.jp）のランキング系ページ（銘柄探検・株価注意報）を毎日収集し、
複数シグナルの重複やスコアリングで候補銘柄を絞り込み、バックテストできる形で
SQLiteに蓄積するツール群。

## アクセスに関する方針

- 通常のブラウザとして自然なヘッダーを付けてアクセスする
- 1日1回のバッチ取得が基本。複数ページ取得する場合はリクエスト間に数秒のインターバルを入れる
- 取得済みデータはDBにキャッシュし、無駄な再取得はしない（差分更新）
- 株探の利用規約（過度な負荷をかける行為の禁止）を踏まえ、高頻度・並列アクセスはしない

## セットアップ

```bash
pip install requests pandas lxml
```

## 日次ルーティン

```bash
python run_daily.py              # 30ランキングを収集
python flag_watch_list.py        # 時間差シグナル（信用高値期日到来）を記録
python score_ranking.py --days 1 --top 20 --min-score 1   # スコアリングで候補抽出
python check_data_health.py      # 取得漏れチェック
```

## ファイル構成

| ファイル | 役割 |
|---|---|
| `config.py` | 追跡するランキングページの一覧 |
| `fetch.py` | HTTPアクセスの共通処理（ヘッダー等） |
| `parse.py` | HTMLテーブルのパース処理 |
| `db.py` | SQLiteスキーマ・読み書き |
| `util.py` | 共通ユーティリティ（ファンド判定、%変換など） |
| `run_daily.py` | 日次のランキング収集メイン |
| `fetch_price_history.py` | 個別銘柄の日足四本値バックフィル（進捗管理付き） |
| `fetch_stock_detail.py` | 個別銘柄の詳細（PER/PBR/信用倍率/業績/信用残週次） |
| `select_candidates.py` | 複数ランキング重複による一次審査 |
| `funnel_screen.py` | 信用需給×テクニカルクロスのファネル抽出 |
| `score_ranking.py` | シグナル加点方式のスコアリング（ファンド・急騰銘柄は除外） |
| `flag_watch_list.py` | 時間差で効くシグナルの別枠記録 |
| `volume_price_check.py` | 出来高と値動きの矛盾チェック |
| `compile_ai_brief.py` | AIチャット向けダイジェストMarkdown生成 |
| `record_ai_ranking.py` | AIの定性判断結果の記録 |
| `check_data_health.py` | 取得漏れ・進捗の健全性チェック |

## DBテーブル

- `rankings` : 追跡対象ページのカタログ
- `stocks` : 銘柄マスタ
- `ranking_snapshots` : 日付×ランキング×銘柄のスナップショット
- `price_history` / `price_history_progress` : 個別銘柄の日足四本値と取得進捗
- `stock_details` : 個別銘柄の詳細情報（JSON）
- `screening_picks` : 各ファネル・スコアリング・AI判断の結果履歴（バックテスト用）
