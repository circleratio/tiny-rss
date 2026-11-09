# RSSリーダー 設計

入力: [requirement.md](requirement.md)

## 1. 全体構成

GUI（tkinter）と、GUIに依存しないロジック層（設定読み込み・取得・解析・既読管理・絞り込み）に分ける。ロジック層は単体テストで担保し、GUI層は薄く保って手動確認で担保する。

```
[feeds.txt] → config ─┐
                      ├→ fetcher（並列取得）→ parser（RSS2/RDF/Atom）→ list[Article]
                      │                                                    │
[read.json] ↔ readstate ←──────────── gui（Treeview表示）←── filtering（絞り込み・並べ替え）
```

## 2. ディレクトリ構成

```
rss/
├─ pyproject.toml
├─ RSSReader.pyw          # ダブルクリック用ランチャー（src を sys.path に追加して main を呼ぶ）
├─ feeds.example.txt       # サンプル（配布物に含める）
├─ feeds.txt               # 利用者が作成・編集（.gitignore で除外）
├─ doc/
│  ├─ requirement.md
│  ├─ spec.md
│  └─ plan.md
├─ src/
│  └─ rss_reader/
│     ├─ __init__.py       # __version__
│     ├─ __main__.py       # 引数解析・起動
│     ├─ models.py         # データクラス・例外
│     ├─ config.py         # feeds.txt の読み込み
│     ├─ parser.py         # XML → Feed
│     ├─ fetcher.py        # HTTP取得・並列化
│     ├─ readstate.py      # 既読情報の永続化
│     ├─ filtering.py      # 絞り込み・並べ替え
│     └─ gui.py            # tkinter 画面
└─ tests/
   ├─ fixtures/            # rss2.xml, rss1.rdf, atom.xml, broken.xml など
   ├─ test_config.py
   ├─ test_parser.py
   ├─ test_fetcher.py
   ├─ test_readstate.py
   └─ test_filtering.py
```

## 3. モジュール設計

### 3.1 `models.py`

```python
@dataclass(frozen=True)
class Article:
    title: str
    link: str                      # 既読管理のキー
    published: datetime | None     # timezone-aware（UTC に正規化）
    feed_title: str

@dataclass(frozen=True)
class FeedConfig:                  # feeds.txt の1フィード分の設定
    url: str
    title_patterns: tuple[str, ...] = ()   # 空なら全記事を表示

@dataclass(frozen=True)
class Feed:
    url: str
    title: str
    articles: list[Article]

@dataclass(frozen=True)
class FeedResult:
    url: str
    feed: Feed | None
    error: str | None              # 失敗時の利用者向けメッセージ

class RssReaderError(Exception): ...
class ConfigError(RssReaderError): ...
class FeedFetchError(RssReaderError): ...
class FeedParseError(RssReaderError): ...
```

### 3.2 `config.py`

```python
FEEDS_FILENAME = "feeds.txt"
TITLE_PREFIX = "title:"
def load_feeds(path: Path) -> list[FeedConfig]
```

- UTF-8（BOM付きも可: `utf-8-sig`）で読む。
- 各行を `strip()` した結果が空、または `#` 始まりの行は除外する（インデントの有無を問わない）。
- 元の行の先頭文字がスペースまたはタブで、かつ `strip()` 後が `http://` / `https://` で始まらない行を「インデント行」、それ以外を「URL行」として扱う（インデントされたURL行を従来どおり有効にするため）。
- URL行:
  - `http://` / `https://` で始まらない行は無視し、`logging.warning` に出す。
  - 重複URLは最初の1件のみ残す（順序維持）。2件目以降の重複URL行と、それに続くインデント行は無視する。
- インデント行（直前の有効なURL行に属する）:
  - `strip()` 後に `title:`（大文字・小文字を区別しない）で始まる場合、残りを `strip()` した文字列をそのフィードの `title_patterns` に追加する（記述順を維持）。
  - 直前に有効なURL行が無い、`title:` 以外で始まる、`title:` の後が空、のいずれかの場合は無視し、`logging.warning` に出す。
  - 直前のURL行が重複などで無視された場合、そのインデント行も（警告なしで）無視する。
