"""
Researcher エージェント

検索と閲覧を担当するエージェント。
Serper（検索）とFirecrawl（閲覧）を組み合わせて
欲求に関連する製品情報を収集。
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.core.config import settings
from src.domain.models import SearchResult, TranslatedQuery
from src.infrastructure.api_clients.serper_client import SerperClient
from src.infrastructure.api_clients.firecrawl_client import FirecrawlClient

logger = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    """リサーチ結果"""

    url: str
    content: str
    language: str
    query: str
    search_position: int


class ResearcherAgent:
    """
    検索・閲覧を担当するエージェント

    責務:
    - 多言語検索クエリの実行
    - 検索結果URLのスクレイピング
    - コンテンツの収集と整理
    """

    def __init__(
        self,
        search_client: Optional[SerperClient] = None,
        scraper_client: Optional[FirecrawlClient] = None,
    ):
        self.search_client = search_client or SerperClient()
        self.scraper_client = scraper_client or FirecrawlClient()
        self.visited_urls: set[str] = set()  # 重複訪問防止

    def search_for_desire(
        self,
        desire: str,
        languages: list[str] = None,
        results_per_language: int = 5,
    ) -> list[SearchResult]:
        """
        欲求に基づいて多言語検索を実行

        Args:
            desire: 検索する欲求
            languages: 検索する言語のリスト
            results_per_language: 各言語での検索結果数

        Returns:
            全言語の検索結果を統合したリスト
        """
        languages = languages or settings.search_languages
        all_results = []

        for lang in languages:
            try:
                # 言語に応じた検索クエリを構築
                query = self._build_query_for_language(desire, lang)
                results = self.search_client.search_in_language(
                    query, lang, results_per_language
                )

                # 言語情報を付加
                for result in results:
                    result.language = lang  # type: ignore

                all_results.extend(results)
                logger.info(f"検索完了 ({lang}): {len(results)}件")

            except Exception as e:
                logger.error(f"検索エラー ({lang}): {e}")
                continue

        # 重複URLを除去
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

        logger.info(f"検索完了: 合計 {len(unique_results)}件 (重複除去後)")
        return unique_results

    def _build_query_for_language(self, desire: str, language: str) -> str:
        """
        言語に応じた検索クエリを構築

        Args:
            desire: 元の欲求
            language: 言語コード

        Returns:
            検索クエリ
        """
        # 言語ごとの製品検索キーワード
        product_keywords = {
            "en": "buy product shop",
            "zh": "购买 产品 商店",
            "de": "kaufen produkt shop",
            "ja": "購入 製品 ショップ",
            "fr": "acheter produit boutique",
            "es": "comprar producto tienda",
            "ko": "구매 제품 쇼핑",
        }

        keyword = product_keywords.get(language, "buy product")
        return f"{desire} {keyword}"

    def research_url(
        self, url: str, language: str = "en", query: str = ""
    ) -> Optional[ResearchResult]:
        """
        単一URLをリサーチ

        Args:
            url: リサーチ対象URL
            language: 言語コード
            query: 使用した検索クエリ

        Returns:
            ResearchResult または None
        """
        # 重複訪問チェック
        if url in self.visited_urls:
            logger.debug(f"既に訪問済み: {url}")
            return None

        self.visited_urls.add(url)

        try:
            content = self.scraper_client.scrape_with_fallback(url)

            if not content or len(content) < 100:
                logger.warning(f"コンテンツが不十分: {url}")
                return None

            return ResearchResult(
                url=url,
                content=content,
                language=language,
                query=query,
                search_position=0,
            )

        except Exception as e:
            logger.error(f"リサーチエラー: {url} - {e}")
            return None

    def research_search_results(
        self,
        search_results: list[SearchResult],
        max_results: int = 10,
    ) -> list[ResearchResult]:
        """
        検索結果のURLをまとめてリサーチ

        Args:
            search_results: 検索結果のリスト
            max_results: リサーチする最大件数

        Returns:
            ResearchResult のリスト
        """
        research_results = []
        count = 0

        for result in search_results:
            if count >= max_results:
                break

            research = self.research_url(
                url=result.url,
                language=getattr(result, "language", "en"),
                query=result.snippet,
            )

            if research:
                research.search_position = result.position
                research_results.append(research)
                count += 1

        logger.info(f"リサーチ完了: {len(research_results)}/{len(search_results)}件")
        return research_results

    def deep_research(
        self,
        base_url: str,
        language: str = "en",
        max_pages: int = 3,
    ) -> list[ResearchResult]:
        """
        サイトを深掘りリサーチ

        サイトマップを取得し、複数ページをスクレイピング。

        Args:
            base_url: サイトのベースURL
            language: 言語コード
            max_pages: 取得する最大ページ数

        Returns:
            ResearchResult のリスト
        """
        results = []

        try:
            # サイトマップを取得
            urls = self.scraper_client.map_site(base_url)

            if not urls:
                # サイトマップが取得できない場合、元のURLのみ
                research = self.research_url(base_url, language)
                if research:
                    results.append(research)
                return results

            # 製品ページっぽいURLを優先
            product_urls = self._filter_product_urls(urls)
            target_urls = product_urls[:max_pages] if product_urls else urls[:max_pages]

            for url in target_urls:
                research = self.research_url(url, language)
                if research:
                    results.append(research)

            logger.info(f"深掘りリサーチ完了: {base_url} -> {len(results)}ページ")

        except Exception as e:
            logger.error(f"深掘りリサーチエラー: {base_url} - {e}")

        return results

    def _filter_product_urls(self, urls: list[str]) -> list[str]:
        """
        製品ページと思われるURLをフィルタリング

        Args:
            urls: URLのリスト

        Returns:
            製品ページのURL
        """
        product_keywords = [
            "product",
            "item",
            "goods",
            "shop",
            "buy",
            "detail",
            "p/",
            "pd/",
            "/dp/",
        ]

        product_urls = []
        for url in urls:
            url_lower = url.lower()
            if any(kw in url_lower for kw in product_keywords):
                product_urls.append(url)

        return product_urls

    def execute_research(
        self,
        translated_queries: list[TranslatedQuery],
        results_per_query: int = 5,
        max_total_results: int = 20,
    ) -> list[ResearchResult]:
        """
        翻訳されたクエリでリサーチを実行

        Args:
            translated_queries: 翻訳されたクエリのリスト
            results_per_query: 各クエリでの検索結果数
            max_total_results: 最大リサーチ件数

        Returns:
            ResearchResult のリスト
        """
        all_research = []

        for query in translated_queries:
            try:
                # 検索実行
                search_results = self.search_client.search_in_language(
                    query.query, query.language, results_per_query
                )

                # 検索結果をリサーチ
                for result in search_results:
                    if len(all_research) >= max_total_results:
                        break

                    research = self.research_url(
                        url=result.url,
                        language=query.language,
                        query=query.query,
                    )

                    if research:
                        research.search_position = result.position
                        all_research.append(research)

                if len(all_research) >= max_total_results:
                    break

            except Exception as e:
                logger.error(f"クエリ実行エラー ({query.language}): {e}")
                continue

        logger.info(f"リサーチ実行完了: {len(all_research)}件")
        return all_research

    def reset_visited(self) -> None:
        """訪問済みURLをリセット"""
        self.visited_urls.clear()
        logger.debug("訪問済みURLをリセットしました")
