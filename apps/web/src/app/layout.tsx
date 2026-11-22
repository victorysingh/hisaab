import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { Bricolage_Grotesque, Geist, Geist_Mono, Inter } from "next/font/google";
import "./globals.css";
import "./hisaab.css";
import { cn } from "@/lib/utils";
import { MicBar } from "@/components/mic-bar";
import { BottomNav } from "@/components/bottom-nav";
import { SidePanel } from "@/components/side-panel";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const display = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-display" });

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Hisaab: voice-first back office for tutors",
  description: "Who owes you, will you make rent, and what to do about it. Just ask.",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#0b6e5b",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={cn(
        "h-full",
        "antialiased",
        geistSans.variable,
        geistMono.variable,
        display.variable,
        "font-sans",
        inter.variable,
      )}
    >
      <body className="dots min-h-full text-[var(--ink)]">
        <SidePanel />
        {/* The app itself: phone-width column, framed on larger screens */}
        <div className="mx-auto flex min-h-screen w-full max-w-md flex-col overflow-x-hidden bg-[var(--paper)] pb-40 md:border-x-2 md:border-[var(--ink)]">
          {children}
        </div>
        <Suspense fallback={null}>
          <MicBar />
          <BottomNav />
        </Suspense>
      </body>
    </html>
  );
}