- ファイルが存在しない場合は `ConfigError("feeds.txt が見つかりません: <path>（feeds.example.txt をコピーして作成してください）")` を送出する。
- 有効URLが0件の場合は空リストを返す（メッセージ表示はGUI側）。

### 3.3 `parser.py`

```python
def parse_feed(data: bytes, url: str) -> Feed
def parse_date(text: str | None) -> datetime | None
```

- `xml.etree.ElementTree.fromstring` で解析する。`ParseError` は `FeedParseError` に変換する。
- 文字コード: 標準の expat は Shift_JIS / EUC-JP などのマルチバイト文字コードを扱えないため、XML宣言の `encoding` が UTF-8 / UTF-16 / ASCII / Latin-1 以外の場合は、Python のコーデックでデコードし、宣言から `encoding` を除いて UTF-8 に変換してから解析する。未知の文字コード名は `FeedParseError("未対応の文字コードです")`。
- ルート要素で形式を判定する。

| 形式 | ルート | フィード名 | 記事要素 | タイトル | リンク | 日時 |
|---|---|---|---|---|---|---|
| RSS 2.0 | `rss` | `channel/title` | `channel/item` | `title` | `link` | `pubDate`（なければ `dc:date`） |
| RSS 1.0 | `rdf:RDF` | `rss1:channel/rss1:title` | `rss1:item` | `rss1:title` | `rss1:link` | `dc:date` |
| Atom | `atom:feed` | `atom:title` | `atom:entry` | `atom:title` | `atom:link` の `rel="alternate"`（または rel 省略）の `href` | `atom:published`（なければ `atom:updated`） |

  - 名前空間: `rss1 = http://purl.org/rss/1.0/`、`atom = http://www.w3.org/2005/Atom`、`dc = http://purl.org/dc/elements/1.1/`
  - 上記以外のルートは `FeedParseError("未対応のフィード形式です")`。
- タイトルは `html.unescape` した後、連続空白を1つにまとめる。空なら `(無題)`。
- フィード名が取れない場合はフィードURLのホスト名を使う。
- リンクは `urljoin(url, link)` で絶対URLにする。リンクが空の記事、および絶対URLのスキームが `http` / `https` 以外またはホストが空の記事は除外する（定数 `ALLOWED_SCHEMES`）。
  - 理由: Windows の `webbrowser.open` は `os.startfile` を経由するため、`file:` や他のスキームのURLを渡すとローカルのファイルやプログラムが起動しうる。`Article.link` は parser でのみ生成されるため、ここで制限すれば GUI に安全なURLだけが渡る。
- `parse_date`:
  1. `email.utils.parsedate_to_datetime`（RFC 822 形式）を試す。
  2. 失敗したら末尾 `Z` を `+00:00` に置換して `datetime.fromisoformat`（ISO 8601 / W3CDTF）を試す。
  3. どちらも失敗したら `None`。
  - タイムゾーン情報が無い場合は UTC とみなす。結果は UTC に正規化して返す。
- XML の安全性: 標準ライブラリの expat（2.4.1以降）はエンティティ展開攻撃を抑止するため、追加対策はしない。

### 3.4 `fetcher.py`

```python
USER_AGENT = f"rss_reader/{__version__}"
TIMEOUT_SEC = 15
MAX_WORKERS = 8

def fetch(url: str, timeout: float = TIMEOUT_SEC) -> bytes
def fetch_feed(url: str) -> FeedResult
def fetch_all(urls: list[str]) -> list[FeedResult]
```

- `fetch`: `urllib.request.urlopen` で取得する。`HTTPError` / `URLError` / `TimeoutError` / `OSError` を `FeedFetchError` に変換する（メッセージ例: `HTTP 404`、`接続できません: <理由>`、`タイムアウト`）。
- `fetch_feed`: `fetch` → `parse_feed` を行い、`RssReaderError` を捕捉して `FeedResult(error=...)` を返す。例外を外に出さない。
- `fetch_all`: `ThreadPoolExecutor(max_workers=MAX_WORKERS)` で並列実行し、結果を `urls` の順序で返す。

### 3.5 `readstate.py`

