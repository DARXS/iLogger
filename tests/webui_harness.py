"""Harness E2E: sobe o servidor, abre a UI no Chromium (Qt WebEngine, offscreen), executa JS e captura telas/erros."""

from __future__ import annotations

import os
import socket
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu --disable-dev-shm-usage --disable-software-rasterizer")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class UiSession:
    def __init__(self, data_dir: Path | None = None, size=(1500, 900)):
        import uvicorn
        from PyQt6.QtCore import QUrl
        from PyQt6.QtWebEngineCore import QWebEnginePage
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWidgets import QApplication

        from mangue_logger.web.server import create_app
        from mangue_logger.web.state import AppService

        self.data_dir = data_dir or Path(tempfile.mkdtemp())
        self.console: list[tuple[int, str, int, str]] = []
        self.app = QApplication.instance() or QApplication(["mangue-ui"])
        self.port = free_port()
        self.server = uvicorn.Server(uvicorn.Config(create_app(AppService(self.data_dir)), host="127.0.0.1", port=self.port, log_level="error"))
        threading.Thread(target=self.server.run, daemon=True).start()
        for _ in range(200):
            if self.server.started:
                break
            time.sleep(0.03)
        outer = self

        class Page(QWebEnginePage):
            def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
                outer.console.append((int(level.value) if hasattr(level, "value") else int(level), message, line, source))

        self.view = QWebEngineView()
        self.page = Page(self.view)
        self.view.setPage(self.page)
        self.view.resize(*size)
        self.view.show()
        self.url = f"http://127.0.0.1:{self.port}"
        loaded = []
        self.page.loadFinished.connect(lambda ok: loaded.append(ok))
        self.view.load(QUrl(self.url + "/"))
        self.pump(until=lambda: bool(loaded), timeout=15)

    def pump(self, secs: float = 0.0, until=None, timeout: float = 10.0):
        end = time.time() + (secs if until is None else timeout)
        while time.time() < end:
            self.app.processEvents()
            if until is not None and until():
                return True
            time.sleep(0.01)
        return until is None

    def js(self, code: str, timeout: float = 15.0):
        """Executa JS (expressão ou async IIFE) e devolve o resultado."""
        box: list = []
        wrapped = f"(async () => {{ {code} }})()"
        self.page.runJavaScript(f"Promise.resolve({wrapped}).then(v => window.__r = v).catch(e => window.__r = '__ERR__' + e)", lambda v: None)
        end = time.time() + timeout
        while time.time() < end:
            self.app.processEvents()
            self.page.runJavaScript("window.__r", box.append)
            self.pump(0.05)
            if box and box[-1] is not None:
                self.page.runJavaScript("window.__r = undefined")
                self.pump(0.02)
                return box[-1]
            box.clear()
        raise TimeoutError(code[:80])

    def goto(self, view: str, settle: float = 1.2):
        self.js(f"location.hash = '#/{view}'; return 1")
        self.pump(settle)

    def shot(self, path: str):
        self.pump(0.2)
        self.view.grab().save(path)

    def errors(self) -> list[str]:
        return [f"{m} ({s.rsplit('/', 1)[-1]}:{ln})" for lvl, m, ln, s in self.console if lvl >= 2]

    def close(self):
        self.server.should_exit = True
        self.view.close()
