"""
設定管理モジュール

環境変数からAPIキー等の設定を読み込む。
"""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """アプリケーション設定"""

    # Gemini
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

    # Serper（Google検索API）
    serper_api_key: str = Field(default="", alias="SERPER_API_KEY")

    # Firecrawl（Webスクレイピング）
    firecrawl_api_key: str = Field(default="", alias="FIRECRAWL_API_KEY")

    # Google Sheets
    google_credentials_path: str = Field(
        default="credentials.json", alias="GOOGLE_CREDENTIALS_PATH"
    )
    spreadsheet_id: str = Field(default="", alias="SPREADSHEET_ID")
    worksheet_name: str = Field(default="Products", alias="WORKSHEET_NAME")

    # レート制限設定
    serper_rate_limit: int = Field(default=10, alias="SERPER_RATE_LIMIT")  # 10回/分
    firecrawl_rate_limit: int = Field(default=5, alias="FIRECRAWL_RATE_LIMIT")  # 5回/分

    # 探索設定
    max_products_per_desire: int = Field(default=20, alias="MAX_PRODUCTS_PER_DESIRE")
    search_languages: list[str] = Field(
        default=["en", "zh", "de", "ja", "fr"], alias="SEARCH_LANGUAGES"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """シングルトンで設定を取得"""
    return Settings()


settings = get_settings()
