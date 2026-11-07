"""
Frostium — отдельный браузер на движке Chromium (через Qt WebEngine).

Запуск:
    python frostium.py                      напрямую, без прокси
    python frostium.py tor                  через Tor (127.0.0.1:9050, или TOR_PORT=9150 для Tor Browser)
    python frostium.py proxy socks5://h:p   через свой VPN/прокси

В режимах tor и proxy браузер не запустится, если прокси недоступен,
поэтому трафик никогда не уйдёт напрямую.
"""
import os
import re
import socket
import sys
from urllib.parse import quote, urlparse

APP_NAME = "Frostium"
SEARCH_URL = "https://duckduckgo.com/?q="


def resource(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


# ---------------------------------------------------------------- режим сети
def parse_mode(argv):
    mode, proxy = "direct", None
    args = argv[1:]
    if args and args[0].lower() == "tor":
        mode = "tor"
        proxy = ("127.0.0.1", int(os.environ.get("TOR_PORT", "9050")))
    elif args and args[0].lower() == "proxy":
        if len(args) < 2:
            sys.exit("Использование: frostium proxy socks5://host:port")
        u = urlparse(args[1] if "://" in args[1] else "socks5://" + args[1])
        if not u.hostname or not u.port:
            sys.exit("Неверный адрес прокси. Пример: socks5://127.0.0.1:1080")
        mode, proxy = "proxy", (u.hostname, u.port)
    return mode, proxy


def proxy_alive(host, port):
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


MODE, PROXY = parse_mode(sys.argv)

flags = [
    # WebRTC не показывает локальные адреса и не ходит мимо прокси
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    # никакого фонового общения Chromium с кем-либо
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-domain-reliability",
    "--disable-sync",
    "--no-pings",
    "--no-report-upload",
    "--disable-features=OptimizationHints,MediaRouter,InterestFeedContentSuggestions",
]
if PROXY:
    host, port = PROXY
    flags += [
        f"--proxy-server=socks5://{host}:{port}",
        # DNS только через прокси, локальный резолвер не используется
        f"--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE {host}",
    ]
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "") + " " + " ".join(flags)
).strip()

