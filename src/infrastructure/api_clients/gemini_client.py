"""
Gemini APIクライアント

LLMによる翻訳・製品情報抽出を担当。
JSON出力を使用して構造化データを取得。
"""

import json
import logging
from typing import Optional

from google import genai
from google.genai import types
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

from src.core.config import settings
from src.core.interfaces import LLMClient
from src.domain.models import (
    Product,
    PriceInfo,
    DesireAnalysis,
    TranslatedQuery,
)

logger = logging.getLogger(__name__)


class GeminiClient(LLMClient):
    """
    Google Gemini APIを使用したLLMクライアント

    JSON出力を活用して、構造化された応答を取得。
    Tenacityによるリトライ機能付き。
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model or settings.gemini_model
        self.client = genai.Client(api_key=self.api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            f"Gemini API リトライ: {retry_state.attempt_number}回目"
        ),
    )
    def translate(self, text: str, target_language: str) -> str:
        """
        テキストを指定言語に翻訳し、検索クエリを生成

        Args:
            text: 翻訳対象テキスト（欲求）
            target_language: 翻訳先言語コード（en, zh, de等）

        Returns:
            翻訳された検索クエリ
        """
        prompt = f"""
以下の「欲求」を{target_language}言語に翻訳し、製品検索に最適なクエリを生成してください。

欲求: {text}

翻訳の際は以下を考慮してください：
- 製品検索に適した具体的なキーワードを含める
- 文化圏に即した表現を使用
- ブランド名や製品カテゴリを明確にする

以下のJSON形式で回答してください：
{{
    "translated_text": "翻訳されたテキスト",
    "search_query": "検索クエリ",
    "search_intent": "検索意図の説明"
}}
"""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        try:
            result = json.loads(response.text)
            return result.get("search_query", text)
        except json.JSONDecodeError:
            logger.warning("JSON解析失敗、元のテキストを返します")
            return text

    def analyze_desire(self, desire: str) -> DesireAnalysis:
        """
        欲求を分析し、多言語検索クエリを生成

        Args:
            desire: ユーザーの欲求テキスト

        Returns:
            DesireAnalysis: 分析結果と翻訳クエリ
        """
        prompt = f"""
以下の「欲求」を分析し、製品探索に最適な検索戦略を立ててください。

欲求: {desire}

以下のJSON形式で回答してください：
{{
    "original_desire": "元の欲求",
    "refined_desire": "精製された欲求",
    "keywords": ["キーワード1", "キーワード2"],
    "category": "製品カテゴリ",
    "translated_queries": [
        {{"original": "元の欲求", "language": "en", "query": "英語クエリ", "search_intent": "意図"}},
        {{"original": "元の欲求", "language": "ja", "query": "日本語クエリ", "search_intent": "意図"}}
    ]
}}
"""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        try:
            result = json.loads(response.text)
            queries = [
                TranslatedQuery(**q) for q in result.get("translated_queries", [])
            ]
            return DesireAnalysis(
                original_desire=result.get("original_desire", desire),
                refined_desire=result.get("refined_desire", ""),
                keywords=result.get("keywords", []),
                category=result.get("category", ""),
                translated_queries=queries,
            )
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"欲求分析の解析失敗: {e}")
            return DesireAnalysis(original_desire=desire)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            f"製品抽出リトライ: {retry_state.attempt_number}回目"
        ),
    )
    def extract_product(self, content: str, desire: str) -> Optional[Product]:
        """
        Markdownコンテンツから製品情報を抽出

        Args:
            content: 解析対象のMarkdownコンテンツ
            desire: ユーザーの欲求（評価の基準として使用）

        Returns:
            抽出された製品情報、または None
        """
        if len(content) < 100:
            logger.debug("コンテンツが短すぎるためスキップ")
            return None

        max_content_length = 8000
        truncated_content = content[:max_content_length]

        prompt = f"""
以下のWebページコンテンツから、製品情報を抽出してください。

## ユーザーの欲求
{desire}

## Webページコンテンツ
{truncated_content}

## 指示
1. 製品情報が見つかった場合、詳細を抽出してください
2. 製品の欲求への適合度を0-10で評価してください
3. 価格情報があれば、通貨と金額を抽出してください
4. 公式サイト、Amazon、楽天、InstagramのURLがあれば抽出してください
5. 製品情報が見つからない場合は、found=false を返してください

以下のJSON形式で回答してください：
{{
    "found": true,
    "name": "製品名",
    "brand": "ブランド名",
    "description": "製品説明",
    "price": {{
        "amount": 1000,
        "currency": "JPY",
        "formatted": "¥1,000"
    }},
    "official_url": "https://example.com",
    "amazon_url": null,
    "rakuten_url": null,
    "instagram_url": null,
    "relevance_score": 8,
    "reasoning": "評価理由"
}}

製品が見つからない場合：
{{
    "found": false
}}
"""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        try:
            result = json.loads(response.text)

            if not result.get("found", False):
                return None

            price_data = result.get("price")
            price_info = None
            if price_data:
                price_info = PriceInfo(
                    amount=price_data.get("amount"),
                    currency=price_data.get("currency", "USD"),
                    formatted=price_data.get("formatted", ""),
                )

            product = Product(
                name=result.get("name", ""),
                brand=result.get("brand", ""),
                description=result.get("description", ""),
                price=price_info,
                official_url=result.get("official_url"),
                amazon_url=result.get("amazon_url"),
                rakuten_url=result.get("rakuten_url"),
                instagram_url=result.get("instagram_url"),
                relevance_score=result.get("relevance_score", 0),
                reasoning=result.get("reasoning", ""),
                desire=desire,
            )

            return product

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"製品抽出の解析失敗: {e}")
            return None

    def generate_search_queries(
        self, desire: str, languages: list[str]
    ) -> list[TranslatedQuery]:
        """
        欲求から複数言語の検索クエリを生成

        Args:
            desire: ユーザーの欲求
            languages: 対象言語コードのリスト

        Returns:
            TranslatedQuery のリスト
        """
        queries = []
        for lang in languages:
            try:
                query = self.translate(desire, lang)
                queries.append(
                    TranslatedQuery(
                        original=desire,
                        language=lang,
                        query=query,
                        search_intent=f"Product search for: {desire}",
                    )
                )
            except Exception as e:
                logger.error(f"翻訳エラー ({lang}): {e}")
                queries.append(
                    TranslatedQuery(
                        original=desire,
                        language=lang,
                        query=desire,
                        search_intent="",
                    )
                )

        return queries
