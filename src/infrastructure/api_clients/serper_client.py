"""
Serper APIクライアント

Google検索結果を取得するためのクライアント。
レート制限とリトライ機能付き。
"""

import logging
from typing import Optional

import requests
from ratelimit import limits, sleep_and_retry
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

from src.core.config import settings
from src.core.interfaces import SearchClient
from src.domain.models import SearchResult

logger = logging.getLogger(__name__)

# Serper API エンドポイント
SERPER_API_URL = "https://google.serper.dev/search"


class SerperClient(SearchClient):
    """
    Serper APIを使用した検索クライアント

    Google検索結果をJSON形式で取得。
    レート制限とリトライ機能を備える。
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.serper_api_key
        self.rate_limit = settings.serper_rate_limit

    @sleep_and_retry
    @limits(calls=10, period=60)  # 10回/分のレート制限
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type(
            (requests.ConnectionError, requests.Timeout, requests.HTTPError)
        ),
        before_sleep=lambda retry_state: logger.warning(
            f"Serper API リトライ: {retry_state.attempt_number}回目"
        ),
    )
    def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        """
        Google検索を実行

        Args:
            query: 検索クエリ
            num_results: 取得する結果数（最大100）

        Returns:
            SearchResult のリスト
        """
        if not self.api_key:
            logger.error("Serper APIキーが設定されていません")
            return []

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "q": query,
            "num": min(num_results, 100),  # 最大100件
        }

        try:
            response = requests.post(
                SERPER_API_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            results = []

            # オーガニック検索結果を処理
            organic_results = data.get("organic", [])
            for i, item in enumerate(organic_results):
                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    position=i + 1,
                )
                results.append(result)

            logger.info(f"検索完了: '{query}' -> {len(results)}件")
            return results

        except requests.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning("Serper API レート制限に到達")
                raise  # リトライさせる
            logger.error(f"Serper API HTTPエラー: {e}")
            return []
        except requests.RequestException as e:
            logger.error(f"Serper API リクエストエラー: {e}")
            raise  # リトライさせる
        except Exception as e:
            logger.error(f"Serper API 予期しないエラー: {e}")
            return []

    def search_products(
        self, query: str, num_results: int = 10
    ) -> list[SearchResult]:
        """
        製品検索に特化した検索

        クエリに「buy」「shop」などのキーワードを追加して
        ECサイトの結果を優先的に取得。

        Args:
            query: 検索クエリ
            num_results: 取得する結果数

        Returns:
            SearchResult のリスト
        """
        # 製品検索用のクエリを構築
        product_query = f"{query} buy shop product"
        return self.search(product_query, num_results)

    def search_in_language(
        self, query: str, language: str, num_results: int = 10
    ) -> list[SearchResult]:
        """
        特定言語での検索

        Args:
            query: 検索クエリ
            language: 言語コード（en, zh, de, ja等）
            num_results: 取得する結果数

        Returns:
            SearchResult のリスト
        """
        if not self.api_key:
            logger.error("Serper APIキーが設定されていません")
            return []

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        # 言語コードをGoogle検索のフォーマットに変換
        gl_mapping = {
            "en": "us",
            "zh": "cn",
            "de": "de",
            "ja": "jp",
            "fr": "fr",
            "es": "es",
            "ko": "kr",
        }

        hl_mapping = {
            "en": "en",
            "zh": "zh-cn",
            "de": "de",
            "ja": "ja",
            "fr": "fr",
            "es": "es",
            "ko": "ko",
        }

        payload = {
            "q": query,
            "num": min(num_results, 100),
            "gl": gl_mapping.get(language, "us"),
            "hl": hl_mapping.get(language, "en"),
        }

        try:
            response = requests.post(
                SERPER_API_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            results = []

            organic_results = data.get("organic", [])
            for i, item in enumerate(organic_results):
                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    position=i + 1,
                )
                results.append(result)

            logger.info(f"言語検索完了 ({language}): '{query}' -> {len(results)}件")
            return results

        except Exception as e:
            logger.error(f"言語検索エラー ({language}): {e}")
            return []
