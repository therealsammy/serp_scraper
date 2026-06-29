"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { clearAuth, getAuth } from "@/lib/auth";
import type { TokenResponse } from "@/lib/types";
import { Button } from "./ui";

export function NavBar() {
  const [auth, setAuth] = useState<TokenResponse | null>(null);
  useEffect(() => setAuth(getAuth()), []);

  return (
    <header className="border-b border-border bg-background">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <span className="rounded bg-primary px-1.5 py-0.5 text-xs text-primary-foreground">
            SERP
          </span>
          Research Tool
        </Link>
        <nav className="flex items-center gap-3 text-sm">
          <Link href="/" className="hover:underline">Search</Link>
          <a
            href="https://github.com/therealsammy/serp_scraper"
            target="_blank"
            rel="noreferrer"
            className="hover:underline"
          >
            GitHub
          </a>
          {auth?.role === "admin" && (
            <Link href="/admin" className="hover:underline">Admin</Link>
          )}
          {auth ? (
            <>
              <span className="text-muted-foreground">{auth.email}</span>
              <Button
                variant="outline"
                onClick={() => {
                  clearAuth();
                  location.href = "/";
                }}
              >
                Sign out
              </Button>
            </>
          ) : (
            <Link href="/login">
              <Button variant="outline">Sign in</Button>
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
