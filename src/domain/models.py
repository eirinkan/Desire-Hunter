"""
ドメインモデル定義

LLMの出力スキーマおよびシステム内でのデータ交換形式。
Pydanticを使用して型安全性を保証。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """検索結果モデル"""

    title: str = Field(..., description="検索結果のタイトル")
    url: str = Field(..., description="検索結果のURL")
    snippet: str = Field(default="", description="検索結果のスニペット")
    position: int = Field(default=0, description="検索結果の順位")


class TranslatedQuery(BaseModel):
    """翻訳されたクエリモデル"""

    original: str = Field(..., description="元の欲求テキスト")
    language: str = Field(..., description="言語コード")
    query: str = Field(..., description="翻訳された検索クエリ")
    search_intent: str = Field(default="", description="文化圏に即した検索インテント")


class PriceInfo(BaseModel):
    """価格情報モデル"""

    amount: Optional[float] = Field(None, description="価格（数値）")
    currency: str = Field(default="USD", description="通貨コード")
    formatted: str = Field(default="", description="フォーマット済み価格文字列")


class Product(BaseModel):
    """
    製品情報モデル

    LLMのStructured Outputsで直接使用可能。
    Google Sheetsへの書き込み時にも使用。
    """

    # 基本情報
    name: str = Field(..., description="製品名")
    brand: str = Field(default="", description="ブランド名")
    description: str = Field(default="", description="製品説明")

    # 価格情報
    price: Optional[PriceInfo] = Field(None, description="価格情報")

    # URL情報
    official_url: Optional[str] = Field(None, description="公式サイトURL")
    amazon_url: Optional[str] = Field(None, description="AmazonのURL")
    rakuten_url: Optional[str] = Field(None, description="楽天のURL")
    instagram_url: Optional[str] = Field(None, description="InstagramのURL")

    # 評価情報
    relevance_score: int = Field(
        default=0, ge=0, le=10, description="欲求適合度（0-10）"
    )
    reasoning: str = Field(default="", description="評価理由")

    # メタデータ
    source_language: str = Field(default="en", description="検索言語コード")
    source_url: str = Field(default="", description="情報取得元URL")
    desire: str = Field(default="", description="関連する欲求")
    extracted_at: datetime = Field(
        default_factory=datetime.now, description="抽出日時"
    )

    def to_row(self) -> list[str]:
        """Google Sheets用の行データに変換"""
        price_str = self.price.formatted if self.price else ""
        return [
            self.name,
            self.brand,
            self.description[:200],  # 説明は200文字まで
            price_str,
            self.official_url or "",
            self.amazon_url or "",
            self.rakuten_url or "",
            self.instagram_url or "",
            str(self.relevance_score),
            self.reasoning[:100],  # 理由は100文字まで
            self.source_language,
            self.source_url,
            self.desire,
            self.extracted_at.isoformat(),
        ]

    @classmethod
    def get_header_row(cls) -> list[str]:
        """Google Sheets用のヘッダー行を取得"""
        return [
            "製品名",
            "ブランド",
            "説明",
            "価格",
            "公式URL",
            "Amazon URL",
            "楽天URL",
            "Instagram URL",
            "適合度",
            "評価理由",
            "検索言語",
            "情報元URL",
            "欲求",
            "抽出日時",
        ]


class DesireAnalysis(BaseModel):
    """欲求分析結果モデル"""

    original_desire: str = Field(..., description="元の欲求テキスト")
    refined_desire: str = Field(default="", description="精製された欲求")
    keywords: list[str] = Field(
        default_factory=list, description="抽出されたキーワード"
    )
    category: str = Field(default="", description="製品カテゴリ")
    translated_queries: list[TranslatedQuery] = Field(
        default_factory=list, description="各言語への翻訳クエリ"
    )


class ExtractionResult(BaseModel):
    """LLMによる製品抽出結果"""

    found: bool = Field(..., description="製品情報が見つかったかどうか")
    product: Optional[Product] = Field(None, description="抽出された製品情報")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="抽出の確信度"
    )
    error_message: str = Field(default="", description="エラーメッセージ（あれば）")
