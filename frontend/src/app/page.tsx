"use client";

import { useRef, useState } from "react";
import { api, API_URL } from "@/lib/api";
import { authHeader } from "@/lib/auth";
import type { EntityResponse, EntityResult, ExtractedResult, SearchJob } from "@/lib/types";
import { Badge, Button, Card, Input } from "@/components/ui";
import { SearchLoader } from "@/components/SearchLoader";

// Map internal served_by strings (e.g. "apify:own", "serp_fallback") to friendly labels.
function prettyProvider(servedBy: string): string {
  const base = servedBy.split(/[:+]/)[0];
  if (servedBy.startsWith("serp_fallback")) return "Google (backup)";
  return { apify: "Google", ddg: "DuckDuckGo", brave: "Brave" }[base] ?? base;
}

const PROVIDERS = [
  { value: "apify", label: "Google" },
  { value: "brave", label: "Brave" },
  { value: "ddg", label: "DuckDuckGo" },
];

const COUNTRIES = [
  { value: "us", label: "United States" },
  { value: "gb", label: "United Kingdom" },
  { value: "ca", label: "Canada" },
  { value: "au", label: "Australia" },
  { value: "de", label: "Germany" },
  { value: "fr", label: "France" },
  { value: "ng", label: "Nigeria" },
  { value: "in", label: "India" },
];

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "pt", label: "Portuguese" },
  { value: "zh-CN", label: "Chinese" },
  { value: "ar", label: "Arabic" },
  { value: "hi", label: "Hindi" },
];

