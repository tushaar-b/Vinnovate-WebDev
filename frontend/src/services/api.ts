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
};


