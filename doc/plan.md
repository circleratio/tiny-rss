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
    `$env:PYTHONPATH = "src"; python -c "from rss_reader.fetcher import fetch_feed; r = fetch_feed('<実在するフィードのURL>'); print(r.error, r.feed and (r.feed.title, len(r.feed.articles)))"`
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

# 通常起動（feeds.example.txt を feeds.txt にコピーし、架空のURLを実在するフィードのURLに書き換えて使用）
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
| 7 | 起動直後の状態を確認し、「未読のみ表示」をOFF→ONと切り替える | 起動時はONで既読記事が表示されない。OFFで既読記事も表示され、ONに戻すと再び消える。絞り込み文字列と併用できる |
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

## 追加機能: フィードごとの表示パターン

requirement.md「フィードごとの表示パターン」、spec.md 3.1・3.2・3.6・3.7 に対応する。

```
F1 models ─┬─ F2 config ────┐
           └─ F3 filtering ─┴─ F4 gui ─ F5 サンプル・ドキュメント ─ F6 手動動作確認 ─ F7 最終確認
```

- F2 と F3 は互いに独立しており並行して実装できる。F4 は F2・F3 の両方に依存する。

### F1. models

- やること: `models.py` に `FeedConfig(url, title_patterns)` を追加する。
- 完了条件: `python -c "from rss_reader.models import FeedConfig; print(FeedConfig('https://a/'))"` が成功する。

### F2. config

- やること: `load_feed_urls` を `load_feeds`（`list[FeedConfig]` を返す）に置き換え、インデント行の `title:` パターンを解釈する。`tests/test_config.py` を新しい関数に合わせて更新し、spec.md 6章のケースを追加する。
- 完了条件: `test_config` が全件成功する。

### F3. filtering

- やること: `matches_patterns` を追加し、`merge_articles` に `title_patterns` 引数を追加する。`tests/test_filtering.py` に spec.md 6章のケースを追加する。
- 完了条件: `test_filtering` が全件成功する（既存テストも引数省略で従来どおり成功する）。

### F4. gui

- やること: `_worker` で `load_feeds` を使い、取得結果とパターンの対応をキューに入れる。`_poll_results` で `merge_articles` にパターンを渡す。
- 完了条件: F6 の確認項目を満たす。

### F5. サンプル・ドキュメント

- やること: `feeds.example.txt` にパターン指定の記述例（コメントアウトした状態）を追加する。README.md の「フィードを登録する」にパターン指定の説明を追加する。
- 完了条件: `feeds.example.txt` をそのままコピーした `feeds.txt` で `load_feeds` がパターン無しの2件を返す。

### F6. 手動動作確認

`feeds.txt` に次の形で追記して起動する。URLは実在するフィードに、パターンはそのフィードの現在の記事タイトルに含まれる文字列（連載名など）に置き換える。

```text
https://magazine.example.net/feed/
    title:週末レシピ
```

| # | 操作 | 期待結果 |
|---|---|---|
| P1 | 起動する | 対象フィードの記事はタイトルにパターンを含むものだけが表示される。他のフィードの記事は従来どおり全件表示される |
| P2 | `title:` 行を2行（別のパターン）にして起動 | いずれかのパターンを含む記事が表示される |
| P3 | `title:` 行を削除して起動 | 対象フィードの全記事が表示される |
| P4 | 絞り込み欄に入力・「すべて既読にする」 | パターンで除外された記事は表示されず、既読にもならない |

GUI を起動できない環境では、`load_feeds` → `fetch_all` → `merge_articles` を一時スクリプトで実行し、上記 P1〜P3 に相当する結果を確認する。

### F7. 最終確認

- テスト実行で全件成功することを確認する。
- requirement.md「フィードごとの表示パターン」の各項目を、F6 の確認結果またはテストに対応付けて漏れがないことを確認する。
- `__pycache__` など生成物を削除する。

## 追加機能: フィードごとの除外パターン（`!title:`）

requirement.md「フィードごとの表示パターン」の除外パターン、spec.md 3.1・3.2・3.6・3.7 に対応する。

```
X1 models ─┬─ X2 config ────┐
           └─ X3 filtering ─┴─ X4 gui ─ X5 サンプル・ドキュメント ─ X6 手動動作確認 ─ X7 最終確認
```

- X2 と X3 は互いに独立しており並行して実装できる。X4 は X2・X3 の両方に依存する。

### X1. models

- やること: `FeedConfig` に `exclude_patterns: tuple[str, ...] = ()` を追加する。
- 完了条件: 既存テストが全件成功する（既定値により既存の生成箇所は変更不要）。

### X2. config

- やること: `EXCLUDE_TITLE_PREFIX = "!title:"` を追加し、インデント行の `!title:` を `exclude_patterns` として解釈する。`tests/test_config.py` に spec.md 6章のケースを追加する。
- 完了条件: `test_config` が全件成功する。

### X3. filtering

- やること: `merge_articles` に `exclude_patterns` 引数を追加する。`tests/test_filtering.py` に spec.md 6章のケースを追加する。
- 完了条件: `test_filtering` が全件成功する（既存テストも引数省略で従来どおり成功する）。

### X4. gui

- やること: `_worker` で `{url: exclude_patterns}` もキューに入れ、`_poll_results` で `merge_articles` に渡す。
- 完了条件: X6 の確認項目を満たす。

### X5. サンプル・ドキュメント

