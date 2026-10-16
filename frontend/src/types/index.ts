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

export interface PickerElement {
  selector: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PickerData {
  screenshot_url: string;
  width: number;
  height: number;
  elements: PickerElement[];
}

export interface NotificationChannel {
  id: string;
  monitor_id?: string | null;
  channel_type: string;
  enabled: boolean;
  configuration: Record<string, any>;
  created_at: string;
}

export interface NotificationOutboxItem {
  id: string;
  monitor_id: string;
  monitor_name: string;
  monitor_url: string;
  version_id: string;
  channel_id: string;
  channel_type: string;
  state: 'pending' | 'sending' | 'sent' | 'failed';
  attempts: number;
  last_error?: string | null;
  sent_at?: string | null;
  created_at: string;
}

export interface JudgeNotificationChannel {
  id: string;
  monitor_id: string;
  monitor_name?: string;
  channel_type: 'discord' | 'telegram';
  enabled: boolean;
  is_verified: boolean;
  configuration: Record<string, any>;
  created_at: string;
}

export interface JudgeNotificationSettings {
  channels: {
    discord?: JudgeNotificationChannel | null;
    telegram?: JudgeNotificationChannel | null;
  };
  limits: {
    max_channels_per_type: number;
    test_rate_limit_per_hour: number;
    max_alerts_volume: number;
  };
}

export interface ActivityItem {
  id: string;
  event_type: string;
  status: string;
  monitor_id: string;
  monitor_name: string;
  monitor_url: string;
  timestamp: string;
  title: string;
  summary: string;
  version_id?: string | null;
  comparison_url?: string | null;
  metadata?: Record<string, any>;
}


