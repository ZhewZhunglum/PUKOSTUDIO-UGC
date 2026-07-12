import type { Metadata } from "next";
import { Manrope, JetBrains_Mono, Noto_Sans_SC } from "next/font/google";
import "./globals.css";

const sans = Manrope({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const sc = Noto_Sans_SC({
  variable: "--font-sc",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "UGC 红人建联系统",
  description: "AI-powered US influencer outreach system",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${sans.variable} ${mono.variable} ${sc.variable} h-full antialiased`}
      // Browser extensions (e.g. QuillBot's data-qb-installed) inject
      // attributes into <html> before React hydrates, triggering a hydration
      // mismatch warning in dev. Suppress it for this one element only.
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