- やること: `feeds.example.txt` に `!title:` の記述例（コメントアウトした状態）を追加する。README.md の「フィードごとに表示する記事を絞る」に除外パターンの説明を追加する。
- 完了条件: `feeds.example.txt` をそのままコピーした `feeds.txt` で `load_feeds` がパターン無しの2件を返す。

### X6. 手動動作確認

`feeds.txt` に次の形で追記して起動する。URLは実在するフィードに、キーワードはそのフィードの現在の記事タイトルに含まれる文字列に置き換える。

```text
https://tech.example.jp/rss
    !title:PR
```

| # | 操作 | 期待結果 |
|---|---|---|
| E1 | 起動する | 対象フィードの記事のうち、タイトルにキーワードを含むものが表示されない。他のフィードの記事は従来どおり表示される |
| E2 | `!title:` 行を2行（別のキーワード）にして起動 | いずれかのキーワードを含む記事が表示されない |
| E3 | 同じフィードに `title:` 行を追加して起動 | `title:` に一致し、かつ `!title:` に一致しない記事だけが表示される |
| E4 | `!title:` 行を削除して起動 | 除外されていた記事が再び表示される |

GUI を起動できない環境では、`load_feeds` → `fetch_all` → `merge_articles` を一時スクリプトで実行し、上記 E1〜E3 に相当する結果を確認する。

### X7. 最終確認

- テスト実行で全件成功することを確認する。
- requirement.md の除外パターンの各項目を、X6 の確認結果またはテストに対応付けて漏れがないことを確認する。
- `__pycache__` など生成物を削除する。

## 追加機能: 分類ごとのタブ表示

requirement.md「分類とタブ」、spec.md 3.1・3.2・3.6・3.7 に対応する。

```
T1 models ─┬─ T2 config ────┐
           └─ T3 filtering ─┴─ T4 gui ─ T5 サンプル・ドキュメント ─ T6 手動動作確認 ─ T7 最終確認
```

- T2 と T3 は互いに独立しており並行して実装できる。T4 は T2・T3 の両方に依存する。

### T1. models

- やること: `models.py` に `Category(name, feeds)` を追加する。
- 完了条件: `python -c "from rss_reader.models import Category; print(Category('a', ()))"` が成功する。

### T2. config

- やること: `load_feeds` を `load_categories`（`list[Category]` を返す）に置き換え、行頭の `#` を区切り行、インデントされた `#` をコメントとして解釈する。`unique_urls` を追加する。`tests/test_config.py` を新しい関数に合わせて更新し、spec.md 6章の分類のケースを追加する。
- 完了条件: `test_config` が全件成功する。

### T3. filtering

- やること: `articles_by_category` を追加する。`tests/test_filtering.py` に spec.md 6章のケースを追加する。
- 完了条件: `test_filtering` が全件成功する。

### T4. gui

- やること: 一覧を `ttk.Notebook` のタブごとの Treeview に分け、タブの状態を `_Tab` で持つ。`_worker` で `load_categories` と `unique_urls` を使い、`_poll_results` で `articles_by_category` の結果からタブを作り直す（選んでいたタブの再選択を含む）。一覧に対する操作を選択中のタブ対象に変える。`<<NotebookTabChanged>>`・`enable_traversal`・タブの配色を設定する。
- 完了条件: T6 の確認項目を満たす。

### T5. サンプル・ドキュメント

- やること: `feeds.example.txt` を分類付きの記述例に書き換え、パターン例の説明を区切り行と誤解されない形（インデントしたコメント）にする。README.md の「フィードを登録する」に分類の説明を追加し、画面の図をタブ付きにする。
- 完了条件: `feeds.example.txt` をそのままコピーした `feeds.txt` で `load_categories` が「ニュース」「趣味」などサンプルどおりの分類を返し、説明コメントが分類にならない。

### T6. 手動動作確認

利用中の `feeds.txt`（行頭の `#` で分類を書いたもの）で起動する。

| # | 操作 | 期待結果 |
|---|---|---|
| C1 | 起動する | `feeds.txt` の分類名のタブが記述順に並び、各タブにその分類のフィードの記事だけが新しい順に表示される |
| C2 | タブをクリック、Ctrl+Tab／Ctrl+Shift+Tab | タブが切り替わる。切り替え後、スペースでページ送りできる（一覧にフォーカスがある） |
| C3 | 絞り込み欄に入力したままタブを切り替える | 切り替え先のタブにも同じ絞り込みが適用され、絞り込み欄のフォーカスは保たれる |
| C4 | 複数の分類に書いたURLの記事を一方のタブで開き、もう一方のタブに切り替える | もう一方のタブでも既読（「未読のみ表示」中は非表示）になっている |
| C5 | あるタブで「すべて既読にする」 | そのタブで表示中の記事だけが既読になる。他のタブは（同じ記事を除き）変わらない |
| C6 | 2番目以降のタブを選んで「更新」 | 再取得後も同じタブが選ばれている |
| C7 | 最初の区切り行より前にURLを書いて起動 | 先頭に「未分類」タブができ、そのURLの記事が表示される |
| C8 | 区切り行をすべて削除して起動 | 「未分類」タブだけになり、全フィードの記事が表示される |

確認後、C7・C8 で変更した `feeds.txt` は元に戻す。

### T7. 最終確認

- テスト実行で全件成功することを確認する。
- requirement.md「分類とタブ」の各項目を、T6 の確認結果またはテストに対応付けて漏れがないことを確認する。
- `__pycache__` など生成物を削除する。
