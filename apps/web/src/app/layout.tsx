import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "NewsFetcher",
  description: "Kuwait media-monitoring SaaS — Phase 0 baseline",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily: "IBM Plex Sans Arabic, Noto Naskh Arabic, Georgia, serif",
          background:
            "radial-gradient(circle at top left, #e8f1f5 0%, #f7f3ea 45%, #eef2f7 100%)",
          minHeight: "100vh",
          color: "#122033",
        }}
      >
        {children}
      </body>
    </html>
  );
}
