"""
インターフェース定義

クリーンアーキテクチャにおける抽象インターフェース。
アプリケーション層はこれらのインターフェースに依存し、
具体的な実装（インフラ層）を知らない。
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models import Product, SearchResult


class SearchClient(ABC):
    """検索クライアントのインターフェース"""

    @abstractmethod
    def search(self, query: str, num_results: int = 10) -> list["SearchResult"]:
        """
        クエリで検索を実行し、結果を返す

        Args:
            query: 検索クエリ
            num_results: 取得する結果数

        Returns:
            SearchResult のリスト
        """
        pass


class WebScraperClient(ABC):
    """Webスクレイピングクライアントのインターフェース"""

    @abstractmethod
    def scrape(self, url: str) -> str:
        """
        URLからコンテンツを取得してMarkdown形式で返す

        Args:
            url: スクレイピング対象URL

        Returns:
            Markdown形式のコンテンツ
        """
        pass

    @abstractmethod
    def map_site(self, url: str) -> list[str]:
        """
        サイトのURLマップを取得

        Args:
            url: 対象サイトのURL

        Returns:
            サイト内のURLリスト
        """
        pass


class LLMClient(ABC):
    """LLMクライアントのインターフェース"""

    @abstractmethod
    def translate(self, text: str, target_language: str) -> str:
        """
        テキストを指定言語に翻訳

        Args:
            text: 翻訳対象テキスト
            target_language: 翻訳先言語コード

        Returns:
            翻訳されたテキスト
        """
        pass

    @abstractmethod
    def extract_product(self, content: str, desire: str) -> "Product | None":
        """
        コンテンツから製品情報を抽出

        Args:
            content: 解析対象のMarkdownコンテンツ
            desire: ユーザーの欲求

        Returns:
            抽出された製品情報、または None
        """
        pass


class ProductRepository(ABC):
    """製品リポジトリのインターフェース"""

    @abstractmethod
    def save(self, product: "Product") -> None:
        """単一の製品を保存"""
        pass

    @abstractmethod
    def save_batch(self, products: list["Product"]) -> None:
        """複数の製品を一括保存"""
        pass

    @abstractmethod
    def find_by_url(self, url: str) -> "Product | None":
        """URLで製品を検索"""
        pass

    @abstractmethod
    def get_all(self) -> list["Product"]:
        """全製品を取得"""
        pass
