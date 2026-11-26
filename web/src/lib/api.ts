export const API_BASE =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
    : process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export const API_PUBLIC_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type Opportunity = {
  id: number;
  source: string;
  source_url: string | null;
  source_reference: string | null;
  title: string;
  buyer: string | null;
  buyer_type: string | null;
  object: string | null;
  description: string | null;
  lots: Record<string, unknown>[];
  cpv: string[];
  procedure: string | null;
  market_type: string | null;
  location: string | null;
  publication_date: string | null;
  deadline: string | null;
  estimated_budget: number | null;
  status: string;
  global_score: number;
  score_by_family: Record<string, number>;
  ai_summary: string | null;
  ai_report: Record<string, unknown> | null;
  keyword_traces: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export type OpportunityListItem = Pick<
  Opportunity,
  | "id"
  | "source"
  | "source_url"
  | "source_reference"
  | "title"
  | "buyer"
  | "object"
  | "description"
  | "location"
  | "publication_date"
  | "deadline"
  | "status"
  | "global_score"
  | "ai_summary"
  | "created_at"
  | "updated_at"
>;

export type OpportunityDocument = {
  id: number;
  opportunity_id: number;
  filename: string;
  content_type: string | null;
  content_hash: string;
  created_at: string;
};

export type OpportunityAudit = {
  id: number;
  action: string;
  action_label: string;
  actor_user_id: number | null;
  actor_label: string;
  actor_role: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  transition: Record<string, unknown> | null;
  created_at: string;
};

export type OpportunityBatchAnalyzeResult = {
  run_id: number | null;
  analyzed_count: number;
  failed_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  opportunities: Opportunity[];
  errors: Array<Record<string, unknown>>;
};

export type OpportunitySearchResult = {
  query: string;
  mode: string;
  total: number;
  run_id: number | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  items: OpportunityListItem[];
  highlights: Record<string, string[]>;
};

export type Dashboard = {
  total_opportunities: number;
  rejected_opportunities: number;
  high_relevance: number;
  to_analyze: number;
  analyzed_opportunities: number;
  relevant_opportunities: number;
  study_opportunities: number;
  deadlines_soon: number;
  active_sources: number;
  token_usage: {
    total_tokens: number;
    input_tokens: number;
    output_tokens: number;
    run_count: number;
    orchestration_run_count: number;
    orchestrated_tokens: number;
    success_count: number;
    failure_count: number;
    last_run_at: string | null;
    last_model: string | null;
  };
  score_buckets: Record<string, number>;
  status_counts: Record<string, number>;
  latest_opportunities: OpportunityListItem[];
  urgent_opportunities: OpportunityListItem[];
  map_points: DashboardMapPoint[];
};

export type DashboardMapOpportunity = {
  id: number;
  title: string;
  buyer: string | null;
  status: string;
  global_score: number;
  deadline: string | null;
};

export type DashboardMapPoint = {
  key: string;
  department_code: string | null;
  department_name: string;
  label: string;
  latitude: number | null;
  longitude: number | null;
  x: number | null;
  y: number | null;
  is_overseas: boolean;
  count: number;
  highest_score: number;
  status_counts: Record<string, number>;
  deadline_counts: Record<string, number>;
  search_text: string | null;
  opportunities: DashboardMapOpportunity[];
};

export type FrontAnalysisResult = {
  analysis_date: string;
  days_back: number;
  status: string;
  fetched_count: number;
  new_count: number;
  already_known_count: number;
  skipped_low_score_count: number;
  analyzed_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  run_id: number;
  new_opportunities: OpportunityListItem[];
  rejected_candidates: Array<{
    source: string;
    source_reference: string | null;
    opportunity_id: number | null;
    title: string | null;
    score: number;
    reason: string | null;
  }>;
};

export type FrontAnalysisLaunch = {
  task_id: string;
  status: "queued" | "running";
};

export type FrontAnalysisTaskStatus = {
  task_id: string;
  status: "queued" | "running" | "success" | "failed";
  result: FrontAnalysisResult | null;
  error: string | null;
};

export type KeywordCategory = {
  id: number;
  name: string;
  threshold: number;
  is_active: boolean;
  strategic_tags: string[];
};

export type Keyword = {
  id: number;
  category_id: number;
  term: string;
  weight: number;
  is_active: boolean;
  synonyms: { id: number; term: string }[];
};

export type Source = {
  id: number;
  name: string;
  connector_type: string;
  url: string | null;
  api_endpoint: string | null;
  frequency_minutes: number;
  is_active: boolean;
  config: Record<string, unknown>;
  last_run_at: string | null;
};

export type SourceRun = {
  id: number;
  source_id: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  fetched_count: number;
  created_count: number;
  error_message: string | null;
  logs: Array<Record<string, unknown>>;
};

export type SourceRunLaunch = {
  task_id: string;
  source_id: number;
  status: string;
};

export type SourceRunTaskStatus = {
  task_id: string;
  status: "queued" | "running" | "success" | "failed";
  result: {
    source_run_id: number;
    status: string;
    fetched_count: number;
    created_count: number;
    error: string | null;
  } | null;
  error: string | null;
};

export type Notification = {
  id: number;
  type: string;
  title: string;
  message: string;
  opportunity_id: number | null;
  is_read: boolean;
  created_at: string;
};

export type UserProfile = {
  id: number;
  email: string;
  full_name: string | null;
  role: "admin" | "analyst" | "viewer";
  is_active: boolean;
};

export type AgentRun = {
  id: number;
  agent_id: number;
  status: string;
  task_name: string;
  target_type: string | null;
  target_id: string | null;
  started_at: string;
  finished_at: string | null;
  input_count: number;
  output_count: number;
  success_count: number;
  failure_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  model: string | null;
  error_message: string | null;
  logs: Array<Record<string, unknown>>;
  metadata_json: Record<string, unknown>;
};

export type AgentStats = {
  run_count: number;
  success_count: number;
  failure_count: number;
  skipped_count: number;
  success_rate: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  orchestrated_tokens: number;
  orchestrated_input_tokens: number;
  orchestrated_output_tokens: number;
  last_status: string | null;
};

export type Agent = {
  id: number;
  slug: string;
  name: string;
  description: string;
  task: string;
  is_active: boolean;
  sort_order: number;
  config: Record<string, unknown>;
  last_run_at: string | null;
  schedule_enabled: boolean;
  schedule_frequency: string;
  schedule_interval: number;
  schedule_time: string;
  schedule_weekday: number;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
  stats: AgentStats;
  recent_runs: AgentRun[];
};

export function getStoredUser(): UserProfile | null {
  if (typeof window === "undefined") return null;
  const rawUser = window.localStorage.getItem("live_pulse_user");
  if (!rawUser) return null;
  try {
    return JSON.parse(rawUser) as UserProfile;
  } catch {
    return null;
  }
}

export function canAccessBackoffice(user: UserProfile | null) {
  return user?.role === "admin";
}

export function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("live_pulse_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...(init?.headers || {})
    }
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function getDashboard() {
  return request<Dashboard>("/dashboard");
}

export async function getDashboardMap() {
  return request<DashboardMapPoint[]>("/dashboard/map");
}

export async function getOpportunities(query = "") {
  return request<{ items: OpportunityListItem[]; total: number }>(`/opportunities${query}`);
}

export async function searchOpportunities(query = "") {
  return request<OpportunitySearchResult>(`/opportunities/search${query}`);
}

export async function getOpportunity(id: string | number) {
  return request<Opportunity>(`/opportunities/${id}`);
}

export async function getOpportunityDocuments(id: string | number) {
  return request<OpportunityDocument[]>(`/opportunities/${id}/documents`);
}

export async function getOpportunityAudit(id: string | number) {
  return request<OpportunityAudit[]>(`/opportunities/${id}/audit`);
}

export async function updateOpportunityStatus(id: string | number, status: string, origin?: string) {
  return request<Opportunity>(`/opportunities/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status, origin })
  });
}

export async function analyzeOpportunities(ids: number[]) {
  return request<OpportunityBatchAnalyzeResult>("/opportunities/analyze-batch", {
    method: "POST",
    body: JSON.stringify({ opportunity_ids: ids })
  });
}

export async function runFrontAnalysis(payload: { analysis_date: string; days_back?: number; limit?: number; min_live_score?: number; departments?: string[] }) {
  return request<FrontAnalysisLaunch>("/frontoffice/analyze", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getFrontAnalysisStatus(taskId: string) {
  return request<FrontAnalysisTaskStatus>(`/frontoffice/analyze/${taskId}`);
}

export async function getReport(id: string | number) {
  return request<{ report: Record<string, unknown>; html: string | null; model: string }>(`/opportunities/${id}/report`);
}

export async function getKeywordData() {
  const [categories, keywords] = await Promise.all([
    request<KeywordCategory[]>("/keyword-categories"),
    request<Keyword[]>("/keywords")
  ]);
  return { categories, keywords };
}

export async function getSources() {
  return request<Source[]>("/sources");
}

export async function getSourceRuns(sourceId: number) {
  return request<SourceRun[]>(`/sources/${sourceId}/runs`);
}

export async function runSource(sourceId: number) {
  return request<SourceRunLaunch>(`/sources/${sourceId}/run`, { method: "POST" });
}

export async function getSourceRunTaskStatus(taskId: string) {
  return request<SourceRunTaskStatus>(`/sources/tasks/${taskId}`);
}

export async function getAgents() {
  return request<Agent[]>("/agents");
}

export async function getNotifications() {
  return request<Notification[]>("/notifications");
}
