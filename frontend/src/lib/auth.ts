"use client";

import type { TokenResponse } from "./types";

const KEY = "serp_auth";

export function saveAuth(t: TokenResponse) {
  localStorage.setItem(KEY, JSON.stringify(t));
}

export function getAuth(): TokenResponse | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(KEY);
  return raw ? (JSON.parse(raw) as TokenResponse) : null;
}

export function clearAuth() {
  localStorage.removeItem(KEY);
}

export function authHeader(): Record<string, string> {
  const a = getAuth();
  return a ? { Authorization: `Bearer ${a.access_token}` } : {};
}
