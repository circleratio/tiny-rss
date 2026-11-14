"""tkinter main window."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from .config import FEEDS_FILENAME, load_categories, unique_urls
from .fetcher import fetch_all
from .filtering import articles_by_category, filter_articles
from .models import Article, Category, ConfigError, FeedResult
from .readstate import READ_FILENAME, ReadStore

logger = logging.getLogger(__name__)

POLL_MS = 100
MAX_FAILED_URLS_SHOWN = 3

FONT_SIZE = 16  # points
FONT_NAMES = ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont")
ROW_PADDING = 8  # extra pixels per Treeview row
CELL_PADDING = 12  # horizontal margin per column, in pixels

# Dark palette: the white Windows pointer stands out against it
BG = "#1E2228"
FG = "#E3E5E8"
READ_FG = "#8B929C"
SELECT_BG = "#2D4F7C"
SURFACE = "#2A2F37"  # headings, buttons, entry, scrollbar
BORDER = "#3A414B"
ACTIVE = "#353B45"  # hovered buttons and headings


@dataclass
class _Tab:
    """One category page of the notebook."""

    name: str
    tree: ttk.Treeview
    articles: list[Article]
    visible: dict[str, Article] = field(default_factory=dict)  # iid -> shown article


class App:
    def __init__(self, root: tk.Tk, data_dir: Path) -> None:
        self.root = root
        self.data_dir = Path(data_dir)
        self.store = ReadStore(self.data_dir / READ_FILENAME)
        self.tabs: list[_Tab] = []
        self._results: queue.Queue[
            tuple[list[Category], list[FeedResult]] | ConfigError
        ] = queue.Queue()

        root.title("RSS Reader")
        root.geometry("1200x750")
        root.report_callback_exception = self._report_exception
        # Theme first: style settings are stored per theme
        self._configure_colors()
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
        style = ttk.Style(self.root)
        linespace = self.font.metrics("linespace")
        # Treeview does not grow its rows with the font; set the height explicitly
        style.configure("Treeview", rowheight=linespace + ROW_PADDING)
        # Likewise the check box indicator keeps a fixed size
        style.configure("TCheckbutton", indicatorsize=linespace * 2 // 3)

    def _configure_colors(self) -> None:
        style = ttk.Style(self.root)
        # The native "vista" theme ignores most color options; "clam" honors them
        style.theme_use("clam")
        style.configure(
            ".",
            background=BG,
            foreground=FG,
            fieldbackground=SURFACE,
            bordercolor=BORDER,
            lightcolor=SURFACE,
            darkcolor=SURFACE,
            troughcolor=BG,
            selectbackground=SELECT_BG,
            selectforeground=FG,
            insertcolor=FG,
        )
        style.map(".", background=[("disabled", BG)], foreground=[("disabled", READ_FG)])
        style.configure("Treeview", background=BG, fieldbackground=BG, foreground=FG)
        style.map("Treeview", background=[("selected", SELECT_BG)], foreground=[("selected", FG)])
        style.configure("Treeview.Heading", background=SURFACE, foreground=FG)
        style.map("Treeview.Heading", background=[("active", ACTIVE)])
        style.configure("TButton", background=SURFACE)
        style.map("TButton", background=[("disabled", BG), ("active", ACTIVE)])
        style.configure("TCheckbutton", indicatorbackground=SURFACE, indicatorforeground=FG)
        style.map(
            "TCheckbutton",
            background=[("active", BG)],
            indicatorbackground=[("pressed", ACTIVE), ("active", ACTIVE)],
        )
        style.configure("TNotebook", background=BG)
        style.configure("TNotebook.Tab", background=SURFACE, padding=(12, 4))
        style.map(
            "TNotebook.Tab",
            background=[("selected", SELECT_BG), ("active", ACTIVE)],
            lightcolor=[("selected", SELECT_BG)],
        )
        style.configure("Vertical.TScrollbar", background=SURFACE, arrowcolor=FG)
        style.map("Vertical.TScrollbar", background=[("active", ACTIVE)])
        self.root.configure(background=BG)

    def _build_widgets(self) -> None:
        bar = ttk.Frame(self.root, padding=(8, 8, 8, 4))
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(bar, text="絞り込み:").pack(side=tk.LEFT)
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self.apply_filter())
        self.entry = ttk.Entry(bar, textvariable=self.query, width=30)
        self.entry.pack(side=tk.LEFT, padx=(4, 12))

        self.unread_only = tk.BooleanVar(value=True)
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
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.enable_traversal()  # Ctrl+Tab / Ctrl+Shift+Tab
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.entry.bind("<Escape>", lambda _e: self._focus_list())

        self.menu = tk.Menu(
            self.root,
            tearoff=False,
            background=SURFACE,
            foreground=FG,
            activebackground=SELECT_BG,
            activeforeground=FG,
        )
        self.menu.add_command(label="ブラウザで開く", command=self._open_selected)
        self.menu.add_command(label="未読に戻す", command=self._mark_selected_unread)

    def _add_tab(self, name: str, articles: list[Article]) -> _Tab:
        page = ttk.Frame(self.notebook)
        tree = ttk.Treeview(
            page, columns=("date", "feed", "title"), show="headings", selectmode="browse"
        )
        tree.heading("date", text="日時", anchor=tk.W)
        tree.heading("feed", text="フィード", anchor=tk.W)
        tree.heading("title", text="タイトル", anchor=tk.W)
        # Column widths follow the font size
        date_width = self.font.measure("2026-11-08 00:00") + 2 * CELL_PADDING
        feed_width = self.font.measure("あ" * 12) + 2 * CELL_PADDING
        tree.column("date", width=date_width, minwidth=date_width, stretch=False)
        tree.column("feed", width=feed_width, minwidth=feed_width // 2, stretch=False)
        tree.column("title", width=feed_width * 4, minwidth=feed_width, stretch=True)
        tree.tag_configure("read", foreground=READ_FG)
        scroll = ttk.Scrollbar(page, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tree.bind("<ButtonRelease-1>", self._on_click)
        tree.bind("<Return>", self._on_return)
        tree.bind("<Button-3>", self._on_right_click)
        # Bound on the list only, so Space/BackSpace still edit the filter entry
        tree.bind("<space>", lambda _e: self.scroll_page(1))
        tree.bind("<BackSpace>", lambda _e: self.scroll_page(-1))

        self.notebook.add(page, text=name)
        tab = _Tab(name, tree, articles)
        self.tabs.append(tab)
        return tab

    def _show_tabs(self, tabs: list[tuple[str, list[Article]]]) -> None:
        """Rebuild the notebook, keeping the previously selected category selected."""
        current = self._current()
        selected = current.name if current else None
        old, self.tabs = self.tabs, []
        for tab in old:
            tab.tree.master.destroy()  # destroying the page removes its tab
        for name, articles in tabs:
            tab = self._add_tab(name, articles)
            if name == selected:
                self.notebook.select(tab.tree.master)
        self.apply_filter()
        if self.root.focus_get() is not self.entry:
            self._focus_list()

    def _current(self) -> _Tab | None:
        if not self.tabs:
            return None
        return self.tabs[self.notebook.index("current")]

    def _focus_list(self) -> None:
        tab = self._current()
        if tab is not None:
            tab.tree.focus_set()

    def _on_tab_changed(self, _event: tk.Event) -> None:
        self.apply_filter()
        # Clicking a tab focuses the tab itself, which would swallow Space/BackSpace
        if self.root.focus_get() is not self.entry:
            self._focus_list()

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
            categories = load_categories(feeds_path)
        except ConfigError as e:
            self._results.put(e)
            return
        if not categories:
            self._results.put(ConfigError(f"feeds.txt に有効なURLが登録されていません: {feeds_path}"))
            return
        self._results.put((categories, fetch_all(unique_urls(categories))))

    def _poll_results(self) -> None:
        try:
            result = self._results.get_nowait()
        except queue.Empty:
            self.root.after(POLL_MS, self._poll_results)
            return
        self.refresh_button.state(["!disabled"])
        if isinstance(result, ConfigError):
            self._show_tabs([])
            message = str(result)
        else:
            categories, results = result
            self._show_tabs(articles_by_category(categories, results))
            message = self._summary(results)
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
        """Redraw the selected tab only; other tabs are redrawn when selected."""
        tab = self._current()
        if tab is None:
            return
        shown = filter_articles(
            tab.articles, self.query.get(), self.unread_only.get(), self.store.is_read
        )
        tab.tree.delete(*tab.tree.get_children())
        tab.visible = {}
        for i, article in enumerate(shown):
            iid = str(i)
            tab.visible[iid] = article
            date = article.published.astimezone().strftime("%Y-%m-%d %H:%M") if article.published else ""
            tab.tree.insert(
                "", tk.END, iid=iid,
                values=(date, article.feed_title, article.title),
                tags=("read",) if self.store.is_read(article.link) else (),
            )

    # ---- actions ----------------------------------------------------------

    def open_article(self, iid: str) -> None:
        tab = self._current()
        article = tab.visible.get(iid) if tab else None
        if article is None:
            return
        if not webbrowser.open(article.link):
            self.status.set(f"ブラウザを開けませんでした: {article.link}")
            return
        self.store.mark_read([article.link])
        if self.unread_only.get():
            self.apply_filter()
        else:
            tab.tree.item(iid, tags=("read",))

    def mark_all_read(self) -> None:
        tab = self._current()
        if tab is None:
            return
        self.store.mark_read(a.link for a in tab.visible.values())
        self.apply_filter()

    def _on_click(self, event: tk.Event) -> None:
        tree = event.widget
        if tree.identify_region(event.x, event.y) != "cell":
            return
        iid = tree.identify_row(event.y)
        if iid:
            self.open_article(iid)

    def scroll_page(self, direction: int) -> str:
        """Scroll the list by one page (1: forward, -1: back) and select the top row."""
        tab = self._current()
        if tab is None:
            return "break"
        tree = tab.tree
        tree.yview_scroll(direction, "pages")
        tree.update_idletasks()
        children = tree.get_children()
        if children:
            # yview()[0] is the fraction of rows scrolled past the top
            top = children[min(round(tree.yview()[0] * len(children)), len(children) - 1)]
            tree.selection_set(top)
            tree.focus(top)
        return "break"  # suppress the default Treeview key handling

    def _on_return(self, _event: tk.Event) -> None:
        self._open_selected()

    def _on_right_click(self, event: tk.Event) -> None:
        tree = event.widget
        iid = tree.identify_row(event.y)
        if not iid:
            return
        tree.selection_set(iid)
        tree.focus(iid)
        self.menu.tk_popup(event.x_root, event.y_root)

    def _open_selected(self) -> None:
        tab = self._current()
        if tab is None:
            return
        for iid in tab.tree.selection():
            self.open_article(iid)

    def _mark_selected_unread(self) -> None:
        tab = self._current()
        if tab is None:
            return
        for iid in tab.tree.selection():
            article = tab.visible.get(iid)
            if article is not None:
                self.store.mark_unread(article.link)
                tab.tree.item(iid, tags=())

    def _report_exception(self, exc_type, exc_value, exc_tb) -> None:
        logger.error("予期しないエラー", exc_info=(exc_type, exc_value, exc_tb))
        self.status.set(f"予期しないエラーが発生しました: {exc_value}")