```python
READ_FILENAME = "read.json"

class ReadStore:
    def __init__(self, path: Path) -> None   # 読み込みまで行う
    def is_read(self, link: str) -> bool
    def mark_read(self, links: Iterable[str]) -> None   # 変更後すぐ保存
    def mark_unread(self, link: str) -> None            # 変更後すぐ保存
    load_warning: str | None                 # 読み込み時の警告（GUIのステータスに表示）
```

- ファイル形式:

  ```json
  {"version": 1, "read": {"https://example.com/a": "2026-11-08T12:30:00+00:00"}}
  ```

  値は既読にした日時（将来の古いデータ整理用。現時点では削除処理はしない）。
- ファイルが無ければ空で開始する。
- JSON が壊れている／形式が違う場合は `read.json.bak` にリネームして退避し、空で開始する。`load_warning` に「既読情報が壊れていたため初期化しました」を設定する。
- 保存は同じフォルダの一時ファイルへ書き込み後 `os.replace` で置き換える（書き込み途中の破損防止）。保存失敗（`OSError`）は `logging.error` に出し、メモリ上の状態は維持する。

### 3.6 `filtering.py`

```python
def merge_articles(results: list[FeedResult],
                   title_patterns: Mapping[str, Sequence[str]] | None = None) -> list[Article]
def matches_patterns(title: str, patterns: Sequence[str]) -> bool
def sort_articles(articles: list[Article]) -> list[Article]
def filter_articles(articles: list[Article], query: str,
                    unread_only: bool, is_read: Callable[[str], bool]) -> list[Article]
```

- `merge_articles`: 成功したフィードの記事を結合し、同じ `link` の記事は最初の1件のみ残す。
  - `title_patterns` はフィードURL（`FeedResult.url`）→ パターン列の対応。パターンが指定されたフィードの記事は `matches_patterns` が真のものだけを残す。対応が無い、またはパターン列が空のフィードは全記事を残す。
  - パターンによる除外は重複除去より先に行う（フィードAで除外された記事と同じリンクの記事がパターン無しのフィードBにあれば、Bの記事として表示される）。
- `matches_patterns`: パターン列のいずれかについて `pattern.casefold()` が `title.casefold()` に含まれれば真（OR条件）。パターン列が空なら真。
- パターンで除外された記事は一覧の元データ（`App.articles`）に入らないため、絞り込み・未読のみ表示・すべて既読にするの対象にもならない。
- `sort_articles`: `published` の降順。`None` は末尾（その中では元の順序を維持）。
- `filter_articles`: `query.strip().casefold()` が `title.casefold()` に含まれるものを残す。空文字なら全件。`unread_only` が真なら既読を除外する。

### 3.7 `gui.py`

```python
class App:
    def __init__(self, root: tk.Tk, data_dir: Path) -> None
    def refresh_feeds(self) -> None      # 「更新」ボタン・起動時
    def apply_filter(self) -> None       # 一覧の再描画
```

画面レイアウト:

```
┌────────────────────────────────────────────────────────────┐
│ 絞り込み:[__________]  □未読のみ表示   [更新] [すべて既読にする] │
├────────────────────────────────────────────────────────────┤
│ 日時             │ フィード    │ タイトル                      │  ← ttk.Treeview + 縦スクロールバー
│ ...                                                        │
├────────────────────────────────────────────────────────────┤
│ ステータス: 12件のフィードを取得しました（失敗 1件: https://...） │
└────────────────────────────────────────────────────────────┘
```

- ウィンドウタイトル `RSS Reader`、初期サイズ 1200×750。
- 文字サイズ: 定数 `FONT_SIZE = 16`（ポイント）。Tk の標準名前付きフォント `TkDefaultFont` / `TkTextFont` / `TkHeadingFont` / `TkMenuFont` のサイズを変更し、全ウィジェットに反映させる。Treeview の行の高さは自動では追従しないため、`ttk.Style` で `rowheight = フォントの linespace + 8px` を設定する。
- 列幅はフォントから算出する: 日時 = `"2026-11-08 00:00"` の描画幅 + 余白、フィード = 全角12文字分 + 余白（固定）、タイトルは残り（伸縮）。
- 起動時のフォーカスは Treeview に置く。スペース・BackSpace は Treeview にのみバインドし、絞り込み欄での入力を妨げない。
- Treeview の各行の iid は表示中リストのインデックス、値として `Article` を内部の dict で保持する。
- 既読行は tag `read`（`foreground="gray"`）を付ける。
- 操作とイベント:

