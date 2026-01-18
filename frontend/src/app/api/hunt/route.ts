import { NextRequest, NextResponse } from "next/server";
import { analyzeDesire, extractProduct, Product } from "@/lib/gemini";
import { search, SearchResult } from "@/lib/serper";
import { scrape } from "@/lib/firecrawl";

export const maxDuration = 60; // Vercel Pro: 最大60秒

interface HuntResult {
  desire: string;
  products: Product[];
  totalSearched: number;
  totalScraped: number;
  errors: string[];
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { desire } = body;

    if (!desire || typeof desire !== "string") {
      return NextResponse.json(
        { error: "欲求を入力してください" },
        { status: 400 }
      );
    }

    const result: HuntResult = {
      desire,
      products: [],
      totalSearched: 0,
      totalScraped: 0,
      errors: [],
    };

    // Step 1: 欲求を分析
    console.log("Step 1: 欲求を分析中...");
    const analysis = await analyzeDesire(desire);
    console.log(`翻訳クエリ: ${analysis.translatedQueries.length}件`);

    // Step 2: 各言語で並列検索（最大2言語、各3件に制限）
    console.log("Step 2: 検索中...");
    const limitedQueries = analysis.translatedQueries.slice(0, 2);

    const searchPromises = limitedQueries.map(async (query) => {
      try {
        const results = await search(query.query, query.language, 3);
        console.log(`検索完了 (${query.language}): ${results.length}件`);
        return results;
      } catch (error) {
        console.error(`検索エラー (${query.language}):`, error);
        result.errors.push(`検索エラー: ${query.language}`);
        return [];
      }
    });

    const searchResults = await Promise.all(searchPromises);
    const allSearchResults: SearchResult[] = searchResults.flat();
    result.totalSearched = allSearchResults.length;

    // 重複URLを除去
    const uniqueUrls = [...new Set(allSearchResults.map((r) => r.link))];
    const limitedUrls = uniqueUrls.slice(0, 5); // 最大5件に制限（タイムアウト対策）

    // Step 3: スクレイピング & 製品抽出（並列処理）
    console.log("Step 3: スクレイピング & 製品抽出中...");

    const scrapePromises = limitedUrls.map(async (url) => {
      try {
        console.log(`スクレイピング: ${url}`);
        const content = await scrape(url);
        if (content && content.length > 100) {
          const product = await extractProduct(content, desire);
          return product;
        }
        return null;
      } catch (error) {
        console.error(`スクレイピングエラー (${url}):`, error);
        return null;
      }
    });

    const products = await Promise.all(scrapePromises);
    result.totalScraped = limitedUrls.length;

    // 有効な製品をフィルタリング
    for (const product of products) {
      if (product && product.relevanceScore >= 5) {
        // 重複チェック
        const isDuplicate = result.products.some(
          (p) =>
            p.name.toLowerCase() === product.name.toLowerCase() ||
            (p.officialUrl && p.officialUrl === product.officialUrl)
        );
        if (!isDuplicate) {
          result.products.push(product);
          console.log(`製品抽出成功: ${product.name}`);
        }
      }
    }

    // スコア順にソート
    result.products.sort((a, b) => b.relevanceScore - a.relevanceScore);

    // 上位5件に制限
    result.products = result.products.slice(0, 5);

    console.log(`完了: ${result.products.length}件の製品を発見`);

    return NextResponse.json(result);
  } catch (error) {
    console.error("Hunt API error:", error);
    return NextResponse.json(
      { error: "内部エラーが発生しました" },
      { status: 500 }
    );
  }
}
