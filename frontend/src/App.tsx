import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Layers, 
  CheckCircle2, 
  AlertCircle, 
  Plus, 
  Search, 
  RefreshCw, 
  Globe, 
  Database, 
  Server, 
  Settings as SettingsIcon,
  ChevronRight,
  ArrowUpRight,
  Lock,
  LogOut,
  Key,
} from 'lucide-react';
import { HealthStatus, MonitorSummary, CreateMonitorInput } from './types';
import { api, getAuthToken } from './services/api';
import { AddMonitorModal } from './components/AddMonitorModal';
import { MonitorDetails } from './components/MonitorDetails';
import { ActivityView } from './components/ActivityView';
import { SettingsView } from './components/SettingsView';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'monitors' | 'activity' | 'settings'>('dashboard');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [monitors, setMonitors] = useState<MonitorSummary[]>([]);
  const [monitorsLoading, setMonitorsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Authentication State
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => !!getAuthToken());
  const [authChecking, setAuthChecking] = useState<boolean>(true);
  const [loginPassword, setLoginPassword] = useState<string>('');
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginLoading, setLoginLoading] = useState<boolean>(false);
  
  // Navigation & Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [selectedMonitorId, setSelectedMonitorId] = useState<string | null>(null);
  const [monitorInitialTab, setMonitorInitialTab] = useState<'overview' | 'compare' | 'rules'>('overview');
  const [checkingIds, setCheckingIds] = useState<Record<string, boolean>>({});

  const fetchHealthData = async () => {
    try {
      setHealthLoading(true);
      const data = await api.getHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  };

  const fetchMonitorsData = async () => {
    if (!isAuthenticated && !getAuthToken()) {
      setMonitorsLoading(false);
      return;
    }
    try {
      setMonitorsLoading(true);
      const res = await api.getMonitors();
      setMonitors(res.items);
    } catch {
      // silently handle
    } finally {
      setMonitorsLoading(false);
    }
  };

  useEffect(() => {
    // Initial health check
    fetchHealthData();

    // Check auth status with backend
    const checkAuth = async () => {
      setAuthChecking(true);
      try {
        const res = await api.getAuthStatus();
        setIsAuthenticated(res.authenticated);
        if (res.authenticated) {
          fetchMonitorsData();
        }
      } catch {
        setIsAuthenticated(false);
      } finally {
        setAuthChecking(false);
      }
    };

    checkAuth();

    const handleUnauthorized = () => {
      setIsAuthenticated(false);
      setLoginError('Your session has expired. Please sign in with your administrative password.');
    };

    const handleLogout = () => {
      setIsAuthenticated(false);
      setLoginPassword('');
      setLoginError(null);
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    window.addEventListener('auth:logout', handleLogout);

    const healthInterval = setInterval(fetchHealthData, 15000);
    const monitorInterval = setInterval(() => {
      if (isAuthenticated) {
        fetchMonitorsData();
      }
    }, 10000);

    const parseHash = () => {
      const hash = window.location.hash;
      const match = hash.match(/^#monitors\/([0-9a-fA-F-]+)/);
      if (match) {
        setSelectedMonitorId(match[1]);
      } else if (hash === '#activity') {
        setSelectedMonitorId(null);
        setActiveTab('activity');
      } else if (hash === '#settings') {
        setSelectedMonitorId(null);
        setActiveTab('settings');
      } else if (hash === '#monitors') {
        setSelectedMonitorId(null);
        setActiveTab('monitors');
      } else if (!hash || hash === '#' || hash === '#dashboard') {
        setSelectedMonitorId(null);
        setActiveTab('dashboard');
      }
    };

    parseHash();
    window.addEventListener('hashchange', parseHash);

    return () => {
      clearInterval(healthInterval);
      clearInterval(monitorInterval);
      window.removeEventListener('hashchange', parseHash);
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
      window.removeEventListener('auth:logout', handleLogout);
    };
  }, [isAuthenticated]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginLoading(true);
    setLoginError(null);
    try {
      await api.login(loginPassword);
      setIsAuthenticated(true);
      fetchHealthData();
      fetchMonitorsData();
    } catch (err: any) {
      setLoginError(err.message || 'Authentication failed. Please verify password.');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogoutClick = async () => {
    await api.logout();
    setIsAuthenticated(false);
    setLoginPassword('');
    setLoginError(null);
  };

  const handleSelectMonitor = (id: string | null, tab: 'overview' | 'compare' | 'rules' = 'overview') => {
    setSelectedMonitorId(id);
    setMonitorInitialTab(tab);
    if (id) {
      window.location.hash = `#monitors/${id}`;
    } else {
      window.location.hash = activeTab === 'dashboard' ? '' : `#${activeTab}`;
    }
  };

  const handleCreateMonitor = async (input: CreateMonitorInput) => {
    const created = await api.createMonitor(input);
    await fetchMonitorsData();
    handleSelectMonitor(created.id);
  };

  const handleCheckNow = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setCheckingIds((prev) => ({ ...prev, [id]: true }));
    try {
      const res = await api.queueCheck(id);
      // Poll until check run is complete
      const poll = setInterval(async () => {
        try {
          const run = await api.getCheck(res.check_run_id);
          if (run.state !== 'queued' && run.state !== 'running') {
            clearInterval(poll);
            setCheckingIds((prev) => ({ ...prev, [id]: false }));
            fetchMonitorsData();
          }
        } catch {
          clearInterval(poll);
          setCheckingIds((prev) => ({ ...prev, [id]: false }));
        }
      }, 1000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to trigger check run');
      setCheckingIds((prev) => ({ ...prev, [id]: false }));
    }
  };

  // Metrics calculation from real monitors
  const totalMonitors = monitors.length;
  const healthyMonitors = monitors.filter((m) => m.status === 'ok' || m.status === 'changed').length;
  const changedMonitors = monitors.filter((m) => m.status === 'changed').length;
  const errorMonitors = monitors.filter((m) => m.status === 'error' || m.status === 'blocked').length;

  // Filtering
  const filteredMonitors = monitors.filter((m) => {
    const matchesSearch =
      m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.url.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === 'all' || m.status.toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesStatus;
  });

  // Session Checking State (prevents mounting protected components prematurely)
  if (authChecking) {
    return (
      <div className="min-h-screen bg-[#F8FAFC] flex flex-col justify-center items-center p-4 text-[#64748B]">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mb-3" />
        <p className="text-sm font-medium">Verifying administrative session...</p>
      </div>
    );
  }

  // Unauthenticated Lock Screen
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#F8FAFC] flex flex-col justify-center items-center p-4">
        <div className="max-w-md w-full bg-white border border-[#E2E8F0] rounded-2xl shadow-xl p-8">
          <div className="flex flex-col items-center text-center mb-6">
            <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center mb-3 shadow-inner">
              <Lock className="w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold text-[#0F172A]">Website Change Detector</h1>
            <p className="text-xs text-[#64748B] mt-1">
              Production Access Protection &bull; Enter administrative password to access system
            </p>
          </div>

          {loginError && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{loginError}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[#475569] mb-1">
                Admin Password
              </label>
              <input
                type="password"
                placeholder="Enter admin password..."
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                className="w-full text-sm px-3.5 py-2.5 bg-white border border-[#CBD5E1] rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                autoFocus
                required
              />
            </div>

            <button
              type="submit"
              disabled={loginLoading || !loginPassword.trim()}
              className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium text-sm rounded-lg shadow-sm transition-all flex items-center justify-center space-x-2"
            >
              {loginLoading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <Key className="w-4 h-4" />
                  <span>Unlock System</span>
                </>
              )}
            </button>
          </form>

          {/* System Health footer on lock screen */}
          <div className="mt-8 pt-4 border-t border-[#F1F5F9] flex items-center justify-between text-[11px] text-[#94A3B8]">
            <span>Access: Protected</span>
            <span className="flex items-center space-x-1.5">
              <span className={`w-2 h-2 rounded-full ${health?.status === 'ok' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              <span>API {health?.status === 'ok' ? 'Online' : 'Checking'}</span>
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#0F172A] flex flex-col font-sans">
      {/* Top Navigation */}
      <header className="bg-white border-b border-[#E2E8F0] sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-8">
            <div 
              onClick={() => handleSelectMonitor(null)}
              className="flex items-center space-x-3 cursor-pointer"
            >
              <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-sm">
                <Globe className="w-5 h-5" />
              </div>
              <div className="flex flex-col">
                <span className="font-semibold text-base leading-none text-[#0F172A]">Website Change Detector</span>
                <span className="text-[11px] text-[#64748B] mt-0.5 font-medium tracking-wide">PRECISION OBSERVABILITY</span>
              </div>
            </div>

            <nav className="hidden md:flex space-x-1">
              {[
                { id: 'dashboard', label: 'Dashboard', icon: Layers },
                { id: 'monitors', label: 'Monitors', icon: Globe },
                { id: 'activity', label: 'Activity', icon: Activity },
                { id: 'settings', label: 'Settings', icon: SettingsIcon },
              ].map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id && !selectedMonitorId;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      handleSelectMonitor(null);
                      setActiveTab(item.id as typeof activeTab);
                      window.location.hash = item.id === 'dashboard' ? '' : `#${item.id}`;
                    }}
                    className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive 
                        ? 'bg-blue-50 text-blue-600' 
                        : 'text-[#64748B] hover:text-[#0F172A] hover:bg-slate-50'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </nav>
          </div>

          {/* System Health Indicators & Action Buttons */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 text-xs bg-slate-50 border border-[#E2E8F0] px-3 py-1.5 rounded-full">
              <div className="flex items-center space-x-1">
                <Server className="w-3.5 h-3.5 text-[#64748B]" />
                <span className="text-[#64748B]">API:</span>
                <span className={health?.status === 'ok' ? 'text-green-600 font-medium' : 'text-amber-600 font-medium'}>
                  {healthLoading ? '...' : health?.status === 'ok' ? 'ONLINE' : 'OFFLINE'}
                </span>
              </div>

              <span className="text-[#CBD5E1]">|</span>

              <div className="flex items-center space-x-1">
                <Database className="w-3.5 h-3.5 text-[#64748B]" />
                <span className="text-[#64748B]">DB:</span>
                <span className={health?.database === 'ok' ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
                  {health?.database === 'ok' ? 'OK' : 'ERR'}
                </span>
              </div>

              <span className="text-[#CBD5E1]">|</span>

              <div className="flex items-center space-x-1">
                <RefreshCw className={`w-3.5 h-3.5 ${healthLoading ? 'animate-spin text-blue-600' : 'text-[#64748B]'}`} />
                <span className="text-[#64748B]">Redis:</span>
                <span className={health?.redis === 'ok' ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
                  {health?.redis === 'ok' ? 'OK' : 'ERR'}
                </span>
              </div>
            </div>

            <button
              onClick={() => setIsAddModalOpen(true)}
              className="inline-flex items-center space-x-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-3.5 py-1.5 rounded-lg shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <Plus className="w-4 h-4" />
              <span>Add Monitor</span>
            </button>

            <button
              onClick={handleLogoutClick}
              title="Sign out of administrative session"
              className="inline-flex items-center space-x-1 border border-[#E2E8F0] hover:bg-slate-50 text-[#64748B] hover:text-[#0F172A] text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {selectedMonitorId ? (
          <MonitorDetails
            monitorId={selectedMonitorId}
            initialTab={monitorInitialTab}
            onBack={() => {
              handleSelectMonitor(null);
              fetchMonitorsData();
            }}
            onDeleted={() => {
              handleSelectMonitor(null);
              fetchMonitorsData();
            }}
          />
        ) : activeTab === 'activity' ? (
          <ActivityView
            onNavigateToMonitor={(id, tab) => handleSelectMonitor(id, (tab as any) || 'overview')}
          />
        ) : activeTab === 'settings' ? (
          <SettingsView />
        ) : (
          <>
            {/* Header & Status */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-6 border-b border-[#E2E8F0]">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight text-[#0F172A]">Website Change Detector</h1>
                <p className="text-sm text-[#64748B] mt-1">
                  Autonomous, high-precision web content diffing & change detection engine.
                </p>
              </div>
              <div className="mt-4 sm:mt-0 flex items-center space-x-2">
                <button
                  onClick={() => {
                    fetchHealthData();
                    fetchMonitorsData();
                  }}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 border border-[#E2E8F0] rounded-lg text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-white transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${monitorsLoading ? 'animate-spin' : ''}`} />
                  <span>Refresh Monitors</span>
                </button>
              </div>
            </div>

            {/* Metric Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
              <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-[#64748B]">
                  <span className="text-xs font-medium uppercase tracking-wider">Total Monitors</span>
                  <Layers className="w-4 h-4 text-blue-600" />
                </div>
                <div className="mt-2 flex items-baseline space-x-2">
                  <span className="text-2xl font-semibold text-[#0F172A]">{totalMonitors}</span>
                  <span className="text-xs text-[#64748B]">monitored targets</span>
                </div>
                <p className="text-xs text-[#64748B] mt-2">Active observation configurations</p>
              </div>

              <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-[#64748B]">
                  <span className="text-xs font-medium uppercase tracking-wider">Healthy</span>
                  <CheckCircle2 className="w-4 h-4 text-[#16A34A]" />
                </div>
                <div className="mt-2 flex items-baseline space-x-2">
                  <span className="text-2xl font-semibold text-[#0F172A]">{healthyMonitors}</span>
                  <span className="text-xs text-[#16A34A] font-medium">operational</span>
                </div>
                <p className="text-xs text-[#64748B] mt-2">Successful captures without outages</p>
              </div>

              <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-[#64748B]">
                  <span className="text-xs font-medium uppercase tracking-wider">Changed (24h)</span>
                  <Activity className="w-4 h-4 text-blue-600" />
                </div>
                <div className="mt-2 flex items-baseline space-x-2">
                  <span className="text-2xl font-semibold text-[#0F172A]">{changedMonitors}</span>
                  <span className="text-xs text-[#64748B]">confirmed diffs</span>
                </div>
                <p className="text-xs text-[#64748B] mt-2">Content changes detected</p>
              </div>

              <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-[#64748B]">
                  <span className="text-xs font-medium uppercase tracking-wider">Errors / Blocked</span>
                  <AlertCircle className="w-4 h-4 text-[#D97706]" />
                </div>
                <div className="mt-2 flex items-baseline space-x-2">
                  <span className="text-2xl font-semibold text-[#0F172A]">{errorMonitors}</span>
                  <span className="text-xs text-[#64748B]">outages / challenges</span>
                </div>
                <p className="text-xs text-[#64748B] mt-2">Never counted as content diffs</p>
              </div>
            </div>

            {/* Monitors Table Container */}
            <div className="mt-6 bg-white border border-[#E2E8F0] rounded-xl shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-[#E2E8F0] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="relative flex-1 max-w-sm">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B]" />
                  <input
                    type="text"
                    placeholder="Search monitors..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-[#E2E8F0] rounded-lg text-[#0F172A] placeholder-[#64748B] focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs text-[#64748B]">Filter:</span>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="text-xs bg-slate-50 border border-[#E2E8F0] text-[#0F172A] px-2.5 py-1 rounded-md font-medium focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="all">All Monitors ({monitors.length})</option>
                    <option value="ok">Healthy (OK)</option>
                    <option value="changed">Changed</option>
                    <option value="pending">Pending</option>
                    <option value="error">Error</option>
                    <option value="blocked">Blocked</option>
                  </select>
                </div>
              </div>

              {filteredMonitors.length === 0 ? (
                <div className="p-12 text-center flex flex-col items-center justify-center">
                  <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mb-4">
                    <Globe className="w-6 h-6" />
                  </div>
                  <h3 className="text-base font-semibold text-[#0F172A]">
                    {monitors.length === 0 ? 'No monitors configured yet' : 'No matching monitors found'}
                  </h3>
                  <p className="text-xs text-[#64748B] max-w-md mt-1 mb-6 leading-relaxed">
                    {monitors.length === 0
                      ? 'Add a public URL or load the built-in local test fixture to start tracking web changes with Playwright screenshots and normalized content diffing.'
                      : 'Try adjusting your search query or status filter.'}
                  </p>
                  {monitors.length === 0 && (
                    <button
                      onClick={() => setIsAddModalOpen(true)}
                      className="inline-flex items-center space-x-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm transition-all"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Create First Monitor</span>
                    </button>
                  )}
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 border-b border-[#E2E8F0] text-[#64748B] uppercase font-semibold text-[11px] tracking-wider">
                      <tr>
                        <th className="px-6 py-3">Monitor</th>
                        <th className="px-6 py-3">Status</th>
                        <th className="px-6 py-3">Interval</th>
                        <th className="px-6 py-3">Last Checked</th>
                        <th className="px-6 py-3">Next Scheduled</th>
                        <th className="px-6 py-3">Versions</th>
                        <th className="px-6 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E2E8F0]">
                      {filteredMonitors.map((m) => {
                        const isChecking = checkingIds[m.id];
                        return (
                          <tr
                            key={m.id}
                            onClick={() => handleSelectMonitor(m.id)}
                            className="hover:bg-slate-50/80 cursor-pointer transition-colors"
                          >
                            <td className="px-6 py-4">
                              <div className="flex flex-col">
                                <span className="font-semibold text-sm text-[#0F172A] hover:text-blue-600 transition-colors">
                                  {m.name}
                                </span>
                                <span className="text-xs text-[#64748B] truncate max-w-xs mt-0.5">
                                  {m.url}
                                </span>
                              </div>
                            </td>

                            <td className="px-6 py-4">
                              <span
                                className={`text-[11px] font-semibold uppercase px-2.5 py-0.5 rounded-full border ${
                                  m.status === 'ok'
                                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                    : m.status === 'changed'
                                    ? 'bg-blue-50 text-blue-700 border-blue-200'
                                    : m.status === 'blocked'
                                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                                    : m.status === 'error'
                                    ? 'bg-rose-50 text-rose-700 border-rose-200'
                                    : 'bg-slate-100 text-slate-700 border-slate-200'
                                }`}
                              >
                                {m.status}
                              </span>
                            </td>

                            <td className="px-6 py-4 text-[#64748B]">
                              Every {m.interval_minutes}m
                            </td>

                            <td className="px-6 py-4 text-[#64748B]">
                              {m.last_checked_at
                                ? new Date(m.last_checked_at).toLocaleTimeString()
                                : 'Pending'}
                            </td>

                            <td className="px-6 py-4 text-[#64748B]">
                              {m.next_check_at
                                ? new Date(m.next_check_at).toLocaleTimeString()
                                : '---'}
                            </td>

                            <td className="px-6 py-4 text-[#0F172A] font-medium">
                              {m.versions_count} snapshot{m.versions_count === 1 ? '' : 's'}
                            </td>

                            <td className="px-6 py-4 text-right">
                              <div className="flex items-center justify-end space-x-2">
                                <button
                                  onClick={(e) => handleCheckNow(m.id, e)}
                                  disabled={isChecking}
                                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-[#E2E8F0] hover:bg-white text-xs font-medium text-[#0F172A] shadow-sm transition-colors"
                                >
                                  <RefreshCw
                                    className={`w-3.5 h-3.5 ${isChecking ? 'animate-spin text-blue-600' : 'text-[#64748B]'}`}
                                  />
                                  <span>{isChecking ? 'Checking...' : 'Check Now'}</span>
                                </button>
                                <ChevronRight className="w-4 h-4 text-[#94A3B8]" />
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Architectural Footnote */}
            <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-[#64748B]">
              <div className="border border-[#E2E8F0] bg-white rounded-lg p-3.5">
                <div className="font-semibold text-[#0F172A] mb-1 flex items-center justify-between">
                  <span>SSRF Defenses Active</span>
                  <ArrowUpRight className="w-3.5 h-3.5 text-[#64748B]" />
                </div>
                <p>DNS resolution verification, private CIDR blocking, subresource request interception.</p>
              </div>
              <div className="border border-[#E2E8F0] bg-white rounded-lg p-3.5">
                <div className="font-semibold text-[#0F172A] mb-1 flex items-center justify-between">
                  <span>Playwright Capture Engine</span>
                  <ArrowUpRight className="w-3.5 h-3.5 text-[#64748B]" />
                </div>
                <p>Headless Chromium renders full DOM, captures consistent 1440x900 viewport screenshots.</p>
              </div>
              <div className="border border-[#E2E8F0] bg-white rounded-lg p-3.5">
                <div className="font-semibold text-[#0F172A] mb-1 flex items-center justify-between">
                  <span>Precision Normalized Diff</span>
                  <ArrowUpRight className="w-3.5 h-3.5 text-[#64748B]" />
                </div>
                <p>SHA-256 content hashing with whitespace normalization to eliminate cosmetic false positives.</p>
              </div>
            </div>
          </>
        )}
      </main>

      {/* Add Monitor Modal */}
      <AddMonitorModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSubmit={handleCreateMonitor}
      />
    </div>
  );
};

export default App;
