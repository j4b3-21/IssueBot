export type DisplayStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "awaiting_approval"
  | "comment_published";

export interface InvestigationSummary {
  id: string;
  repo_full_name: string;
  issue_number: number;
  issue_title: string;
  issue_url: string;
  status: string;
  display_status: DisplayStatus;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  mock: boolean;
}

export interface SourceItem {
  title: string;
  url: string | null;
  snippet: string;
  linkable: boolean;
  retrieved_at: string;
}

export interface Report {
  summary: string;
  documented_facts: string[];
  historical_evidence: { text: string; url: string; number: number }[];
  hypotheses: string[];
  unknowns: string[];
  next_steps: string[];
  questions_for_reporter: string[];
  sources: SourceItem[];
  related_issues: {
    number: number;
    title: string;
    url: string;
    state: string;
    excerpt: string;
    reason: string;
  }[];
  limitations: string[];
  mock: boolean;
  ai_generated: boolean;
  evidence_note: string;
}

export interface InvestigationDetail extends InvestigationSummary {
  issue_body: string;
  issue_author: string;
  issue_labels: string[];
  report: Report | null;
  audit: { actor: string; action: string; created_at: string; detail: Record<string, unknown> }[];
  published_comment: { comment_url: string | null; approved_by: string; state: string } | null;
  comment_preview: { body: string; content_sha256: string; repo_full_name: string; issue_number: number } | null;
  actions: {
    publish_allowed: boolean;
    publish_block_reason: string | null;
    retry_allowed: boolean;
    demo_mode: boolean;
  };
}

export interface SettingsView {
  demo_mode: boolean;
  public_base_url: string;
  webhook_url: string;
  docsgpt_base_url: string;
  docsgpt_agent_id: string;
  docsgpt_api_key_configured: boolean;
  github_app_id: string;
  github_private_key_configured: boolean;
  github_webhook_secret_configured: boolean;
  allowed_repos: string[];
  publish_enabled: boolean;
  publish_effective: boolean;
  allow_private_docsgpt: boolean;
  installations: { installation_id: number; account_login: string; status: string }[];
}

export interface HealthView {
  api: string;
  database: string;
  worker: string;
  docsgpt: string;
  github: string;
  publish_enabled: boolean;
}
