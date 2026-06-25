"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import type { TokenResponse } from "@/lib/types";
import { Button, Card, Input } from "@/components/ui";

function AcceptInvite() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [email, setEmail] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) {
      setError("Missing invitation token");
      return;
    }
    api<{ email: string }>(`/auth/invite-info?token=${encodeURIComponent(token)}`)
      .then((r) => setEmail(r.email))
      .catch((e) => setError((e as Error).message));
  }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const t = await api<TokenResponse>("/auth/accept-invite", {
        method: "POST",
        body: JSON.stringify({ token, password }),
      });
      saveAuth(t);
      location.href = "/";
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <Card className="p-6">
        <h1 className="text-xl font-semibold">Accept your invitation</h1>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        {email && (
          <form onSubmit={submit} className="mt-4 space-y-3">
            {/* Email is bound to the invite token — read-only. */}
            <Input value={email} readOnly className="bg-muted" />
            <Input type="password" placeholder="Choose a password" value={password}
                   onChange={(e) => setPassword(e.target.value)} required minLength={8} />
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Creating account…" : "Create account"}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <AcceptInvite />
    </Suspense>
  );
}
