# -*- coding: utf-8 -*-
"""
Playwright（実ブラウザ）を使ったページ取得。

requestsライブラリによる単純なHTTPアクセスでは、kabutan.jp側のbot対策と
みられる挙動により、テーブル自体は見つかるものの中身が0件になる、という
症状が実際の環境で確認されている。そのため、ヘッドレスChromiumを実際に
起動してページを読み込み、レンダリング後のHTMLを取得する方式に切り替えた。

初回のみ `playwright install chromium` によるブラウザ本体のダウンロード
（150～300MB程度）が必要。run.bat / run.sh が初回セットアップ時に自動で
実行する（setup_marker ファイルで2回目以降はスキップする）。
"""

import os

from . import config


class BrowserFetcher:
    """
    1回のスクリーナー実行につき1つ生成し、使い終わったら close() する
    （with文で使うのが確実）。

    使い方:
        with BrowserFetcher() as fetcher:
            html = fetcher.get("https://kabutan.jp/...", debug_name="foo.html")
    """

    def __init__(self, headless=True):
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._context = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self):
        if self._playwright is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "playwrightがインストールされていません。"
                "`pip install -r requirements.txt` を実行してください。"
            ) from e

        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self._headless)
            self._context = self._browser.new_context(
                user_agent=config.USER_AGENT,
                locale="ja-JP",
            )
        except Exception as e:
            self.close()
            raise RuntimeError(
                "Chromiumの起動に失敗しました。初回は `playwright install chromium` の"
                "実行が必要です（run.bat/run.shなら自動実行されるはずです）。"
                "エラー詳細: {}".format(e)
            ) from e

    def get(self, url, wait_selector="table", timeout_ms=None, debug_name=None):
        """
        指定URLをブラウザで開き、レンダリング後のHTML文字列を返す。
        wait_selector: このセレクタが出現するまで待つ（Noneなら待たない）。
        見つからなくても例外にはしない（その後の見出し検索側でエラーにする）。
        """
        if self._context is None:
            self.start()
        timeout_ms = timeout_ms or (config.REQUEST_TIMEOUT_SEC * 1000)
        page = self._context.new_page()
        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except Exception:
                    pass
            html = page.content()
        finally:
            page.close()
        if debug_name:
            self._save_debug_html(debug_name, html)
        return html

    @staticmethod
    def _save_debug_html(name, html):
        try:
            os.makedirs(config.RAW_HTML_DEBUG_DIR, exist_ok=True)
            path = os.path.join(config.RAW_HTML_DEBUG_DIR, name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
        except OSError:
            pass  # デバッグ保存の失敗は致命的ではない

    def close(self):
        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        self._context = None
        self._browser = None
        self._playwright = None
