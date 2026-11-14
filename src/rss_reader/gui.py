"""tkinter main window."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from .config import FEEDS_FILENAME, load_feeds
from .fetcher import fetch_all
from .filtering import filter_articles, merge_articles, sort_articles
from .models import Article, ConfigError, FeedResult
from .readstate import READ_FILENAME, ReadStore

logger = logging.getLogger(__name__)

POLL_MS = 100
MAX_FAILED_URLS_SHOWN = 3

FONT_SIZE = 16  # points
FONT_NAMES = ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont")
ROW_PADDING = 8  # extra pixels per Treeview row
CELL_PADDING = 12  # horizontal margin per column, in pixels


class App:
    def __init__(self, root: tk.Tk, data_dir: Path) -> None:
        self.root = root
        self.data_dir = Path(data_dir)
        self.store = ReadStore(self.data_dir / READ_FILENAME)
        self.articles: list[Article] = []
        self.visible: dict[str, Article] = {}
        self._results: queue.Queue[
            tuple[list[FeedResult], dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]
            | ConfigError
        ] = queue.Queue()

        root.title("RSS Reader")
        root.geometry("1200x750")
        root.report_callback_exception = self._report_exception
        self._configure_fonts()
        self._build_widgets()

        # Shown together with the first fetch result so it is not overwritten
        self._startup_notice = self.store.load_warning
        self.refresh_feeds()

    # ---- layout -----------------------------------------------------------

    def _configure_fonts(self) -> None:
        # Enlarge Tk's standard named fonts so every widget (incl. menus) follows
        for name in FONT_NAMES:
            tkfont.nametofont(name).configure(size=FONT_SIZE)
        self.font = tkfont.nametofont("TkDefaultFont")
        # Treeview does not grow its rows with the font; set the height explicitly
        ttk.Style(self.root).configure(
            "Treeview", rowheight=self.font.metrics("linespace") + ROW_PADDING
        )

    def _build_widgets(self) -> None:
        bar = ttk.Frame(self.root, padding=(8, 8, 8, 4))
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(bar, text="絞り込み:").pack(side=tk.LEFT)
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self.apply_filter())
        entry = ttk.Entry(bar, textvariable=self.query, width=30)
        entry.pack(side=tk.LEFT, padx=(4, 12))

        self.unread_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            bar, text="未読のみ表示", variable=self.unread_only, command=self.apply_filter
        ).pack(side=tk.LEFT)

        ttk.Button(bar, text="すべて既読にする", command=self.mark_all_read).pack(side=tk.RIGHT)
        self.refresh_button = ttk.Button(bar, text="更新", command=self.refresh_feeds)
        self.refresh_button.pack(side=tk.RIGHT, padx=(0, 6))

        self.status = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status, anchor=tk.W, padding=(8, 2)).pack(
            side=tk.BOTTOM, fill=tk.X
        )

        body = ttk.Frame(self.root, padding=(8, 0, 8, 0))
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            body, columns=("date", "feed", "title"), show="headings", selectmode="browse"
        )
        self.tree.heading("date", text="日時", anchor=tk.W)
        self.tree.heading("feed", text="フィード", anchor=tk.W)
        self.tree.heading("title", text="タイトル", anchor=tk.W)
        # Column widths follow the font size
        date_width = self.font.measure("2026-11-08 00:00") + 2 * CELL_PADDING
        feed_width = self.font.measure("あ" * 12) + 2 * CELL_PADDING
        self.tree.column("date", width=date_width, minwidth=date_width, stretch=False)
        self.tree.column("feed", width=feed_width, minwidth=feed_width // 2, stretch=False)
        self.tree.column("title", width=feed_width * 4, minwidth=feed_width, stretch=True)
        self.tree.tag_configure("read", foreground="gray")
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.bind("<ButtonRelease-1>", self._on_click)
        self.tree.bind("<Return>", self._on_return)
        self.tree.bind("<Button-3>", self._on_right_click)
        # Bound on the list only, so Space/BackSpace still edit the filter entry
        self.tree.bind("<space>", lambda _e: self.scroll_page(1))
        self.tree.bind("<BackSpace>", lambda _e: self.scroll_page(-1))
        entry.bind("<Escape>", lambda _e: self.tree.focus_set())

        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="ブラウザで開く", command=self._open_selected)
        self.menu.add_command(label="未読に戻す", command=self._mark_selected_unread)

        self.tree.focus_set()

    # ---- feed loading -----------------------------------------------------

    def refresh_feeds(self) -> None:
        self.refresh_button.state(["disabled"])
        self.status.set("取得中…")
        feeds_path = self.data_dir / FEEDS_FILENAME
        threading.Thread(target=self._worker, args=(feeds_path,), daemon=True).start()
        self.root.after(POLL_MS, self._poll_results)

    def _worker(self, feeds_path: Path) -> None:
        # Runs in a background thread: must not touch any widget.
        try:
            feeds = load_feeds(feeds_path)
        except ConfigError as e:
            self._results.put(e)
            return
        if not feeds:
            self._results.put(ConfigError(f"feeds.txt に有効なURLが登録されていません: {feeds_path}"))
            return
        title_patterns = {f.url: f.title_patterns for f in feeds}
        exclude_patterns = {f.url: f.exclude_patterns for f in feeds}
        self._results.put((fetch_all([f.url for f in feeds]), title_patterns, exclude_patterns))

    def _poll_results(self) -> None:
        try:
            result = self._results.get_nowait()
        except queue.Empty:
            self.root.after(POLL_MS, self._poll_results)
            return
        self.refresh_button.state(["!disabled"])
        if isinstance(result, ConfigError):
            self.articles = []
            message = str(result)
        else:
            results, title_patterns, exclude_patterns = result
            self.articles = sort_articles(merge_articles(results, title_patterns, exclude_patterns))
            message = self._summary(results)
        self.apply_filter()
        if self._startup_notice:
            message = f"{self._startup_notice} / {message}"
            self._startup_notice = None
        self.status.set(message)

    def _summary(self, results: list[FeedResult]) -> str:
        failed = [r for r in results if r.error is not None]
        for r in failed:
            logger.warning("フィードの取得に失敗しました: %s (%s)", r.url, r.error)
        text = f"{len(results) - len(failed)}件のフィードを取得しました（失敗 {len(failed)}件）"
        if failed:
            shown = ", ".join(r.url for r in failed[:MAX_FAILED_URLS_SHOWN])
            more = " …" if len(failed) > MAX_FAILED_URLS_SHOWN else ""
            text += f": {shown}{more}"
        return text

    # ---- list rendering ---------------------------------------------------

    def apply_filter(self) -> None:
        shown = filter_articles(
            self.articles, self.query.get(), self.unread_only.get(), self.store.is_read
        )
        self.tree.delete(*self.tree.get_children())
        self.visible = {}
        for i, article in enumerate(shown):
            iid = str(i)
            self.visible[iid] = article
            date = article.published.astimezone().strftime("%Y-%m-%d %H:%M") if article.published else ""
            self.tree.insert(
                "", tk.END, iid=iid,
                values=(date, article.feed_title, article.title),
                tags=("read",) if self.store.is_read(article.link) else (),
            )

    # ---- actions ----------------------------------------------------------

    def open_article(self, iid: str) -> None:
        article = self.visible.get(iid)
        if article is None:
            return
        if not webbrowser.open(article.link):
            self.status.set(f"ブラウザを開けませんでした: {article.link}")
            return
        self.store.mark_read([article.link])
        if self.unread_only.get():
            self.apply_filter()
        else:
            self.tree.item(iid, tags=("read",))

    def mark_all_read(self) -> None:
        self.store.mark_read(a.link for a in self.visible.values())
        self.apply_filter()

    def _on_click(self, event: tk.Event) -> None:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        iid = self.tree.identify_row(event.y)
        if iid:
            self.open_article(iid)

    def scroll_page(self, direction: int) -> str:
        """Scroll the list by one page (1: forward, -1: back) and select the top row."""
        self.tree.yview_scroll(direction, "pages")
        self.tree.update_idletasks()
        children = self.tree.get_children()
        if children:
            # yview()[0] is the fraction of rows scrolled past the top
            top = children[min(round(self.tree.yview()[0] * len(children)), len(children) - 1)]
            self.tree.selection_set(top)
            self.tree.focus(top)
        return "break"  # suppress the default Treeview key handling

    def _on_return(self, _event: tk.Event) -> None:
        self._open_selected()

    def _on_right_click(self, event: tk.Event) -> None:
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.menu.tk_popup(event.x_root, event.y_root)

    def _open_selected(self) -> None:
        for iid in self.tree.selection():
            self.open_article(iid)

    def _mark_selected_unread(self) -> None:
        for iid in self.tree.selection():
            article = self.visible.get(iid)
            if article is not None:
                self.store.mark_unread(article.link)
                self.tree.item(iid, tags=())

    def _report_exception(self, exc_type, exc_value, exc_tb) -> None:
        logger.error("予期しないエラー", exc_info=(exc_type, exc_value, exc_tb))
        self.status.set(f"予期しないエラーが発生しました: {exc_value}")