from PyQt6.QtCore import Qt, QUrl  # noqa: E402
from PyQt6.QtGui import QAction, QIcon, QKeySequence  # noqa: E402
from PyQt6.QtWebEngineCore import (  # noqa: E402
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

START_URL = QUrl.fromLocalFile(resource("assets", "startpage.html"))
START_DIR = os.path.normcase(resource("assets"))

STYLE = """
QMainWindow, QWidget#root { background: #cfe6fb; }
QTabWidget::pane { border: 0; }
QTabBar { background: transparent; }
QTabBar::tab {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #e9f5ff, stop:1 #bcdcf6);
    color: #0b2e55; padding: 7px 14px; min-width: 120px; max-width: 220px;
    border: 1px solid #8fb8e0; border-bottom: 0;
    border-top-left-radius: 9px; border-top-right-radius: 9px; margin-right: 2px;
}
QTabBar::tab:selected { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:1 #dff0ff); font-weight: 600; }
QTabBar::tab:hover:!selected { background: #d8ecfd; }
QWidget#bar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #e3f2ff, stop:1 #bfdcf5); border-bottom: 1px solid #8fb8e0; }
QToolButton {
    border: 1px solid #8fb8e0; border-radius: 16px; background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f7fcff, stop:1 #a9d2f3);
    color: #0b4a9c; font-size: 16px; font-weight: bold; min-width: 32px; min-height: 32px;
}
QToolButton:hover { background: #ffffff; border-color: #4d92d6; }
QToolButton:disabled { color: #8fb0d0; background: #dcebf8; }
QToolButton#plus { border-radius: 9px; min-width: 30px; min-height: 24px; margin: 3px; }
QLineEdit {
    border: 1px solid #8fb8e0; border-radius: 16px; padding: 0 14px; min-height: 32px;
    background: rgba(255,255,255,.88); color: #0b2e55; font-size: 15px; selection-background-color: #4d92d6;
}
QLineEdit:focus { border: 1px solid #2a78c8; background: #ffffff; }
QLabel#badge { border-radius: 10px; padding: 4px 10px; font-weight: 700; font-size: 12px; color: white; }
"""


def to_url(text):
    t = text.strip()
    if not t:
        return None
    if re.match(r"^https://", t, re.I):
        return QUrl(t)
    if re.match(r"^http://", t, re.I):
        return QUrl("https://" + t[7:])
    if not re.search(r"\s", t) and re.match(r"^[^\s.]+\.[^\s]{2,}$", t):
        return QUrl("https://" + t)
    return QUrl(SEARCH_URL + quote(t))


def is_start(url):
    return url.isLocalFile() and os.path.normcase(os.path.dirname(url.toLocalFile())) == START_DIR


BLOCK_HTML = (
    "<body style='font-family:Segoe UI,sans-serif;background:#0c4ba3;color:#e6f3ff;"
    "display:grid;place-items:center;height:100vh;margin:0;text-align:center'>"
    "<div><h1>Frostium заблокировал адрес</h1><p>{}</p></div></body>"
)


class Page(QWebEnginePage):
    def __init__(self, profile, window, parent=None):
        super().__init__(profile, parent)
        self.window_ = window
        if hasattr(self, "permissionRequested"):  # Qt >= 6.8
            self.permissionRequested.connect(lambda p: p.deny())
        else:
            self.featurePermissionRequested.connect(
                lambda origin, feature: self.setFeaturePermission(
                    origin, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
                )
            )

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if not is_main_frame:
            return True
        scheme = url.scheme().lower()
        if scheme in ("https", "about", "blob", "data"):
            return True
        if scheme == "file" and is_start(url):
            return True
        self.setHtml(BLOCK_HTML.format("Разрешены только HTTPS-адреса."))
        return False

    def createWindow(self, window_type):
        if window_type in (
            QWebEnginePage.WebWindowType.WebBrowserTab,
            QWebEnginePage.WebWindowType.WebBrowserBackgroundTab,
        ):
            return self.window_.new_tab(None).page()
        return None


class Browser(QMainWindow):
    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(resource("assets", "icon.png")))
        self.resize(1280, 800)

        root = QWidget(objectName="root")
        lay = QVBoxLayout(root)
        lay.setContentsMargins(6, 6, 6, 0)
        lay.setSpacing(0)
        self.setCentralWidget(root)

        self.tabs = QTabWidget(documentMode=True, tabsClosable=True, movable=True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        plus = QToolButton(text="+", objectName="plus")
        plus.clicked.connect(lambda: self.new_tab())
        self.tabs.setCornerWidget(plus, Qt.Corner.TopRightCorner)

        bar = QWidget(objectName="bar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(6)
        self.btn_back = self.tool("◀", "Назад (Alt+←)", lambda: self.view().back())
        self.btn_fwd = self.tool("▶", "Вперёд (Alt+→)", lambda: self.view().forward())
        self.btn_reload = self.tool("⟳", "Обновить (F5)", lambda: self.view().reload())
        self.btn_home = self.tool("⌂", "Домой", lambda: self.view().setUrl(START_URL))
        for b in (self.btn_back, self.btn_fwd, self.btn_reload, self.btn_home):
            row.addWidget(b)
        self.addr = QLineEdit(placeholderText="Найдите в Frostium или введите адрес")
        self.addr.returnPressed.connect(self.navigate)
        row.addWidget(self.addr, 1)

        names = {
            "direct": ("ПРЯМОЕ", "#e08a1e", "Прямое соединение: сайты видят ваш настоящий IP"),
            "tor": ("TOR", "#2e9d4f", "Трафик и DNS идут через Tor"),
            "proxy": ("ПРОКСИ", "#2a78c8", "Трафик и DNS идут через ваш прокси"),
        }
        text, color, tip = names[MODE]
        badge = QLabel(text, objectName="badge", toolTip=tip)
        badge.setStyleSheet(f"background:{color};")
        row.addWidget(badge)

        lay.addWidget(bar)
        lay.addWidget(self.tabs)

        for seq, fn in (
            ("Ctrl+T", lambda: self.new_tab()),
            ("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Ctrl+L", lambda: (self.addr.setFocus(), self.addr.selectAll())),
            ("F5", lambda: self.view().reload()),
            ("Alt+Left", lambda: self.view().back()),
            ("Alt+Right", lambda: self.view().forward()),
            ("Ctrl++", lambda: self.zoom(+0.1)),
            ("Ctrl+=", lambda: self.zoom(+0.1)),
            ("Ctrl+-", lambda: self.zoom(-0.1)),
            ("Ctrl+0", lambda: self.view().setZoomFactor(1.0)),
            ("F11", self.toggle_full),
        ):
            act = QAction(self)
            act.setShortcut(QKeySequence(seq))
            act.triggered.connect(fn)
            self.addAction(act)

        self.new_tab(START_URL)

    # ---- помощники
    def tool(self, text, tip, slot):
        b = QToolButton(text=text, toolTip=tip)
        b.clicked.connect(slot)
        return b

    def view(self):
        return self.tabs.currentWidget()

    def zoom(self, d):
        v = self.view()
        v.setZoomFactor(max(0.3, min(5.0, v.zoomFactor() + d)))

    def toggle_full(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    # ---- вкладки
    def new_tab(self, url=None):
        view = QWebEngineView()
        view.setPage(Page(self.profile, self, view))
        i = self.tabs.addTab(view, "Новая вкладка")
        self.tabs.setCurrentIndex(i)
        view.titleChanged.connect(lambda t, v=view: self.set_title(v, t))
        view.iconChanged.connect(lambda ic, v=view: self.set_icon(v, ic))
        view.urlChanged.connect(lambda u, v=view: self.on_url(v, u))
        view.loadFinished.connect(lambda _ok, v=view: self.update_nav(v))
        if url is not None:
            view.setUrl(url)
        return view

    def close_tab(self, i):
        if self.tabs.count() <= 1:
            self.close()
            return
        w = self.tabs.widget(i)
        self.tabs.removeTab(i)
        w.page().deleteLater()
        w.deleteLater()

    def set_title(self, view, title):
        i = self.tabs.indexOf(view)
        if i >= 0:
            self.tabs.setTabText(i, (title or "Новая вкладка")[:40])
            self.tabs.setTabToolTip(i, title)
            if view is self.view():
                self.setWindowTitle(f"{title} — {APP_NAME}" if title else APP_NAME)

    def set_icon(self, view, icon):
        i = self.tabs.indexOf(view)
        if i >= 0:
            self.tabs.setTabIcon(i, icon)

    def on_url(self, view, url):
        if view is self.view():
            self.show_url(url)
        self.update_nav(view)

    def show_url(self, url):
        self.addr.setText("" if is_start(url) or url.scheme() in ("about", "data") else url.toString())

    def update_nav(self, view):
        if view is self.view():
            h = view.history()
            self.btn_back.setEnabled(h.canGoBack())
            self.btn_fwd.setEnabled(h.canGoForward())

    def on_tab_changed(self, _i):
        v = self.view()
        if v:
            self.show_url(v.url())
            self.update_nav(v)
            self.setWindowTitle(f"{v.title()} — {APP_NAME}" if v.title() else APP_NAME)

    def navigate(self):
        u = to_url(self.addr.text())
        if u:
            self.view().setUrl(u)
            self.view().setFocus()


def on_download(item):
    path, _ = QFileDialog.getSaveFileName(None, "Сохранить файл", item.downloadFileName())
    if not path:
        item.cancel()
        return
    item.setDownloadDirectory(os.path.dirname(path))
    item.setDownloadFileName(os.path.basename(path))
    item.accept()


def make_profile(app):
    profile = QWebEngineProfile(app)  # без имени = приватный профиль: ничего не пишется на диск
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
    profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    ua = re.sub(r"\s*QtWebEngine/\S+", "", profile.httpUserAgent())
    profile.setHttpUserAgent(ua)
    s = profile.settings()
    A = QWebEngineSettings.WebAttribute
    for attr, val in (
        (A.WebGLEnabled, False),
        (A.Accelerated2dCanvasEnabled, False),
        (A.PluginsEnabled, False),
        (A.JavascriptCanAccessClipboard, False),
        (A.JavascriptCanOpenWindows, False),
        (A.DnsPrefetchEnabled, False),
        (A.WebRTCPublicInterfacesOnly, True),
        (A.LocalContentCanAccessRemoteUrls, False),
        (A.ScreenCaptureEnabled, False),
        (A.PdfViewerEnabled, True),
        (A.FullScreenSupportEnabled, True),
    ):
        s.setAttribute(attr, val)
    profile.downloadRequested.connect(on_download)
    return profile


def main():
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(resource("assets", "icon.png")))
    app.setStyleSheet(STYLE)

    if PROXY and not proxy_alive(*PROXY):
        QMessageBox.critical(
            None,
            APP_NAME,
            f"Прокси {PROXY[0]}:{PROXY[1]} недоступен.\n\n"
            "Frostium не запускается без него, чтобы трафик не ушёл напрямую.\n"
            "Для Tor: запустите Tor (порт 9050) или Tor Browser (TOR_PORT=9150).",
        )
        return 1

    win = Browser(make_profile(app))
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
