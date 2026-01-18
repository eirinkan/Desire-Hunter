"use client";

import { useState } from "react";

// 製品データの型定義
interface Product {
  name: string;
  brand: string;
  description: string;
  price?: {
    amount: number;
    currency: string;
    formatted: string;
  };
  officialUrl?: string;
  amazonUrl?: string;
  rakutenUrl?: string;
  relevanceScore: number;
  reasoning: string;
}

interface HuntResult {
  desire: string;
  products: Product[];
  totalSearched: number;
  totalScraped: number;
  errors: string[];
}

export default function Home() {
  const [desire, setDesire] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<HuntResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!desire.trim()) return;

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch("/api/hunt", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ desire }),
      });

      if (!response.ok) {
        // レスポンスがJSONかどうか確認
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
          const errorData = await response.json();
          throw new Error(errorData.error || "エラーが発生しました");
        } else {
          // プレーンテキストのエラー
          const errorText = await response.text();
          throw new Error(errorText || "サーバーエラーが発生しました");
        }
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      if (err instanceof SyntaxError) {
        // JSONパースエラー
        setError("サーバーからの応答を解析できませんでした。しばらく待ってから再試行してください。");
      } else {
        setError(err instanceof Error ? err.message : "予期しないエラーが発生しました");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-50 to-zinc-100 dark:from-zinc-900 dark:to-black">
      {/* ヘッダー */}
      <header className="border-b border-zinc-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">
            🎯 Desire Hunter
          </h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            欲求から最適な製品を発見
          </p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {/* 検索フォーム */}
        <form onSubmit={handleSubmit} className="mb-8">
          <div className="bg-white dark:bg-zinc-800 rounded-2xl shadow-lg p-6">
            <label
              htmlFor="desire"
              className="block text-lg font-semibold text-zinc-900 dark:text-white mb-2"
            >
              あなたの欲求を教えてください
            </label>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
              例: 「集中力を高めたい」「肩こりを解消したい」「在宅ワークを快適にしたい」
            </p>
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                type="text"
                id="desire"
                value={desire}
                onChange={(e) => setDesire(e.target.value)}
                placeholder="欲求を入力..."
                className="flex-1 px-4 py-3 rounded-xl border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading || !desire.trim()}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-400 text-white font-semibold rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                {isLoading ? "検索中..." : "製品を探す"}
              </button>
            </div>
          </div>
        </form>

        {/* ローディング状態 */}
        {isLoading && (
          <div className="bg-white dark:bg-zinc-800 rounded-2xl shadow-lg p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-zinc-600 dark:text-zinc-400">
              世界中から製品を探しています...
            </p>
            <p className="text-sm text-zinc-500 dark:text-zinc-500 mt-2">
              多言語検索・スクレイピング中（最大60秒）
            </p>
          </div>
        )}

        {/* エラー表示 */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-6 mb-8">
            <p className="text-red-700 dark:text-red-400 font-medium">
              ⚠️ {error}
            </p>
          </div>
        )}

        {/* 検索結果 */}
        {result && (
          <div>
            {/* 統計情報 */}
            <div className="bg-white dark:bg-zinc-800 rounded-2xl shadow-lg p-6 mb-6">
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-white mb-3">
                検索結果
              </h2>
              <div className="flex flex-wrap gap-4 text-sm">
                <span className="px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full">
                  検索: {result.totalSearched}件
                </span>
                <span className="px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full">
                  解析: {result.totalScraped}件
                </span>
                <span className="px-3 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full">
                  発見: {result.products.length}製品
                </span>
              </div>
              {result.errors.length > 0 && (
                <p className="text-sm text-orange-600 dark:text-orange-400 mt-3">
                  一部のソースでエラー: {result.errors.join(", ")}
                </p>
              )}
            </div>

            {/* 製品カード */}
            {result.products.length > 0 ? (
              <div className="space-y-4">
                {result.products.map((product, index) => (
                  <div
                    key={index}
                    className="bg-white dark:bg-zinc-800 rounded-2xl shadow-lg p-6 hover:shadow-xl transition-shadow"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-2xl font-bold text-zinc-300 dark:text-zinc-600">
                            #{index + 1}
                          </span>
                          <h3 className="text-xl font-bold text-zinc-900 dark:text-white">
                            {product.name}
                          </h3>
                        </div>
                        {product.brand && (
                          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-2">
                            ブランド: {product.brand}
                          </p>
                        )}
                        <p className="text-zinc-700 dark:text-zinc-300 mb-3">
                          {product.description}
                        </p>

                        {/* 価格 */}
                        {product.price && (
                          <p className="text-lg font-bold text-blue-600 dark:text-blue-400 mb-3">
                            {product.price.formatted}
                          </p>
                        )}

                        {/* 適合度スコア */}
                        <div className="mb-3">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-zinc-600 dark:text-zinc-400">
                              適合度:
                            </span>
                            <div className="flex-1 max-w-xs bg-zinc-200 dark:bg-zinc-700 rounded-full h-2">
                              <div
                                className="bg-gradient-to-r from-blue-500 to-blue-600 h-2 rounded-full"
                                style={{
                                  width: `${product.relevanceScore * 10}%`,
                                }}
                              ></div>
                            </div>
                            <span className="text-sm font-semibold text-blue-600 dark:text-blue-400">
                              {product.relevanceScore}/10
                            </span>
                          </div>
                          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                            {product.reasoning}
                          </p>
                        </div>

                        {/* リンク */}
                        <div className="flex flex-wrap gap-2">
                          {product.officialUrl && (
                            <a
                              href={product.officialUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-4 py-2 bg-zinc-100 dark:bg-zinc-700 hover:bg-zinc-200 dark:hover:bg-zinc-600 text-zinc-700 dark:text-zinc-300 text-sm rounded-lg transition-colors"
                            >
                              🔗 公式サイト
                            </a>
                          )}
                          {product.amazonUrl && (
                            <a
                              href={product.amazonUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-4 py-2 bg-orange-100 dark:bg-orange-900/30 hover:bg-orange-200 dark:hover:bg-orange-900/50 text-orange-700 dark:text-orange-300 text-sm rounded-lg transition-colors"
                            >
                              🛒 Amazon
                            </a>
                          )}
                          {product.rakutenUrl && (
                            <a
                              href={product.rakutenUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-4 py-2 bg-red-100 dark:bg-red-900/30 hover:bg-red-200 dark:hover:bg-red-900/50 text-red-700 dark:text-red-300 text-sm rounded-lg transition-colors"
                            >
                              🛒 楽天
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-white dark:bg-zinc-800 rounded-2xl shadow-lg p-8 text-center">
                <p className="text-zinc-600 dark:text-zinc-400">
                  該当する製品が見つかりませんでした。
                </p>
                <p className="text-sm text-zinc-500 dark:text-zinc-500 mt-2">
                  別の表現で検索してみてください。
                </p>
              </div>
            )}
          </div>
        )}

        {/* 初期状態 */}
        {!isLoading && !result && !error && (
          <div className="bg-white dark:bg-zinc-800 rounded-2xl shadow-lg p-8 text-center">
            <p className="text-4xl mb-4">🔍</p>
            <p className="text-zinc-600 dark:text-zinc-400">
              欲求を入力して、最適な製品を発見しましょう
            </p>
            <p className="text-sm text-zinc-500 dark:text-zinc-500 mt-2">
              日本語・英語など多言語で世界中を検索します
            </p>
          </div>
        )}
      </main>

      {/* フッター */}
      <footer className="border-t border-zinc-200 dark:border-zinc-800 mt-auto">
        <div className="max-w-4xl mx-auto px-4 py-6 text-center text-sm text-zinc-500 dark:text-zinc-500">
          Desire Hunter v2.0 - Powered by Gemini AI
        </div>
      </footer>
    </div>
  );
}
