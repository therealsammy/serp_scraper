"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getAuth } from "@/lib/auth";
import type {
  CostStatus,
  InviteResponse,
  InviteRow,
  ProviderHealth,
  UserRow,
} from "@/lib/types";
import { Badge, Button, Card, Input } from "@/components/ui";

export default function AdminPage() {
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [invites, setInvites] = useState<InviteRow[]>([]);
  const [providers, setProviders] = useState<ProviderHealth[]>([]);
  const [cost, setCost] = useState<CostStatus | null>(null);
  const [cache, setCache] = useState<{ hit_rate_pct: number; hits: number; misses: number } | null>(null);
  const [entityCost, setEntityCost] = useState<{
    google_nl_units_used: number;
    google_nl_units_cap: number;
    google_nl_free_tier: number;
    google_nl_estimated_spend_usd: number;
    langextract_used_today: number;
    langextract_daily_cap: number;
  } | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [lastLink, setLastLink] = useState<InviteResponse | null>(null);
  const [error, setError] = useState("");

  async function loadAll() {
    try {
      const [u, i, p, c, ch, ec] = await Promise.all([
        api<UserRow[]>("/admin/users"),
        api<InviteRow[]>("/admin/invites"),
        api<ProviderHealth[]>("/admin/providers"),
        api<CostStatus>("/admin/costs"),
        api<{ hit_rate_pct: number; hits: number; misses: number }>("/admin/cache"),
        api<typeof entityCost>("/admin/entity-costs"),
      ]);
      setUsers(u); setInvites(i); setProviders(p); setCost(c); setCache(ch); setEntityCost(ec);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    const auth = getAuth();
    if (!auth || auth.role !== "admin") {
      setAllowed(false);
      return;
    }
    setAllowed(true);
    loadAll();
  }, []);

  async function createInvite(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const r = await api<InviteResponse>("/admin/invites", {
        method: "POST",
        body: JSON.stringify({ email: inviteEmail, tier: "registered" }),
      });
      setLastLink(r);
      setInviteEmail("");
      loadAll();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function revoke(id: string) {
    await api(`/admin/invites/${id}`, { method: "DELETE" });
    loadAll();
  }

  async function toggleUser(u: UserRow) {
    await api(`/admin/users/${u.id}/${u.is_active ? "disable" : "enable"}`, { method: "POST" });
    loadAll();
  }

  if (allowed === false)
    return <p className="text-sm text-red-600">Admin access required. <a href="/login" className="underline">Sign in</a>.</p>;
  if (allowed === null) return null;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">Admin</h1>
      {error && <Card className="border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</Card>}

      {/* Metrics */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground">
            {cost?.guarded_provider ?? "Guarded"} daily cap
          </div>
          {cost && (
            <>
              <div className="mt-1 text-2xl font-semibold">{cost.daily_used}/{cost.daily_cap}</div>
              {cost.kill_switch_active
                ? <Badge tone="red">kill-switch active</Badge>
                : <Badge tone="green">within daily cap</Badge>}
            </>
          )}
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground">Cache hit rate</div>
          {cache && (
            <>
              <div className="mt-1 text-2xl font-semibold">{cache.hit_rate_pct}%</div>
              <span className="text-xs text-muted-foreground">{cache.hits} hits / {cache.misses} misses</span>
            </>
          )}
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground">Users</div>
          <div className="mt-1 text-2xl font-semibold">{users.length}</div>
          <span className="text-xs text-muted-foreground">{invites.filter(i => i.status === "pending").length} pending invites</span>
        </Card>
      </div>

      {/* Entity extraction usage */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground">Google NL units (this month)</div>
          {entityCost && (
            <>
              <div className="mt-1 text-2xl font-semibold">
                {entityCost.google_nl_units_used}/{entityCost.google_nl_units_cap}
              </div>
              <div className="flex items-center gap-2">
                {entityCost.google_nl_units_used >= entityCost.google_nl_units_cap
                  ? <Badge tone="red">cap reached → spaCy</Badge>
                  : <Badge tone="green">within free tier</Badge>}
                <span className="text-xs text-muted-foreground">
                  est. ${entityCost.google_nl_estimated_spend_usd.toFixed(2)} · free {entityCost.google_nl_free_tier}/mo
                </span>
              </div>
            </>
          )}
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground">LangExtract (today)</div>
          {entityCost && (
            <>
              <div className="mt-1 text-2xl font-semibold">
                {entityCost.langextract_used_today}/{entityCost.langextract_daily_cap}
              </div>
              <span className="text-xs text-muted-foreground">LLM actor requests · resets daily</span>
            </>
          )}
        </Card>
      </div>

      {/* Provider health */}
      <section>
        <h2 className="mb-2 font-semibold">SERP fallback health</h2>
        <Card className="divide-y divide-border">
          {providers.map((p) => (
            <div key={p.name} className="flex items-center justify-between p-3 text-sm">
              <span className="font-medium">{p.name}</span>
              <span className="text-muted-foreground">{p.daily_used}/{p.daily_cap ?? "∞"} today</span>
              {p.breaker_open ? <Badge tone="red">breaker open</Badge>
                : p.healthy ? <Badge tone="green">healthy</Badge>
                : <Badge tone="amber">not configured</Badge>}
            </div>
          ))}
          {!providers.length && <div className="p-3 text-sm text-muted-foreground">No fallback vendors configured.</div>}
        </Card>
      </section>

      {/* Invite */}
      <section>
        <h2 className="mb-2 font-semibold">Invite a user</h2>
        <Card className="p-4">
          <form onSubmit={createInvite} className="flex gap-3">
            <Input type="email" placeholder="person@example.com" value={inviteEmail}
                   onChange={(e) => setInviteEmail(e.target.value)} required />
            <Button type="submit">Generate link</Button>
          </form>
          {lastLink && (
            <div className="mt-3 rounded-md bg-muted p-3 text-xs">
              <p className="mb-1 text-muted-foreground">Email this single-use link to {lastLink.email}:</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 break-all">{lastLink.accept_url}</code>
                <Button variant="outline" className="h-7 px-2"
                        onClick={() => navigator.clipboard.writeText(lastLink.accept_url)}>
                  Copy
                </Button>
              </div>
            </div>
          )}
        </Card>
      </section>

      {/* Pending invites */}
      <section>
        <h2 className="mb-2 font-semibold">Invites</h2>
        <Card className="divide-y divide-border">
          {invites.map((i) => (
            <div key={i.id} className="flex items-center justify-between p-3 text-sm">
              <span>{i.email}</span>
              <Badge tone={i.status === "pending" ? "blue" : i.status === "used" ? "green" : "muted"}>
                {i.status}
              </Badge>
              {i.status === "pending" && (
                <Button variant="destructive" className="h-7 px-2 text-xs" onClick={() => revoke(i.id)}>
                  Revoke
                </Button>
              )}
            </div>
          ))}
          {!invites.length && <div className="p-3 text-sm text-muted-foreground">No invites yet.</div>}
        </Card>
      </section>

      {/* Users */}
      <section>
        <h2 className="mb-2 font-semibold">Users</h2>
        <Card className="divide-y divide-border">
          {users.map((u) => (
            <div key={u.id} className="flex items-center justify-between p-3 text-sm">
              <div>
                <span className="font-medium">{u.email}</span>
                <span className="ml-2 text-xs text-muted-foreground">{u.role} · {u.tier}</span>
              </div>
              <div className="flex items-center gap-2">
                {u.is_active ? <Badge tone="green">active</Badge> : <Badge tone="red">disabled</Badge>}
                {u.role !== "admin" && (
                  <Button variant="outline" className="h-7 px-2 text-xs" onClick={() => toggleUser(u)}>
                    {u.is_active ? "Disable" : "Enable"}
                  </Button>
                )}
              </div>
            </div>
          ))}
        </Card>
      </section>
    </div>
  );
}
