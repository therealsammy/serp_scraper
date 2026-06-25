"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import type { TokenResponse } from "@/lib/types";
import { Button, Card, Input } from "@/components/ui";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const t = await api<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      saveAuth(t);
      location.href = t.role === "admin" ? "/admin" : "/";
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <Card className="p-6">
        <h1 className="text-xl font-semibold">Sign in</h1>
        <p className="mb-4 text-sm text-muted-foreground">
          Accounts are invite-only. Contact the admin for access.
        </p>
        <form onSubmit={submit} className="space-y-3">
          <Input type="email" placeholder="Email" value={email}
                 onChange={(e) => setEmail(e.target.value)} required />
          <Input type="password" placeholder="Password" value={password}
                 onChange={(e) => setPassword(e.target.value)} required />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
