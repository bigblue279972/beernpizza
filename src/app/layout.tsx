import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { getSports } from "@/lib/actions/sports";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "BeerNPizza CLV",
  description: "Betfair discipline platform — CLV tracking for serious bettors.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const sports = await getSports();
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="h-full flex bg-[var(--bg)] text-[var(--text)] antialiased">
        <Nav sports={sports} />
        <main className="flex-1 overflow-y-auto min-h-screen">{children}</main>
      </body>
    </html>
  );
}
