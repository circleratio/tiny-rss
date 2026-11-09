# RSSリーダー 実装計画

入力: [spec.md](spec.md)

## ステップ一覧と依存関係

```
S1 雛形 ─┬─ S2 models ─┬─ S3 config ──────────┐
         │             ├─ S4 parser ─ S5 fetcher ┤
         │             ├─ S6 readstate ──────────┼─ S8 gui ─ S9 __main__/ランチャー ─ S10 手動動作確認 ─ S11 最終確認
         │             └─ S7 filtering ─────────┘
```

- S1 → S2 は順に行う。S2 完了後、S3・S4・S6・S7 は互いに独立しており並行して実装できる。
- S5 は S4（`parse_feed`）に依存する。
- S8 は S3〜S7 すべてに依存するため、ロジック層が揃ってから着手する。
- 以下のコマンドはすべてプロジェクトのルートフォルダで PowerShell から実行する。テストは `$env:PYTHONPATH = "src"; python -m unittest discover -s tests -v`（以下「テスト実行」）。

## S1. プロジェクト雛形

- やること
  - spec.md 2章のディレクトリ構成を作成する（`src/rss_reader/`、`tests/fixtures/`）。
  - `pyproject.toml`（spec.md 5章の内容）、`src/rss_reader/__init__.py`（`__version__ = "0.1.0"`）を作成する。
  - サンプルの `feeds.example.txt`（requirement.md の使いかた1の内容）を作成し、`feeds.txt` は `.gitignore` で除外する。
- 完了条件
  - `$env:PYTHONPATH = "src"; python -c "import rss_reader; print(rss_reader.__version__)"` が `0.1.0` を出力する。
  - テスト実行が「Ran 0 tests」でエラーなく終わる。

## S2. models

- やること: `models.py` に `Article` / `Feed` / `FeedResult` と例外クラス群を定義する（spec.md 3.1）。
- 完了条件: `python -c "from rss_reader.models import Article, Feed, FeedResult, ConfigError, FeedFetchError, FeedParseError"` が成功する。

## S3. config

- やること: `config.py` の `load_feed_urls` と `tests/test_config.py` を実装する（spec.md 3.2、6章）。
- 完了条件: `test_config` が全件成功する。

## S4. parser

- やること
  - フィクスチャ `tests/fixtures/` に `rss2.xml`、`rss1.rdf`、`atom.xml`、`broken.xml`、`unknown_root.xml` を作成する。各フィクスチャには日時なし記事・リンクなし記事・HTMLエンティティを含むタイトル・相対リンク（Atom）を含める。
  - `parser.py` の `parse_feed` / `parse_date` と `tests/test_parser.py` を実装する（spec.md 3.3、6章）。
- 完了条件: `test_parser` が全件成功する。

## S5. fetcher

- やること: `fetcher.py` の `fetch` / `fetch_feed` / `fetch_all` と `tests/test_fetcher.py`（`urlopen` をモック）を実装する（spec.md 3.4、6章）。
- 完了条件
  - `test_fetcher` が全件成功する。
  - 実ネットワークで1件取得できることを確認する:
    `$env:PYTHONPATH = "src"; python -c "from rss_reader.fetcher import fetch_feed; r = fetch_feed('https://www.publickey1.jp/atom.xml'); print(r.error, r.feed and (r.feed.title, len(r.feed.articles)))"`
    がエラー `None` とフィード名・記事数を出力する。

## S6. readstate

- やること: `readstate.py` の `ReadStore` と `tests/test_readstate.py`（`tempfile.TemporaryDirectory` を使用）を実装する（spec.md 3.5、6章）。
- 完了条件: `test_readstate` が全件成功する。

## S7. filtering

- やること: `filtering.py` の `merge_articles` / `sort_articles` / `filter_articles` と `tests/test_filtering.py` を実装する（spec.md 3.6、6章）。
- 完了条件: `test_filtering` が全件成功する。

## S8. gui

- やること: `gui.py` の `App` を実装する（spec.md 3.7）。画面レイアウト、Treeview と既読 tag、クリック・Enter・右クリックメニュー、絞り込み、未読のみ表示、更新（バックグラウンド取得とキュー監視）、すべて既読にする、ステータスバー表示、`report_callback_exception` の設定。
- 完了条件: 一時スクリプトで `App(tk.Tk(), Path("."))` を生成し、ウィンドウが開いて `feeds.txt`（`feeds.example.txt` のコピー）の記事が表示される。

