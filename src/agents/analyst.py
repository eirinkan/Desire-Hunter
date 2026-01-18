"""
Analyst エージェント

コンテンツ分析と製品情報抽出を担当するエージェント。
Gemini を使用して構造化抽出を実現。
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.domain.models import Product
from src.infrastructure.api_clients.gemini_client import GeminiClient
from src.agents.researcher import ResearchResult

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析結果"""

    research: ResearchResult
    product: Optional[Product]
    success: bool
    error_message: str = ""


class AnalystAgent:
    """
    分析・抽出を担当するエージェント

    責務:
    - リサーチ結果の分析
    - 製品情報の構造化抽出
    - 欲求との適合度評価
    """

    def __init__(self, llm_client: Optional[GeminiClient] = None):
        self.llm_client = llm_client or GeminiClient()
        self.extraction_count = 0
        self.success_count = 0

    def analyze(
        self, research: ResearchResult, desire: str
    ) -> AnalysisResult:
        """
        リサーチ結果を分析し、製品情報を抽出

        Args:
            research: リサーチ結果
            desire: ユーザーの欲求

        Returns:
            AnalysisResult
        """
        self.extraction_count += 1

        try:
            # LLMで製品情報を抽出
            product = self.llm_client.extract_product(research.content, desire)

            if product:
                # メタデータを追加
                product.source_url = research.url
                product.source_language = research.language

                self.success_count += 1
                logger.info(
                    f"製品抽出成功: {product.name} (適合度: {product.relevance_score})"
                )

                return AnalysisResult(
                    research=research,
                    product=product,
                    success=True,
                )
            else:
                logger.debug(f"製品情報なし: {research.url}")
                return AnalysisResult(
                    research=research,
                    product=None,
                    success=False,
                    error_message="製品情報が見つかりませんでした",
                )

        except Exception as e:
            logger.error(f"分析エラー: {research.url} - {e}")
            return AnalysisResult(
                research=research,
                product=None,
                success=False,
                error_message=str(e),
            )

    def analyze_batch(
        self,
        research_results: list[ResearchResult],
        desire: str,
        min_relevance_score: int = 5,
    ) -> list[Product]:
        """
        複数のリサーチ結果を一括分析

        Args:
            research_results: リサーチ結果のリスト
            desire: ユーザーの欲求
            min_relevance_score: 最小適合度（これ以下は除外）

        Returns:
            抽出された製品のリスト
        """
        products = []

        for research in research_results:
            result = self.analyze(research, desire)

            if result.success and result.product:
                # 適合度でフィルタリング
                if result.product.relevance_score >= min_relevance_score:
                    products.append(result.product)
                else:
                    logger.debug(
                        f"適合度が低いためスキップ: {result.product.name} "
                        f"(スコア: {result.product.relevance_score})"
                    )

        logger.info(
            f"バッチ分析完了: {len(products)}/{len(research_results)}件 "
            f"(適合度{min_relevance_score}以上)"
        )
        return products

    def rank_products(
        self, products: list[Product], top_n: int = 10
    ) -> list[Product]:
        """
        製品を適合度でランキング

        Args:
            products: 製品のリスト
            top_n: 上位N件を返す

        Returns:
            ランキングされた製品リスト
        """
        # 適合度で降順ソート
        sorted_products = sorted(
            products,
            key=lambda p: p.relevance_score,
            reverse=True,
        )

        return sorted_products[:top_n]

    def deduplicate_products(self, products: list[Product]) -> list[Product]:
        """
        重複製品を除去

        同じ製品名の場合、適合度が高い方を残す。

        Args:
            products: 製品のリスト

        Returns:
            重複除去後の製品リスト
        """
        seen = {}  # name -> product

        for product in products:
            name = product.name.lower().strip()

            if name not in seen:
                seen[name] = product
            else:
                # 既存より適合度が高ければ置き換え
                if product.relevance_score > seen[name].relevance_score:
                    seen[name] = product

        unique_products = list(seen.values())
        removed_count = len(products) - len(unique_products)

        if removed_count > 0:
            logger.info(f"重複除去: {removed_count}件を除去")

        return unique_products

    def filter_by_criteria(
        self,
        products: list[Product],
        min_score: int = 0,
        require_price: bool = False,
        require_official_url: bool = False,
    ) -> list[Product]:
        """
        条件で製品をフィルタリング

        Args:
            products: 製品のリスト
            min_score: 最小適合度
            require_price: 価格が必須かどうか
            require_official_url: 公式URLが必須かどうか

        Returns:
            フィルタリング後の製品リスト
        """
        filtered = []

        for product in products:
            # 適合度チェック
            if product.relevance_score < min_score:
                continue

            # 価格チェック
            if require_price and not product.price:
                continue

            # 公式URLチェック
            if require_official_url and not product.official_url:
                continue

            filtered.append(product)

        logger.info(f"フィルタリング: {len(filtered)}/{len(products)}件")
        return filtered

    def get_statistics(self) -> dict:
        """
        分析統計を取得

        Returns:
            統計情報の辞書
        """
        success_rate = (
            (self.success_count / self.extraction_count * 100)
            if self.extraction_count > 0
            else 0
        )

        return {
            "total_extractions": self.extraction_count,
            "successful_extractions": self.success_count,
            "success_rate": f"{success_rate:.1f}%",
        }

    def reset_statistics(self) -> None:
        """統計をリセット"""
        self.extraction_count = 0
        self.success_count = 0
        logger.debug("分析統計をリセットしました")