| 操作 | バインド | 動作 |
|---|---|---|
| 記事をクリック | `<ButtonRelease-1>`（`identify_region` が `cell` の行のみ。見出しや列境界は対象外） | `webbrowser.open(link)` → `mark_read` → その行に `read` tag を付与（「未読のみ表示」中は一覧を再描画） |
| Enter キー | `<Return>` | 選択中の記事をクリックと同様に開く |
| スペースキー | Treeview の `<space>` | `scroll_page(1)`: `yview_scroll(1, "pages")` の後、`yview()[0]` から求めた表示先頭行を選択・フォーカスする。`"break"` を返し既定の処理を抑止 |
| BackSpace キー | Treeview の `<BackSpace>` | `scroll_page(-1)`: 1ページ前へ。以降は同上 |
| 絞り込み欄で Esc | Entry の `<Escape>` | 記事一覧にフォーカスを移す |
| 右クリック | `<Button-3>` | 行を選択し、メニュー「ブラウザで開く」「未読に戻す」を表示 |
| 絞り込み入力 | `StringVar.trace_add("write")` | `apply_filter` |
| 未読のみ表示 | `BooleanVar` の command | `apply_filter` |
| 更新 | ボタン | `refresh_feeds` |
| すべて既読にする | ボタン | 表示中の全記事を `mark_read`（ブラウザは開かない）→ `apply_filter` |

- バックグラウンド取得:
  - `refresh_feeds` は「更新」ボタンを無効化し、ステータスを「取得中…」にして `threading.Thread(daemon=True)` で `fetch_all` を実行する。
  - ワーカーは結果を `queue.Queue` に入れるだけで、ウィジェットには触れない（tkinter はスレッドセーフでないため）。
  - ワーカーは `load_feeds` で得た `FeedConfig` から URL 一覧を `fetch_all` に渡し、取得結果と `{url: title_patterns}` の組をキューに入れる。
  - メインスレッドは `root.after(100, ...)` でキューを監視し、結果を受け取ったら `merge_articles(results, title_patterns)` → `sort_articles` → `apply_filter`、ボタンを再度有効化する。
- ステータスバーの表示:
  - 成功時: `N件のフィードを取得しました（失敗 M件）`。失敗があれば `: URL1, URL2 …`（先頭3件まで）を続ける。失敗の詳細は `logging.warning` にも出す。
  - `ConfigError` 時: そのメッセージを表示し、一覧は空。
  - 有効URL 0件時: `feeds.txt に有効なURLが登録されていません: <path>`。
  - `ReadStore.load_warning` があれば、起動直後の取得結果メッセージの前に `<警告> / <取得結果>` の形で表示する（「取得中…」で上書きされないようにするため）。

### 3.8 `__main__.py`

```python
def build_parser() -> argparse.ArgumentParser
def main(argv: list[str] | None = None) -> int
```

| 引数 | 説明 | 既定値 |
|---|---|---|
| `--data-dir DIR` | `feeds.txt` と `read.json` を置くフォルダ | カレントフォルダ |
| `--version` | `rss_reader <version>` を表示して終了 | — |
| `--help` / `-h` | 使いかたを表示して終了 | — |

| 終了コード | 条件 |
|---|---|
| 0 | 正常終了（ウィンドウを閉じた）、`--help`、`--version` |
| 1 | `--data-dir` が存在しないフォルダ（メッセージを標準エラーに出力） |
| 2 | 不正な引数（argparse 既定の挙動） |

- `logging.basicConfig(level=WARNING)` で標準エラーへ出力する（`.pyw` 起動時は捨てられる）。
- ランチャー名はパッケージ名と別にする（`rss_reader.pyw` だとプロジェクト直下で `import rss_reader` がランチャーを拾ってしまうため）。
- `RSSReader.pyw` は自身のフォルダの `src` を `sys.path` に追加し、`--data-dir` に自身のフォルダを渡して `main` を呼ぶ。

