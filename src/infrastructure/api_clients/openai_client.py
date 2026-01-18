"""
OpenAI APIクライアント

LLMによる翻訳・製品情報抽出を担当。
Structured Outputsを使用して型安全な出力を保証。
"""

import logging
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel
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
    DesireAnalysis,
    TranslatedQuery,
    ExtractionResult,
)

logger = logging.getLogger(__name__)


class TranslationOutput(BaseModel):
    """翻訳出力スキーマ"""

    translated_text: str
    search_query: str
    search_intent: str


class OpenAIClient(LLMClient):
    """
    OpenAI APIを使用したLLMクライアント

    Structured Outputsを活用して、型安全な応答を取得。
    Tenacityによるリトライ機能付き。
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self.client = OpenAI(api_key=self.api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            f"OpenAI API リトライ: {retry_state.attempt_number}回目"
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
"""

        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "あなたは多言語対応の製品検索エキスパートです。",
                },
                {"role": "user", "content": prompt},
            ],
            response_format=TranslationOutput,
        )

        result = completion.choices[0].message.parsed
        return result.search_query if result else text

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

以下の情報を抽出してください：
1. 欲求の本質（何を求めているか）
2. 関連するキーワード
3. 製品カテゴリ
4. 各言語（en, zh, de, ja, fr）での最適な検索クエリ
"""

        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "あなたは消費者心理と製品マーケティングの専門家です。",
                },
                {"role": "user", "content": prompt},
            ],
            response_format=DesireAnalysis,
        )

        return completion.choices[0].message.parsed or DesireAnalysis(
            original_desire=desire
        )

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
        # コンテンツが短すぎる場合はスキップ
        if len(content) < 100:
            logger.debug("コンテンツが短すぎるためスキップ")
            return None

        # コンテンツを適切な長さに切り詰め（トークン節約）
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
"""

        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは製品情報抽出の専門家です。"
                        "Webページから正確に製品情報を抽出し、構造化データとして出力します。"
                        "情報が不明確な場合は推測せず、空欄にしてください。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format=ExtractionResult,
        )

        result = completion.choices[0].message.parsed
        if result and result.found and result.product:
            # 欲求情報を付加
            result.product.desire = desire
            return result.product

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
                # フォールバック：元のテキストを使用
                queries.append(
                    TranslatedQuery(
                        original=desire,
                        language=lang,
                        query=desire,
                        search_intent="",
                    )
                )

        return queries
