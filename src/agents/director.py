"""
Director エージェント

全体の指揮・統合を担当するエージェント。
欲求の受け取りから製品データの保存まで、
全プロセスをオーケストレーション。
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from src.core.config import settings
from src.domain.models import Product, DesireAnalysis
from src.infrastructure.api_clients.gemini_client import GeminiClient
from src.infrastructure.repositories.gsheets_repo import GSheetsProductRepository
from src.agents.researcher import ResearcherAgent
from src.agents.analyst import AnalystAgent

logger = logging.getLogger(__name__)


@dataclass
class HuntResult:
    """ハント結果"""

    desire: str
    products: list[Product] = field(default_factory=list)
    total_searched: int = 0
    total_researched: int = 0
    total_extracted: int = 0
    total_saved: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """結果のサマリーを返す"""
        return (
            f"欲求: {self.desire}\n"
            f"検索: {self.total_searched}件\n"
            f"リサーチ: {self.total_researched}件\n"
            f"抽出: {self.total_extracted}件\n"
            f"保存: {self.total_saved}件\n"
            f"エラー: {len(self.errors)}件"
        )


class DirectorAgent:
    """
    全体統括エージェント

    責務:
    - 欲求の分析・翻訳
    - 各エージェントの協調
    - 結果の集約・保存
    - エラーハンドリング
    """

    def __init__(
        self,
        llm_client: Optional[GeminiClient] = None,
        researcher: Optional[ResearcherAgent] = None,
        analyst: Optional[AnalystAgent] = None,
        repository: Optional[GSheetsProductRepository] = None,
    ):
        self.llm_client = llm_client or GeminiClient()
        self.researcher = researcher or ResearcherAgent()
        self.analyst = analyst or AnalystAgent()
        self.repository = repository

    def hunt(
        self,
        desire: str,
        max_products: int = None,
        min_relevance_score: int = 5,
        save_to_sheets: bool = True,
    ) -> HuntResult:
        """
        欲求に基づいて製品を探索

        メインのエントリーポイント。
        欲求を受け取り、検索→リサーチ→分析→保存の
        全プロセスを実行。

        Args:
            desire: ユーザーの欲求
            max_products: 取得する最大製品数
            min_relevance_score: 最小適合度
            save_to_sheets: Google Sheetsに保存するか

        Returns:
            HuntResult
        """
        max_products = max_products or settings.max_products_per_desire
        result = HuntResult(desire=desire)

        logger.info(f"=== ハント開始: {desire} ===")

        try:
            # Step 1: 欲求の分析・翻訳
            logger.info("Step 1: 欲求を分析中...")
            analysis = self._analyze_desire(desire)

            if not analysis.translated_queries:
                # 翻訳クエリがない場合、デフォルト生成
                queries = self.llm_client.generate_search_queries(
                    desire, settings.search_languages
                )
                analysis.translated_queries = queries

            logger.info(f"翻訳クエリ: {len(analysis.translated_queries)}件")

            # Step 2: 検索・リサーチ
            logger.info("Step 2: 検索・リサーチ中...")
            research_results = self.researcher.execute_research(
                translated_queries=analysis.translated_queries,
                results_per_query=5,
                max_total_results=max_products * 2,  # 余裕を持って取得
            )

            result.total_searched = len(analysis.translated_queries) * 5
            result.total_researched = len(research_results)
            logger.info(f"リサーチ完了: {result.total_researched}件")

            # Step 3: 分析・抽出
            logger.info("Step 3: 製品情報を抽出中...")
            products = self.analyst.analyze_batch(
                research_results=research_results,
                desire=desire,
                min_relevance_score=min_relevance_score,
            )

            # 重複除去とランキング
            products = self.analyst.deduplicate_products(products)
            products = self.analyst.rank_products(products, max_products)

            result.products = products
            result.total_extracted = len(products)
            logger.info(f"抽出完了: {result.total_extracted}件")

            # Step 4: 保存
            if save_to_sheets and self.repository and products:
                logger.info("Step 4: Google Sheetsに保存中...")
                try:
                    self.repository.save_batch(products)
                    result.total_saved = len(products)
                    logger.info(f"保存完了: {result.total_saved}件")
                except Exception as e:
                    error_msg = f"保存エラー: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            logger.info(f"=== ハント完了 ===\n{result.summary()}")

        except Exception as e:
            error_msg = f"ハントエラー: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        return result

    def _analyze_desire(self, desire: str) -> DesireAnalysis:
        """
        欲求を分析

        Args:
            desire: ユーザーの欲求

        Returns:
            DesireAnalysis
        """
        try:
            return self.llm_client.analyze_desire(desire)
        except Exception as e:
            logger.warning(f"欲求分析エラー: {e}")
            # フォールバック: 基本的な分析結果を返す
            return DesireAnalysis(
                original_desire=desire,
                refined_desire=desire,
                keywords=[desire],
                category="",
                translated_queries=[],
            )

    def hunt_batch(
        self,
        desires: list[str],
        max_products_per_desire: int = None,
        min_relevance_score: int = 5,
    ) -> list[HuntResult]:
        """
        複数の欲求を一括処理

        Args:
            desires: 欲求のリスト
            max_products_per_desire: 各欲求での最大製品数
            min_relevance_score: 最小適合度

        Returns:
            HuntResult のリスト
        """
        results = []

        for i, desire in enumerate(desires, 1):
            logger.info(f"--- バッチ処理: {i}/{len(desires)} ---")

            # リサーチャーの訪問済みURLをリセット
            self.researcher.reset_visited()
            self.analyst.reset_statistics()

            result = self.hunt(
                desire=desire,
                max_products=max_products_per_desire,
                min_relevance_score=min_relevance_score,
            )
            results.append(result)

        # 全体の統計
        total_products = sum(len(r.products) for r in results)
        total_errors = sum(len(r.errors) for r in results)
        logger.info(
            f"=== バッチ処理完了 ===\n"
            f"欲求: {len(desires)}件\n"
            f"製品: {total_products}件\n"
            f"エラー: {total_errors}件"
        )

        return results

    def quick_search(
        self,
        desire: str,
        num_results: int = 5,
    ) -> list[Product]:
        """
        クイック検索（保存なし）

        素早く結果を得たい場合に使用。
        Google Sheetsへの保存は行わない。

        Args:
            desire: ユーザーの欲求
            num_results: 取得する結果数

        Returns:
            製品のリスト
        """
        result = self.hunt(
            desire=desire,
            max_products=num_results,
            min_relevance_score=3,  # 低めの閾値
            save_to_sheets=False,
        )
        return result.products

    def get_top_products(
        self,
        desire: str,
        top_n: int = 3,
    ) -> list[Product]:
        """
        トップN製品を取得

        最も適合度の高い製品を素早く取得。

        Args:
            desire: ユーザーの欲求
            top_n: 取得する件数

        Returns:
            トップN製品のリスト
        """
        products = self.quick_search(desire, num_results=top_n * 3)
        return self.analyst.rank_products(products, top_n)


def create_director(
    enable_sheets: bool = True,
) -> DirectorAgent:
    """
    DirectorAgentのファクトリ関数

    Args:
        enable_sheets: Google Sheets連携を有効にするか

    Returns:
        設定済みのDirectorAgent
    """
    repository = None

    if enable_sheets:
        try:
            repository = GSheetsProductRepository()
            logger.info("Google Sheets リポジトリを初期化しました")
        except Exception as e:
            logger.warning(f"Google Sheets初期化エラー: {e}")
            logger.info("Google Sheets連携は無効です")

    return DirectorAgent(repository=repository)
