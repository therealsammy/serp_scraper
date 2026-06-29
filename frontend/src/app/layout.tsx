import type { Metadata } from "next";
import "./globals.css";
import { NavBar } from "@/components/NavBar";
import { WelcomeModal, GITHUB_URL } from "@/components/WelcomeModal";

export const metadata: Metadata = {
  title: "SERP Research Tool",
  description: "Multi-provider search + content extraction",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <NavBar />
        <WelcomeModal />
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 py-8 text-sm text-muted-foreground">
          Free demo project · keep to ~3 searches/day ·{" "}
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="hover:underline">
            View on GitHub
          </a>
        </footer>
      </body>
    </html>
  );
}
