import {
  HealthStatus,
  MonitorSummary,
  MonitorDetail,
  CheckRun,
  VersionSummary,
  VersionDetail,
  CreateMonitorInput,
} from '../types';

const BASE_URL = '';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorMsg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail?.error?.message) {
        errorMsg = body.detail.error.message;
      } else if (body.detail) {
        errorMsg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errorMsg);
  }
  return res.json();
}

export const api = {
  async getHealth(): Promise<HealthStatus> {
    const res = await fetch(`${BASE_URL}/api/health`);
    return handleResponse<HealthStatus>(res);
  },

  async getMonitors(): Promise<{ items: MonitorSummary[]; total: number }> {
    const res = await fetch(`${BASE_URL}/api/monitors`);
    return handleResponse<{ items: MonitorSummary[]; total: number }>(res);
  },

  async createMonitor(input: CreateMonitorInput): Promise<MonitorDetail> {
    const res = await fetch(`${BASE_URL}/api/monitors`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    return handleResponse<MonitorDetail>(res);
  },

  async getMonitor(id: string): Promise<MonitorDetail> {
    const res = await fetch(`${BASE_URL}/api/monitors/${id}`);
    return handleResponse<MonitorDetail>(res);
  },

  async deleteMonitor(id: string): Promise<void> {
    const res = await fetch(`${BASE_URL}/api/monitors/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok && res.status !== 204) {
      throw new Error(`Failed to delete monitor (HTTP ${res.status})`);
    }
  },

  async queueCheck(id: string): Promise<{ check_run_id: string; job_id: string; state: string }> {
    const res = await fetch(`${BASE_URL}/api/monitors/${id}/checks`, {
      method: 'POST',
    });
    return handleResponse<{ check_run_id: string; job_id: string; state: string }>(res);
  },

  async getChecks(monitorId: string): Promise<{ items: CheckRun[] }> {
    const res = await fetch(`${BASE_URL}/api/monitors/${monitorId}/checks?limit=50`);
    return handleResponse<{ items: CheckRun[] }>(res);
  },

  async getCheck(checkId: string): Promise<CheckRun> {
    const res = await fetch(`${BASE_URL}/api/checks/${checkId}`);
    return handleResponse<CheckRun>(res);
  },

  async getVersions(monitorId: string): Promise<{ items: VersionSummary[] }> {
    const res = await fetch(`${BASE_URL}/api/monitors/${monitorId}/versions`);
    return handleResponse<{ items: VersionSummary[] }>(res);
  },

  async getVersion(monitorId: string, versionId: string): Promise<VersionDetail> {
    const res = await fetch(`${BASE_URL}/api/monitors/${monitorId}/versions/${versionId}`);
    return handleResponse<VersionDetail>(res);
  },

  async compareVersions(monitorId: string, fromId: string, toId: string) {
    const res = await fetch(`${BASE_URL}/api/monitors/${monitorId}/compare?from=${fromId}&to=${toId}`);
    return handleResponse<import('../types').VersionComparison>(res);
  },

  async getPicker(monitorId: string): Promise<import('../types').PickerData> {
    const res = await fetch(`${BASE_URL}/api/monitors/${monitorId}/picker`);
    return handleResponse<import('../types').PickerData>(res);
  },

  async updateRules(
    monitorId: string,
    rules: { rule_type: 'watch' | 'ignore'; css_selector: string; label?: string }[]
  ): Promise<import('../types').MonitorRule[]> {
    const res = await fetch(`${BASE_URL}/api/monitors/${monitorId}/rules`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules }),
    });
    return handleResponse<import('../types').MonitorRule[]>(res);
  },

  async getNotificationSettings(): Promise<Record<string, import('../types').NotificationChannel>> {
    const res = await fetch(`${BASE_URL}/api/settings/notifications`);
    return handleResponse<Record<string, import('../types').NotificationChannel>>(res);
  },

  async updateNotificationSettings(
    channelType: string,
    payload: { enabled: boolean; configuration: Record<string, any> }
  ): Promise<import('../types').NotificationChannel> {
    const res = await fetch(`${BASE_URL}/api/settings/notifications/${channelType}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<import('../types').NotificationChannel>(res);
  },

  async testNotification(
    channelType: string,
    configuration?: Record<string, any>
  ): Promise<{ success: boolean; message: string; channel_type: string }> {
    const res = await fetch(`${BASE_URL}/api/settings/notifications/${channelType}/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ configuration }),
    });
    return handleResponse<{ success: boolean; message: string; channel_type: string }>(res);
  },

  async getNotificationOutbox(limit: number = 50, state?: string): Promise<import('../types').NotificationOutboxItem[]> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (state && state !== 'all') query.append('state', state);
    const res = await fetch(`${BASE_URL}/api/notifications/outbox?${query.toString()}`);
    return handleResponse<import('../types').NotificationOutboxItem[]>(res);
  },

  async getActivity(
    limit: number = 50,
    eventType?: string,
    monitorId?: string
  ): Promise<{ items: import('../types').ActivityItem[]; total: number }> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (eventType && eventType !== 'all') query.append('event_type', eventType);
    if (monitorId) query.append('monitor_id', monitorId);
    const res = await fetch(`${BASE_URL}/api/activity?${query.toString()}`);
    return handleResponse<{ items: import('../types').ActivityItem[]; total: number }>(res);
  },
};