## 4. エラーハンドリング方針

| 発生箇所 | 元の例外 | 変換先 | 利用者への見え方 |
|---|---|---|---|
| config | `FileNotFoundError` | `ConfigError` | ステータスバーにメッセージ |
| config | 不正なインデント行 | — | ログ出力のみ（行は無視） |
| fetcher | `HTTPError` / `URLError` / `TimeoutError` / `OSError` | `FeedFetchError` | `FeedResult.error` → ステータスバーに失敗件数とURL |
| parser | `ParseError` / 未対応ルート | `FeedParseError` | 同上 |
| readstate 読み込み | `json.JSONDecodeError` / 形式不一致 | — | `.bak` に退避し `load_warning` を表示 |
| readstate 保存 | `OSError` | — | ログ出力のみ。動作は継続 |
| ブラウザ起動 | `webbrowser.open` が False | — | ステータスバーに「ブラウザを開けませんでした」。既読にはしない |

- 1フィードの失敗で全体を止めない。GUI のイベントハンドラ内で想定外の例外が出た場合も `report_callback_exception` で `logging.exception` に出し、アプリは継続する。

## 5. パッケージング

- `pyproject.toml`（setuptools、`src` レイアウト）
  - `requires-python = ">=3.10"`、依存パッケージなし
  - バージョンは `rss_reader/__init__.py` の `__version__` を唯一の定義とし、`[tool.setuptools.dynamic] version = {attr = "rss_reader.__version__"}` で参照する
  - `[project.gui-scripts] rss-reader = "rss_reader.__main__:main"`（コンソールを出さない起動コマンド）
- インストールせずに使う場合は `PYTHONPATH=src` で `python -m rss_reader`、または `RSSReader.pyw` をダブルクリックする。

## 6. テスト方針

- フレームワークは標準の `unittest`（`python -m unittest discover -s tests`）。ネットワークには接続しない。
- `test_config.py`: コメント・空行・前後空白・BOM・非HTTP行・重複の扱い、ファイル無しで `ConfigError`、有効0件で空リスト。インデント行の `title:` パターン（スペース/タブのインデント、複数行、前後空白、`TITLE:` の大文字）、パターン無しのフィードは空タプル、無視されるインデント行（URL行より前、`title:` 以外、`title:` の後が空、インデントされた `#` コメント、重複URL行に続く行）。
- `test_parser.py`: RSS 2.0 / RSS 1.0（Shift_JIS）/ Atom の各フィクスチャからフィード名・記事数・タイトル・リンク・日時が取れること。EUC-JP の変換、未知の文字コードで `FeedParseError`。Atom の複数 link から alternate を選ぶこと、相対リンクの絶対化、HTMLエンティティの展開、リンク無し記事の除外、`file:` / `javascript:` / `ftp:` など http(s) 以外のリンクの除外、壊れたXMLと未対応ルートで `FeedParseError`。`parse_date` は RFC 822（タイムゾーン有り/無し）、ISO 8601（`Z`/オフセット/日付のみ）、不正文字列で `None`。
- `test_fetcher.py`: `urlopen` を `unittest.mock.patch` で差し替え、正常時のバイト列取得、HTTPError/URLError/タイムアウトの `FeedFetchError` 変換、`fetch_all` が一部失敗でも全件の `FeedResult` を入力順で返すこと。
- `test_readstate.py`: 一時フォルダでの保存→再読み込み、未読に戻す、ファイル無しで空開始、壊れたJSONで `.bak` 退避と `load_warning` 設定。
- `test_filtering.py`: 重複リンクの除去、日時降順と `None` の末尾配置、大文字小文字を区別しない部分一致、空クエリで全件、未読のみ表示との併用。フィードごとの表示パターン（一致する記事のみ残る、複数パターンのOR、大文字小文字無視、パターン無しのフィードに影響しない、除外された記事と同じリンクが別フィードにあれば残る）。
- GUI（`gui.py`）は単体テストの対象外とし、実装計画の手動動作確認で requirement.md の使いかたと突き合わせる。
