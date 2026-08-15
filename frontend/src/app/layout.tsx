import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "NFL BetMaster — Analytics & Bet Tracking",
  description:
    "Free, self-hosted NFL analytics platform with live scores, odds tracking, EPA analysis, and personal bet management.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="flex min-h-screen">
        <Sidebar />
        {/* Main content area — offset by sidebar width */}
        <main className="flex-1 ml-64 p-6 lg:p-8">
          {children}
        </main>
      </body>
    </html>
  );
}
