"""
Firecrawl APIクライアント

Webページのスクレイピングとサイトマップ取得を担当。
動的サイトにも対応し、LLM向けのMarkdown形式で出力。
"""

import logging
from typing import Optional

from firecrawl import Firecrawl
from ratelimit import limits, sleep_and_retry
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

from src.core.config import settings
from src.core.interfaces import WebScraperClient

logger = logging.getLogger(__name__)


class FirecrawlError(Exception):
    """Firecrawl固有のエラー"""

    pass


class FirecrawlClient(WebScraperClient):
    """
    Firecrawl v1 APIを使用したWebスクレイピングクライアント

    特徴:
    - 動的サイト（JavaScript）に対応
    - LLM向けにMarkdown形式で出力
    - /map でサイト構造を把握
    - /scrape で詳細コンテンツを取得
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.firecrawl_api_key
        self.app = Firecrawl(api_key=self.api_key) if self.api_key else None

    @sleep_and_retry
    @limits(calls=5, period=60)  # 5回/分のレート制限
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            f"Firecrawl scrape リトライ: {retry_state.attempt_number}回目"
        ),
    )
    def scrape(self, url: str) -> str:
        """
        URLからコンテンツを取得してMarkdown形式で返す

        Args:
            url: スクレイピング対象URL

        Returns:
            Markdown形式のコンテンツ

        Raises:
            FirecrawlError: スクレイピングに失敗した場合
        """
        if not self.app:
            logger.error("Firecrawl APIキーが設定されていません")
            return ""

        try:
            logger.info(f"スクレイピング開始: {url}")

            result = self.app.scrape(url, formats=["markdown"])

            if result and hasattr(result, "markdown") and result.markdown:
                content = result.markdown
                logger.info(f"スクレイピング完了: {url} ({len(content)}文字)")
                return content
            elif result and isinstance(result, dict) and "markdown" in result:
                content = result["markdown"]
                logger.info(f"スクレイピング完了: {url} ({len(content)}文字)")
                return content
            else:
                logger.warning(f"コンテンツが取得できませんでした: {url}")
                return ""

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                logger.warning(f"Firecrawl レート制限: {url}")
                raise  # リトライさせる
            logger.error(f"Firecrawl スクレイピングエラー: {url} - {e}")
            raise FirecrawlError(f"スクレイピング失敗: {url}") from e

    @sleep_and_retry
    @limits(calls=3, period=60)  # 3回/分のレート制限（mapは重い）
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=60),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            f"Firecrawl map リトライ: {retry_state.attempt_number}回目"
        ),
    )
    def map_site(self, url: str) -> list[str]:
        """
        サイトのURLマップを取得

        Args:
            url: 対象サイトのURL

        Returns:
            サイト内のURLリスト
        """
        if not self.app:
            logger.error("Firecrawl APIキーが設定されていません")
            return []

        try:
            logger.info(f"サイトマップ取得開始: {url}")

            result = self.app.map_url(url)

            if result and "links" in result:
                urls = result["links"]
                logger.info(f"サイトマップ取得完了: {url} ({len(urls)}件)")
                return urls[:50]  # 最大50件に制限
            else:
                logger.warning(f"サイトマップが取得できませんでした: {url}")
                return []

        except Exception as e:
            logger.error(f"Firecrawl マップエラー: {url} - {e}")
            return []

    def scrape_with_fallback(self, url: str) -> str:
        """
        フォールバック付きスクレイピング

        Firecrawlが失敗した場合、シンプルなrequestsでフォールバック。

        Args:
            url: スクレイピング対象URL

        Returns:
            コンテンツ（Markdown or HTML）
        """
        try:
            return self.scrape(url)
        except Exception:
            logger.warning(f"Firecrawl失敗、フォールバック試行: {url}")
            return self._fallback_scrape(url)

    def _fallback_scrape(self, url: str) -> str:
        """
        シンプルなrequestsによるフォールバックスクレイピング

        Args:
            url: スクレイピング対象URL

        Returns:
            HTMLコンテンツ
        """
        import requests

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # 簡易的なHTML→テキスト変換
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self.skip_tags = {"script", "style", "head", "meta", "link"}
                    self.current_tag = None

                def handle_starttag(self, tag, attrs):
                    self.current_tag = tag

                def handle_data(self, data):
                    if self.current_tag not in self.skip_tags:
                        text = data.strip()
                        if text:
                            self.text_parts.append(text)

            extractor = TextExtractor()
            extractor.feed(response.text)
            content = "\n".join(extractor.text_parts)

            logger.info(f"フォールバックスクレイピング完了: {url} ({len(content)}文字)")
            return content

        except Exception as e:
            logger.error(f"フォールバックスクレイピングも失敗: {url} - {e}")
            return ""

    def scrape_product_pages(
        self, base_url: str, max_pages: int = 5
    ) -> list[tuple[str, str]]:
        """
        製品ページを複数スクレイピング

        サイトマップから製品ページを特定し、コンテンツを取得。

        Args:
            base_url: サイトのベースURL
            max_pages: 取得する最大ページ数

        Returns:
            (URL, コンテンツ) のタプルリスト
        """
        results = []

        # まずサイトマップを取得
        urls = self.map_site(base_url)

        # 製品ページっぽいURLをフィルタリング
        product_keywords = ["product", "item", "goods", "shop", "buy"]
        filtered_urls = []
        for url in urls:
            url_lower = url.lower()
            if any(kw in url_lower for kw in product_keywords):
                filtered_urls.append(url)

        # 製品ページがなければ元のURLリストを使用
        target_urls = filtered_urls[:max_pages] if filtered_urls else urls[:max_pages]

        for url in target_urls:
            try:
                content = self.scrape_with_fallback(url)
                if content:
                    results.append((url, content))
            except Exception as e:
                logger.warning(f"ページスクレイピング失敗: {url} - {e}")
                continue

        return results
