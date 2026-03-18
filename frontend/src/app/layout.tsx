import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Desire Hunter - 欲求から製品を発見",
  description: "あなたの欲求を入力すると、世界中から最適な製品を見つけ出します",
  openGraph: {
    title: "Desire Hunter - 欲求から製品を発見",
    description: "あなたの欲求を入力すると、世界中から最適な製品を見つけ出します",
    type: "website",
    url: "https://desire-hunter.vercel.app",
    images: [
      {
        url: "https://desire-hunter.vercel.app/og-image.png",
        width: 1200,
        height: 630,
        alt: "Desire Hunter",
      },
    ],
    locale: "ja_JP",
  },
  twitter: {
    card: "summary_large_image",
    title: "Desire Hunter - 欲求から製品を発見",
    description: "あなたの欲求を入力すると、世界中から最適な製品を見つけ出します",
    images: ["https://desire-hunter.vercel.app/og-image.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
