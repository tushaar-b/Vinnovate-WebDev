export interface HealthStatus {
  status: string;
  database: string;
  redis: string;
}

export type SensitivityLevel = 'low' | 'medium' | 'high';
export type MonitorStatus = 'pending' | 'ok' | 'changed' | 'error' | 'blocked';
export type CheckRunState = 'queued' | 'running' | 'unchanged' | 'changed' | 'baseline' | 'error' | 'blocked';
export type RuleType = 'watch' | 'ignore';

export interface MonitorRule {
  id: string;
  monitor_id: string;
  rule_type: RuleType;
  css_selector: string;
  label?: string | null;
  created_at: string;
}

export interface MonitorSummary {
  id: string;
  name: string;
  url: string;
  interval_minutes: number;
  sensitivity: SensitivityLevel;
  enabled: boolean;
  status: MonitorStatus;
  last_checked_at?: string | null;
  last_changed_at?: string | null;
  next_check_at: string;
  last_error?: string | null;
  versions_count: number;
  created_at: string;
}

export interface MonitorDetail extends MonitorSummary {
  canonical_url: string;
  updated_at: string;
  rules: MonitorRule[];
}

export interface CheckRun {
  id: string;
  monitor_id: string;
  state: CheckRunState;
  started_at?: string | null;
  finished_at?: string | null;
  http_status?: number | null;
  error_code?: string | null;
  error_message?: string | null;
  duration_ms?: number | null;
  version_id?: string | null;
}

export interface VersionSummary {
  id: string;
  monitor_id: string;
  sequence_number: number;
  captured_at: string;
  content_hash: string;
  screenshot_url: string;
  short_preview: string;
}

export interface VersionDetail extends VersionSummary {
  normalized_text: string;
}

export interface CreateMonitorInput {
  name: string;
  url: string;
  interval_minutes: number;
  sensitivity: SensitivityLevel;
}

export interface TextDiffItem {
  kind: 'equal' | 'add' | 'remove';
  text: string;
}

export interface VersionComparison {
  old_version: VersionDetail;
  new_version: VersionDetail;
  text_diff: TextDiffItem[];
  image_old_url: string;
  image_new_url: string;
  image_diff_url?: string | null;
  change_ratio: number;
}

