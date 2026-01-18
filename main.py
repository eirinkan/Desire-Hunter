"""
Desire-Hunter V2.0

ユーザーの「欲求」を入力とし、全世界のWeb空間から
最適な製品を自律的に探索・評価するシステム。

使用例:
    # 基本的な使用
    python main.py "快適な在宅勤務環境を作りたい"

    # 複数の欲求を処理
    python main.py --batch desires.txt

    # クイック検索（保存なし）
    python main.py --quick "高品質なワイヤレスイヤホンが欲しい"
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# .env ファイルを読み込み（インポート前に実行する必要がある）
load_dotenv()

from src.agents.director import create_director, DirectorAgent  # noqa: E402
from src.core.config import settings  # noqa: E402


def setup_logging(verbose: bool = False) -> None:
    """ロギングの設定"""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 外部ライブラリのログレベルを抑制
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def validate_settings() -> bool:
    """設定の検証"""
    errors = []

    if not settings.openai_api_key:
        errors.append("OPENAI_API_KEY が設定されていません")

    if not settings.serper_api_key:
        errors.append("SERPER_API_KEY が設定されていません")

    if not settings.firecrawl_api_key:
        errors.append("FIRECRAWL_API_KEY が設定されていません")

    if errors:
        print("設定エラー:")
        for error in errors:
            print(f"  - {error}")
        print("\n.env ファイルに必要なAPIキーを設定してください。")
        print("詳細は .env.example を参照してください。")
        return False

    return True


def hunt_single(director: DirectorAgent, desire: str, quick: bool = False) -> None:
    """単一の欲求を処理"""
    print(f"\n🎯 欲求: {desire}")
    print("-" * 50)

    if quick:
        products = director.quick_search(desire, num_results=5)
    else:
        result = director.hunt(desire)
        products = result.products

        if result.errors:
            print("\n⚠️ エラー:")
            for error in result.errors:
                print(f"  - {error}")

    if products:
        print(f"\n✅ 発見した製品: {len(products)}件")
        print("=" * 50)

        for i, product in enumerate(products, 1):
            print(f"\n【{i}】{product.name}")
            if product.brand:
                print(f"    ブランド: {product.brand}")
            if product.price:
                print(f"    価格: {product.price.formatted}")
            print(f"    適合度: {product.relevance_score}/10")
            print(f"    理由: {product.reasoning[:80]}...")
            if product.official_url:
                print(f"    URL: {product.official_url}")

    else:
        print("\n❌ 製品が見つかりませんでした")


def hunt_batch(director: DirectorAgent, file_path: str) -> None:
    """バッチ処理"""
    path = Path(file_path)

    if not path.exists():
        print(f"エラー: ファイルが見つかりません: {file_path}")
        return

    desires = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    if not desires:
        print("エラー: 処理する欲求がありません")
        return

    print(f"\n📋 バッチ処理: {len(desires)}件の欲求")
    print("=" * 50)

    results = director.hunt_batch(desires)

    # サマリー表示
    print("\n" + "=" * 50)
    print("📊 バッチ処理結果")
    print("=" * 50)

    total_products = 0
    for i, result in enumerate(results, 1):
        product_count = len(result.products)
        total_products += product_count
        status = "✅" if product_count > 0 else "❌"
        print(f"{status} {i}. {result.desire[:30]}... -> {product_count}件")

    print(f"\n合計: {total_products}件の製品を発見")


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="Desire-Hunter V2.0 - 欲求から製品を探索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s "快適な在宅勤務環境を作りたい"
  %(prog)s --quick "高品質なワイヤレスイヤホン"
  %(prog)s --batch desires.txt
  %(prog)s --no-sheets "テスト検索"
        """,
    )

    parser.add_argument(
        "desire",
        nargs="?",
        help="探索したい欲求",
    )

    parser.add_argument(
        "--batch",
        metavar="FILE",
        help="欲求リストファイルでバッチ処理",
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="クイック検索モード（保存なし）",
    )

    parser.add_argument(
        "--no-sheets",
        action="store_true",
        help="Google Sheetsへの保存を無効化",
    )

    parser.add_argument(
        "--max-products",
        type=int,
        default=10,
        help="取得する最大製品数（デフォルト: 10）",
    )

    parser.add_argument(
        "--min-score",
        type=int,
        default=5,
        help="最小適合度スコア（0-10、デフォルト: 5）",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="詳細ログを表示",
    )

    args = parser.parse_args()

    # ロギング設定
    setup_logging(args.verbose)

    # 引数チェック
    if not args.desire and not args.batch:
        parser.print_help()
        print("\nエラー: 欲求または --batch オプションを指定してください")
        sys.exit(1)

    # 設定検証
    if not validate_settings():
        sys.exit(1)

    print("=" * 50)
    print("🔍 Desire-Hunter V2.0")
    print("=" * 50)

    # Director作成
    enable_sheets = not args.no_sheets and not args.quick
    director = create_director(enable_sheets=enable_sheets)

    try:
        if args.batch:
            hunt_batch(director, args.batch)
        else:
            hunt_single(director, args.desire, args.quick)

    except KeyboardInterrupt:
        print("\n\n⏹️ 処理を中断しました")
        sys.exit(0)
    except Exception as e:
        logging.error(f"予期しないエラー: {e}")
        if args.verbose:
            raise
        sys.exit(1)

    print("\n✨ 完了")


if __name__ == "__main__":
    main()
