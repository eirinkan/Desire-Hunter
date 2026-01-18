"""
Google Sheets リポジトリ

製品データの永続化を担当。
バッチ更新による効率化とレート制限対応。
"""

import logging
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

from src.core.config import settings
from src.core.interfaces import ProductRepository
from src.domain.models import Product, PriceInfo

logger = logging.getLogger(__name__)

# Google Sheets API のスコープ
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GSheetsProductRepository(ProductRepository):
    """
    Google Sheetsを使用した製品リポジトリ

    特徴:
    - バッチ更新による効率化
    - 重複チェック機能
    - 自動ヘッダー作成
    """

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        spreadsheet_id: Optional[str] = None,
        worksheet_name: Optional[str] = None,
    ):
        self.credentials_path = credentials_path or settings.google_credentials_path
        self.spreadsheet_id = spreadsheet_id or settings.spreadsheet_id
        self.worksheet_name = worksheet_name or settings.worksheet_name

        self._client: Optional[gspread.Client] = None
        self._worksheet: Optional[gspread.Worksheet] = None
        self._write_queue: list[Product] = []

    def _get_client(self) -> gspread.Client:
        """gspreadクライアントを取得（遅延初期化）"""
        if self._client is None:
            try:
                credentials = Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=SCOPES,
                )
                self._client = gspread.authorize(credentials)
                logger.info("Google Sheets クライアント初期化完了")
            except Exception as e:
                logger.error(f"Google Sheets 認証エラー: {e}")
                raise

        return self._client

    def _get_worksheet(self) -> gspread.Worksheet:
        """ワークシートを取得（遅延初期化）"""
        if self._worksheet is None:
            try:
                client = self._get_client()
                spreadsheet = client.open_by_key(self.spreadsheet_id)

                # ワークシートを取得、なければ作成
                try:
                    self._worksheet = spreadsheet.worksheet(self.worksheet_name)
                except gspread.WorksheetNotFound:
                    self._worksheet = spreadsheet.add_worksheet(
                        title=self.worksheet_name,
                        rows=1000,
                        cols=20,
                    )
                    # ヘッダーを追加
                    self._worksheet.append_row(Product.get_header_row())
                    logger.info(f"ワークシート作成: {self.worksheet_name}")

                logger.info(f"ワークシート取得完了: {self.worksheet_name}")
            except Exception as e:
                logger.error(f"ワークシート取得エラー: {e}")
                raise

        return self._worksheet

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((gspread.exceptions.APIError,)),
        before_sleep=lambda retry_state: logger.warning(
            f"Google Sheets API リトライ: {retry_state.attempt_number}回目"
        ),
    )
    def save(self, product: Product) -> None:
        """
        単一の製品を保存

        注意: 単一保存は非効率。可能な限り save_batch を使用すること。

        Args:
            product: 保存する製品
        """
        worksheet = self._get_worksheet()
        row = product.to_row()

        try:
            worksheet.append_row(row)
            logger.info(f"製品保存完了: {product.name}")
        except Exception as e:
            logger.error(f"製品保存エラー: {product.name} - {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((gspread.exceptions.APIError,)),
        before_sleep=lambda retry_state: logger.warning(
            f"Google Sheets バッチ保存リトライ: {retry_state.attempt_number}回目"
        ),
    )
    def save_batch(self, products: list[Product]) -> None:
        """
        複数の製品を一括保存（推奨）

        バッチ更新により、API呼び出しを最小化。

        Args:
            products: 保存する製品のリスト
        """
        if not products:
            return

        worksheet = self._get_worksheet()
        rows = [p.to_row() for p in products]

        try:
            # append_rows で一括追加（update_cell は絶対に使わない）
            worksheet.append_rows(rows)
            logger.info(f"バッチ保存完了: {len(products)}件")
        except Exception as e:
            logger.error(f"バッチ保存エラー: {e}")
            raise

    def queue_product(self, product: Product) -> None:
        """
        製品を書き込みキューに追加

        flush() を呼ぶまで実際の書き込みは行わない。

        Args:
            product: キューに追加する製品
        """
        self._write_queue.append(product)
        queue_len = len(self._write_queue)
        logger.debug(f"キュー追加: {product.name} (キュー内: {queue_len}件)")

    def flush(self) -> int:
        """
        キューに溜まった製品を一括保存

        Returns:
            保存した製品数
        """
        if not self._write_queue:
            return 0

        count = len(self._write_queue)
        self.save_batch(self._write_queue)
        self._write_queue = []
        return count

    def find_by_url(self, url: str) -> Optional[Product]:
        """
        URLで製品を検索

        Args:
            url: 検索するURL

        Returns:
            見つかった製品、または None
        """
        worksheet = self._get_worksheet()

        try:
            # 全データを取得
            records = worksheet.get_all_records()

            for record in records:
                # 公式URL、Amazon、楽天のいずれかにマッチ
                if (
                    record.get("公式URL") == url
                    or record.get("Amazon URL") == url
                    or record.get("楽天URL") == url
                ):
                    return self._record_to_product(record)

            return None

        except Exception as e:
            logger.error(f"URL検索エラー: {e}")
            return None

    def get_all(self) -> list[Product]:
        """
        全製品を取得

        Returns:
            製品のリスト
        """
        worksheet = self._get_worksheet()

        try:
            records = worksheet.get_all_records()
            products = []

            for record in records:
                product = self._record_to_product(record)
                if product:
                    products.append(product)

            logger.info(f"全製品取得完了: {len(products)}件")
            return products

        except Exception as e:
            logger.error(f"全製品取得エラー: {e}")
            return []

    def _record_to_product(self, record: dict) -> Optional[Product]:
        """
        Google Sheetsのレコードを Product に変換

        Args:
            record: シートのレコード（辞書）

        Returns:
            Product オブジェクト、または None
        """
        try:
            # 価格情報の解析
            price_str = record.get("価格", "")
            price_info = None
            if price_str:
                price_info = PriceInfo(
                    formatted=price_str,
                    currency="",
                    amount=None,
                )

            return Product(
                name=record.get("製品名", ""),
                brand=record.get("ブランド", ""),
                description=record.get("説明", ""),
                price=price_info,
                official_url=record.get("公式URL") or None,
                amazon_url=record.get("Amazon URL") or None,
                rakuten_url=record.get("楽天URL") or None,
                instagram_url=record.get("Instagram URL") or None,
                relevance_score=int(record.get("適合度", 0) or 0),
                reasoning=record.get("評価理由", ""),
                source_language=record.get("検索言語", ""),
                source_url=record.get("情報元URL", ""),
                desire=record.get("欲求", ""),
            )

        except Exception as e:
            logger.warning(f"レコード変換エラー: {e}")
            return None

    def exists_by_name(self, name: str) -> bool:
        """
        製品名で重複チェック

        Args:
            name: チェックする製品名

        Returns:
            存在すればTrue
        """
        worksheet = self._get_worksheet()

        try:
            records = worksheet.get_all_records()
            return any(record.get("製品名") == name for record in records)
        except Exception as e:
            logger.error(f"重複チェックエラー: {e}")
            return False

    def ensure_header(self) -> None:
        """ヘッダー行が存在することを確認し、なければ追加"""
        worksheet = self._get_worksheet()

        try:
            first_row = worksheet.row_values(1)
            expected_header = Product.get_header_row()

            if first_row != expected_header:
                # 空の場合はヘッダーを追加
                if not first_row or all(not cell for cell in first_row):
                    worksheet.insert_row(expected_header, 1)
                    logger.info("ヘッダー行を追加しました")

        except Exception as e:
            logger.warning(f"ヘッダー確認エラー: {e}")