## S9. エントリポイントとランチャー

- やること: `__main__.py`（`build_parser` / `main`、spec.md 3.8）と、ルートの `RSSReader.pyw` を実装する。
- 完了条件
  - `$env:PYTHONPATH = "src"; python -m rss_reader --version` が `rss_reader 0.1.0` を出力し終了コード0。
  - `python -m rss_reader --help` が `--data-dir` を含むヘルプを出力し終了コード0。
  - `python -m rss_reader --bogus` が終了コード2。
  - `python -m rss_reader --data-dir C:\no\such\dir` がエラーメッセージを出力し終了コード1。

## S10. 手動動作確認

requirement.md の「使いかた」と突き合わせる。終了コードは各コマンド直後に `$LASTEXITCODE` で確認する。

```powershell
$env:PYTHONPATH = "src"

# 起動オプション（正常系・異常系）
python -m rss_reader --version;              $LASTEXITCODE   # rss_reader 0.1.0 / 0
python -m rss_reader --help;                 $LASTEXITCODE   # ヘルプ / 0
python -m rss_reader --bogus;                $LASTEXITCODE   # エラー / 2
python -m rss_reader --data-dir C:\no\such;  $LASTEXITCODE   # エラー / 1

# 通常起動（サンプルを feeds.txt としてコピーして使用）
Copy-Item feeds.example.txt feeds.txt
python -m rss_reader
```

通常起動後、画面で以下を確認する。

| # | 操作 | 期待結果 |
|---|---|---|
| 1 | 起動する | 取得中もウィンドウが固まらない。全フィードの記事が新しい順に「日時｜フィード｜タイトル」で表示され、ステータスに取得件数が出る |
| 2 | 絞り込み欄に `cpu`（小文字）を入力 | タイトルに「CPU」を含む記事だけになる。入力を消すと全件に戻る |
| 3 | 記事を1件クリック | 既定のブラウザで記事が開き、その行がグレーになる |
| 4 | 列見出しをクリック | ブラウザは開かない |
| 5 | 記事を選択して Enter | ブラウザで開き、グレーになる |
| 6 | 既読記事を右クリック →「未読に戻す」 | 通常色に戻る |
| 6a | 一覧でスペース／BackSpace を押す | 1ページ先／前へスクロールし、表示先頭の記事が選択される |
| 6b | 絞り込み欄でスペース・BackSpace を押し、続けて Esc | 文字が入力・削除され一覧はスクロールしない。Esc で一覧にフォーカスが移る |
| 7 | 「未読のみ表示」をON | 既読記事が消える。絞り込み文字列と併用できる |
| 8 | 絞り込み中に「すべて既読にする」 | 表示中の記事だけが既読になり、ブラウザは開かない |
| 9 | 「更新」 | ボタンが一時無効になり、再取得後も既読状態が保たれる |
| 10 | アプリを閉じて再起動 | 既読状態が保持されている（`read.json` が作成されている） |
| 11 | `feeds.txt` に存在しないURL（例: `https://example.invalid/rss`）を追加して起動 | 他のフィードは表示され、ステータスに失敗1件とURLが出る |
| 12 | `feeds.txt` を空（コメントのみ）にして起動 | 「有効なURLが登録されていません」と表示される |
| 13 | `feeds.txt` を削除（または `--data-dir` に空フォルダを指定）して起動 | 「feeds.txt が見つかりません（feeds.example.txt をコピーして作成してください）」と表示される |
| 14 | `read.json` を壊れた内容にして起動 | 「既読情報が壊れていたため初期化しました」と表示され、`read.json.bak` が作られる |
| 15 | エクスプローラーから `RSSReader.pyw` をダブルクリック | コンソールが出ずに起動し、ルートの `feeds.txt` が使われる |

確認後、#11〜#14 で変更した `feeds.txt` / `read.json` は元に戻す。

## S11. 最終確認

- テスト実行で全件成功することを確認する。
- requirement.md の「要求仕様」の各項目を1つずつ読み、S10 の確認結果またはテストのどれで担保されたかを対応付け、漏れがないことを確認する。
- `__pycache__` など生成物を削除する（`Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force`）。