function statusBadge(s: ExtractedResult["status"]) {
  switch (s) {
    case "extracted": return <Badge tone="green">extracted</Badge>;
    case "blocked": return <Badge tone="amber">blocked</Badge>;
    case "error": return <Badge tone="red">error</Badge>;
    default: return <Badge tone="blue">loading…</Badge>;
  }
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState("apify");
  const [count, setCount] = useState(10);
  const [country, setCountry] = useState("us");
  const [language, setLanguage] = useState("en");
  const [location, setLocation] = useState("");
  const [results, setResults] = useState<ExtractedResult[]>([]);
  const [job, setJob] = useState<SearchJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  // Entity extraction state, keyed by result rank.
  const [entities, setEntities] = useState<Record<number, EntityResponse>>({});
  const [entityLoading, setEntityLoading] = useState<number | null>(null);
  const [entityError, setEntityError] = useState<Record<number, string>>({});
  const esRef = useRef<EventSource | null>(null);

  async function extractEntities(r: ExtractedResult) {
    if (entities[r.rank]) return; // cached in component state
    setEntityLoading(r.rank);
    setEntityError((e) => ({ ...e, [r.rank]: "" }));
    try {
      const res = await api<EntityResponse>("/entities", {
        method: "POST",
        body: JSON.stringify({ text: r.full_text, language }),
      });
      setEntities((e) => ({ ...e, [r.rank]: res }));
    } catch (err) {
      setEntityError((e) => ({ ...e, [r.rank]: (err as Error).message }));
    } finally {
      setEntityLoading(null);
    }
  }

  async function runSearch(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setResults([]);
    setJob(null);
    setLoading(true);
    esRef.current?.close();

    try {
      const j = await api<SearchJob>("/search", {
        method: "POST",
        body: JSON.stringify({
          query,
          provider,
          count,
          geo: { country, language, location: location.trim() || null },
        }),
      });
      setJob(j);
      streamResults(j.job_id);
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  }

  function streamResults(jobId: string) {
    // EventSource can't send Authorization headers; pass token via query for the
    // stream endpoint only (it just reads a cached job by id).
    const es = new EventSource(`${API_URL}/stream/${jobId}`);
    esRef.current = es;
    es.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.event === "result") {
        setResults((prev) => [...prev, msg.data as ExtractedResult].sort((a, b) => a.rank - b.rank));
      } else if (msg.event === "done") {
        setLoading(false);
        es.close();
      }
    };
    es.onerror = () => {
      setLoading(false);
      es.close();
    };
  }

  async function exportAs(format: "csv" | "json") {
    const res = await fetch(`${API_URL}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: JSON.stringify({ results, format }),
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `results.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Search the open web</h1>
        <p className="text-sm text-muted-foreground">
          Pick a provider, run a query, and get clean extracted article text.
        </p>
      </div>

      <Card className="p-4">
        <form onSubmit={runSearch} className="flex flex-wrap items-center gap-3">
          <Input
            placeholder="e.g. best CRM for small teams 2026"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="min-w-[260px] flex-1"
            required
          />
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="h-10 rounded-md border border-border bg-background px-3 text-sm"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
          <select
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="h-10 rounded-md border border-border bg-background px-3 text-sm"
          >
            {[5, 10, 20].map((n) => (
              <option key={n} value={n}>{n} results</option>
            ))}
          </select>
          <Button type="submit" disabled={loading}>
            {loading ? "Searching…" : "Search"}
          </Button>
        </form>

        {/* Geo-targeting (applies to Google/Brave; ignored by DuckDuckGo) */}
        <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-border pt-3">
          <span className="text-xs font-medium text-muted-foreground">Location:</span>
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          >
            {COUNTRIES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          >
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
          <Input
            placeholder="City (optional), e.g. Austin, Texas, United States"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="h-9 min-w-[280px] flex-1"
          />
          {provider === "ddg" && (
            <span className="text-xs text-amber-600">
              DuckDuckGo ignores location — use Google for geo-targeting
            </span>
          )}
        </div>
      </Card>

      {error && (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</Card>
      )}

      {job && (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <span>Served by <Badge tone="blue">{prettyProvider(job.served_by)}</Badge></span>
          {job.cached && <Badge tone="green">cache hit</Badge>}
          <div className="ml-auto flex gap-2">
            <Button variant="outline" onClick={() => exportAs("csv")} disabled={!results.length}>
              Export CSV
            </Button>
            <Button variant="outline" onClick={() => exportAs("json")} disabled={!results.length}>
              Export JSON
            </Button>
          </div>
        </div>
      )}

      {loading && results.length === 0 && <SearchLoader />}

      <div className="space-y-3">
        {results.map((r) => (
          <Card key={r.rank} className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <a href={r.url} target="_blank" rel="noreferrer"
                   className="font-medium text-accent hover:underline">
                  {r.rank}. {r.title || r.url}
                </a>
                <div className="truncate text-xs text-muted-foreground">{r.domain}</div>
                {r.snippet && <p className="mt-1 text-sm">{r.snippet}</p>}
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                {statusBadge(r.status)}
                {r.word_count > 0 && (
                  <span className="text-xs text-muted-foreground">{r.word_count} words</span>
                )}
              </div>
            </div>
            {r.full_text && (
              <div className="mt-3">
                <Button
                  variant="ghost"
                  className="h-7 px-2 text-xs"
                  onClick={() => setExpanded(expanded === r.rank ? null : r.rank)}
                >
                  {expanded === r.rank ? "Hide" : "Show"} extracted text
                </Button>
                {expanded === r.rank && (
                  <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-xs">
                    {r.full_text}
                  </pre>
                )}

                {/* Entity extraction */}
                <div className="mt-2">
                  <Button
                    variant="ghost"
                    className="h-7 px-2 text-xs"
                    disabled={entityLoading === r.rank}
                    onClick={() => extractEntities(r)}
                  >
                    {entityLoading === r.rank
                      ? "Extracting entities…"
                      : entities[r.rank]
                      ? "Top entities"
                      : "Extract entities"}
                  </Button>
                  {entityError[r.rank] && (
                    <span className="ml-2 text-xs text-red-600">{entityError[r.rank]}</span>
                  )}
                  {entities[r.rank] && (
                    <div className="mt-2 rounded-md bg-muted p-3">
                      <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                        <span>Top {entities[r.rank].entities.length} by salience</span>
                        <Badge tone={entities[r.rank].source === "spacy" ? "muted" : "blue"}>
                          {entities[r.rank].source === "google_nl"
                            ? "Google NL"
                            : entities[r.rank].source === "langextract"
                            ? "LangExtract"
                            : "computed (spaCy)"}
                        </Badge>
                      </div>
                      <div className="space-y-1.5">
                        {entities[r.rank].entities.map((ent: EntityResult, i: number) => (
                          <div key={i} className="flex items-center gap-2 text-xs">
                            <span className="w-44 shrink-0 truncate font-medium">{ent.name}</span>
                            {ent.type && <Badge tone="muted">{ent.type}</Badge>}
                            <div className="h-2 flex-1 rounded bg-background">
                              <div
                                className="h-2 rounded bg-accent"
                                style={{ width: `${Math.max(ent.salience * 100, 3)}%` }}
                              />
                            </div>
                            <span className="w-10 shrink-0 text-right tabular-nums text-muted-foreground">
                              {ent.salience.toFixed(2)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
