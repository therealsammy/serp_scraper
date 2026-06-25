export interface SearchJob {
  job_id: string;
  query: string;
  provider: string;
  count: number;
  served_by: string;
  cached: boolean;
}

export interface ExtractedResult {
  title: string;
  url: string;
  snippet: string;
  rank: number;
  source_provider: string;
  full_text: string;
  word_count: number;
  domain: string;
  status: "pending" | "extracted" | "blocked" | "error";
  extracted_at: string | null;
}

export interface EntityResult {
  name: string;
  type: string;
  salience: number;
  mentions: number;
  source: "google_nl" | "langextract" | "spacy";
}

export interface EntityResponse {
  source: string;
  units_charged: number;
  entities: EntityResult[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
  email: string;
}

export interface UserRow {
  id: string;
  email: string;
  role: string;
  tier: string;
  is_active: boolean;
  created_at: string;
}

export interface InviteRow {
  id: string;
  email: string;
  expires_at: string;
  used_at: string | null;
  status: "pending" | "used" | "expired";
}

export interface InviteResponse {
  id: string;
  email: string;
  accept_url: string;
  expires_at: string;
}

export interface ProviderHealth {
  name: string;
  daily_used: number;
  daily_cap: number | null;
  healthy: boolean;
  breaker_open: boolean;
}

export interface CostStatus {
  guarded_provider: string;
  daily_used: number;
  daily_cap: number;
  kill_switch_active: boolean;
}
