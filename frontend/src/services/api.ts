import {
  HealthStatus,
  MonitorSummary,
  MonitorDetail,
  CheckRun,
  VersionSummary,
  VersionDetail,
  CreateMonitorInput,
} from '../types';

// Set VITE_API_URL to the HTTPS API origin at build time in hosted environments.
const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

let authToken: string = (() => {
  try {
    return localStorage.getItem('change_detector_token') || '';
  } catch {
    return '';
  }
})();

export function setAuthToken(token: string) {
  authToken = token;
  try {
    if (token) {
      localStorage.setItem('change_detector_token', token);
    } else {
      localStorage.removeItem('change_detector_token');
    }
  } catch {
    // ignore storage exceptions
  }
}

export function getAuthToken(): string {
  return authToken;
}

export function clearAuthToken() {
  setAuthToken('');
}

export function attachAuthToMediaUrl(url: string): string {
  if (!url) return '';

  // If the media URL is a relative path, resolve it against the configured backend origin (VITE_API_URL)
  // so requests target the Railway backend rather than resolving to the Vercel frontend origin.
  let fullUrl = url;
  if (!fullUrl.startsWith('http://') && !fullUrl.startsWith('https://')) {
    if (BASE_URL) {
      const normalizedPath = fullUrl.startsWith('/') ? fullUrl : `/${fullUrl}`;
      fullUrl = `${BASE_URL}${normalizedPath}`;
    }
  }

  if (!authToken) return fullUrl;

  try {
    const origin = typeof window !== 'undefined' && window.location?.origin ? window.location.origin : 'http://localhost';
    const parsed = new URL(fullUrl, origin);
    if (!parsed.searchParams.has('token') && !parsed.searchParams.has('auth_token')) {
      parsed.searchParams.set('token', authToken);
    }
    return fullUrl.startsWith('http://') || fullUrl.startsWith('https://')
      ? parsed.toString()
      : `${parsed.pathname}${parsed.search}`;
  } catch {
    const separator = fullUrl.includes('?') ? '&' : '?';
    return `${fullUrl}${separator}token=${encodeURIComponent(authToken)}`;
  }
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers || {});
  if (authToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${authToken}`);
  }
  return fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    clearAuthToken();
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    }
    throw new Error('Authentication required or session expired.');
  }

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
  // Authentication Endpoints
  async login(password: string): Promise<{ token: string; expires_at: number; user: string }> {
    const res = await fetch(`${BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    const data = await handleResponse<{ token: string; expires_at: number; user: string }>(res);
    setAuthToken(data.token);
    return data;
  },

  async logout(): Promise<void> {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    } catch {
      // ignore
    } finally {
      clearAuthToken();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('auth:logout'));
      }
    }
  },

  async getAuthStatus(): Promise<{ authenticated: boolean; user?: string }> {
    try {
      const res = await apiFetch('/api/auth/status');
      return await handleResponse<{ authenticated: boolean; user?: string }>(res);
    } catch {
      return { authenticated: false };
    }
  },

  async getHealth(): Promise<HealthStatus> {
    const res = await apiFetch('/api/health');
    return handleResponse<HealthStatus>(res);
  },

  async getMonitors(): Promise<{ items: MonitorSummary[]; total: number }> {
    const res = await apiFetch('/api/monitors');
    return handleResponse<{ items: MonitorSummary[]; total: number }>(res);
  },

  async createMonitor(input: CreateMonitorInput): Promise<MonitorDetail> {
    const res = await apiFetch('/api/monitors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    return handleResponse<MonitorDetail>(res);
  },

  async getMonitor(id: string): Promise<MonitorDetail> {
    const res = await apiFetch(`/api/monitors/${id}`);
    return handleResponse<MonitorDetail>(res);
  },

  async deleteMonitor(id: string): Promise<void> {
    const res = await apiFetch(`/api/monitors/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok && res.status !== 204) {
      throw new Error(`Failed to delete monitor (HTTP ${res.status})`);
    }
  },

  async queueCheck(id: string): Promise<{ check_run_id: string; job_id: string; state: string }> {
    const res = await apiFetch(`/api/monitors/${id}/checks`, {
      method: 'POST',
    });
    return handleResponse<{ check_run_id: string; job_id: string; state: string }>(res);
  },

  async getChecks(monitorId: string): Promise<{ items: CheckRun[] }> {
    const res = await apiFetch(`/api/monitors/${monitorId}/checks?limit=50`);
    return handleResponse<{ items: CheckRun[] }>(res);
  },

  async getCheck(checkId: string): Promise<CheckRun> {
    const res = await apiFetch(`/api/checks/${checkId}`);
    return handleResponse<CheckRun>(res);
  },

  async getVersions(monitorId: string): Promise<{ items: VersionSummary[] }> {
    const res = await apiFetch(`/api/monitors/${monitorId}/versions`);
    const data = await handleResponse<{ items: VersionSummary[] }>(res);
    data.items = data.items.map(v => ({
      ...v,
      screenshot_url: attachAuthToMediaUrl(v.screenshot_url),
    }));
    return data;
  },

  async getVersion(monitorId: string, versionId: string): Promise<VersionDetail> {
    const res = await apiFetch(`/api/monitors/${monitorId}/versions/${versionId}`);
    const data = await handleResponse<VersionDetail>(res);
    if (data.screenshot_url) {
      data.screenshot_url = attachAuthToMediaUrl(data.screenshot_url);
    }
    return data;
  },

  async compareVersions(monitorId: string, fromId: string, toId: string) {
    const res = await apiFetch(`/api/monitors/${monitorId}/compare?from=${fromId}&to=${toId}`);
    const data = await handleResponse<import('../types').VersionComparison>(res);
    if (data.image_old_url) {
      data.image_old_url = attachAuthToMediaUrl(data.image_old_url);
    }
    if (data.image_new_url) {
      data.image_new_url = attachAuthToMediaUrl(data.image_new_url);
    }
    if (data.image_diff_url) {
      data.image_diff_url = attachAuthToMediaUrl(data.image_diff_url);
    }
    if (data.old_version?.screenshot_url) {
      data.old_version.screenshot_url = attachAuthToMediaUrl(data.old_version.screenshot_url);
    }
    if (data.new_version?.screenshot_url) {
      data.new_version.screenshot_url = attachAuthToMediaUrl(data.new_version.screenshot_url);
    }
    return data;
  },

  async getPicker(monitorId: string): Promise<import('../types').PickerData> {
    const res = await apiFetch(`/api/monitors/${monitorId}/picker`);
    const data = await handleResponse<import('../types').PickerData>(res);
    if (data.screenshot_url) {
      data.screenshot_url = attachAuthToMediaUrl(data.screenshot_url);
    }
    return data;
  },

  async updateRules(
    monitorId: string,
    rules: { rule_type: 'watch' | 'ignore'; css_selector: string; label?: string }[]
  ): Promise<import('../types').MonitorRule[]> {
    const res = await apiFetch(`/api/monitors/${monitorId}/rules`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules }),
    });
    return handleResponse<import('../types').MonitorRule[]>(res);
  },

  async getNotificationSettings(): Promise<Record<string, import('../types').NotificationChannel>> {
    const res = await apiFetch('/api/settings/notifications');
    return handleResponse<Record<string, import('../types').NotificationChannel>>(res);
  },

  async updateNotificationSettings(
    channelType: string,
    payload: { enabled: boolean; configuration: Record<string, any> }
  ): Promise<import('../types').NotificationChannel> {
    const res = await apiFetch(`/api/settings/notifications/${channelType}`, {
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
    const res = await apiFetch(`/api/settings/notifications/${channelType}/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ configuration }),
    });
    return handleResponse<{ success: boolean; message: string; channel_type: string }>(res);
  },

  async getNotificationOutbox(limit: number = 50, state?: string): Promise<import('../types').NotificationOutboxItem[]> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (state && state !== 'all') query.append('state', state);
    const res = await apiFetch(`/api/notifications/outbox?${query.toString()}`);
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
    const res = await apiFetch(`/api/activity?${query.toString()}`);
    return handleResponse<{ items: import('../types').ActivityItem[]; total: number }>(res);
  },
};
