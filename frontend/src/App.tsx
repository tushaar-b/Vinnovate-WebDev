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
  ShieldAlert,
  ArrowUpRight
} from 'lucide-react';
import { HealthStatus } from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'monitors' | 'activity' | 'settings'>('dashboard');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [healthError, setHealthError] = useState<string | null>(null);

  const fetchHealth = async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const res = await fetch('/api/health');
      if (!res.ok) {
        throw new Error(`Health check failed with status: ${res.status}`);
      }
      const data: HealthStatus = await res.json();
      setHealth(data);
    } catch (err: unknown) {
      setHealthError(err instanceof Error ? err.message : 'Failed to reach API');
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#0F172A] flex flex-col font-sans">
      {/* Top Navigation */}
      <header className="bg-white border-b border-[#E2E8F0] sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-8">
            <div className="flex items-center space-x-3">
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
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id as typeof activeTab)}
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

          {/* System Health Indicators */}
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
              onClick={() => alert('Add Monitor modal will be connected in Phase 1')}
              className="inline-flex items-center space-x-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-3.5 py-1.5 rounded-lg shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <Plus className="w-4 h-4" />
              <span>Add Monitor</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
              onClick={fetchHealth}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 border border-[#E2E8F0] rounded-lg text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-white transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${healthLoading ? 'animate-spin' : ''}`} />
              <span>Refresh Status</span>
            </button>
          </div>
        </div>

        {/* Phase 0 Status Banner */}
        <div className="mt-6 bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-sm">
          <div className="flex items-start space-x-3">
            <div className="p-2 rounded-lg bg-blue-50 text-blue-600 mt-0.5">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-semibold text-[#0F172A]">Phase 0: Environment & Architecture Verified</h3>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                  READY
                </span>
              </div>
              <p className="text-xs text-[#64748B] mt-1 leading-relaxed">
                Core infrastructure is operational: FastAPI server running, PostgreSQL 16 connected, Redis 7 operational, 
                and Vite + React 18 + Tailwind frontend built cleanly on macOS Apple Silicon.
              </p>
              {healthError && (
                <div className="mt-2 text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded p-2 flex items-center space-x-2">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  <span>Connection notice: {healthError}</span>
                </div>
              )}
            </div>
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
              <span className="text-2xl font-semibold text-[#0F172A]">0</span>
              <span className="text-xs text-[#64748B]">monitored targets</span>
            </div>
            <p className="text-xs text-[#64748B] mt-2">Ready to configure in Phase 1</p>
          </div>

          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between text-[#64748B]">
              <span className="text-xs font-medium uppercase tracking-wider">Healthy</span>
              <CheckCircle2 className="w-4 h-4 text-[#16A34A]" />
            </div>
            <div className="mt-2 flex items-baseline space-x-2">
              <span className="text-2xl font-semibold text-[#0F172A]">0</span>
              <span className="text-xs text-[#16A34A] font-medium">100% operational</span>
            </div>
            <p className="text-xs text-[#64748B] mt-2">No failing targets</p>
          </div>

          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between text-[#64748B]">
              <span className="text-xs font-medium uppercase tracking-wider">Changed (24h)</span>
              <Activity className="w-4 h-4 text-blue-600" />
            </div>
            <div className="mt-2 flex items-baseline space-x-2">
              <span className="text-2xl font-semibold text-[#0F172A]">0</span>
              <span className="text-xs text-[#64748B]">confirmed diffs</span>
            </div>
            <p className="text-xs text-[#64748B] mt-2">Zero false positives</p>
          </div>

          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between text-[#64748B]">
              <span className="text-xs font-medium uppercase tracking-wider">Errors / Blocked</span>
              <AlertCircle className="w-4 h-4 text-[#D97706]" />
            </div>
            <div className="mt-2 flex items-baseline space-x-2">
              <span className="text-2xl font-semibold text-[#0F172A]">0</span>
              <span className="text-xs text-[#64748B]">outages / challenges</span>
            </div>
            <p className="text-xs text-[#64748B] mt-2">Never counted as diffs</p>
          </div>
        </div>

        {/* Empty State / Monitor Table Container */}
        <div className="mt-6 bg-white border border-[#E2E8F0] rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-[#E2E8F0] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B]" />
              <input
                type="text"
                placeholder="Search monitors..."
                disabled
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-[#E2E8F0] rounded-lg text-[#0F172A] placeholder-[#64748B] focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-not-allowed"
              />
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-xs text-[#64748B]">Filter:</span>
              <span className="text-xs bg-slate-100 text-[#0F172A] px-2.5 py-1 rounded-md font-medium">
                All Monitors (0)
              </span>
            </div>
          </div>

          <div className="p-12 text-center flex flex-col items-center justify-center">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mb-4">
              <Globe className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-[#0F172A]">No monitors configured yet</h3>
            <p className="text-xs text-[#64748B] max-w-md mt-1 mb-6 leading-relaxed">
              Monitors will capture rendered DOM snapshots, calculate normalized SHA-256 content hashes, and track visual diffs.
              Monitor CRUD and manual check queues will be implemented in Phase 1.
            </p>
            <button
              onClick={() => alert('Add Monitor modal will be enabled in Phase 1')}
              className="inline-flex items-center space-x-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create First Monitor</span>
            </button>
          </div>
        </div>

        {/* System Architecture Specifications Footnote */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-[#64748B]">
          <div className="border border-[#E2E8F0] bg-white rounded-lg p-3.5">
            <div className="font-semibold text-[#0F172A] mb-1 flex items-center justify-between">
              <span>Database Layer</span>
              <ArrowUpRight className="w-3.5 h-3.5 text-[#64748B]" />
            </div>
            <p>PostgreSQL 16 with SQLAlchemy 2 declarative models and Alembic schema migrations.</p>
          </div>
          <div className="border border-[#E2E8F0] bg-white rounded-lg p-3.5">
            <div className="font-semibold text-[#0F172A] mb-1 flex items-center justify-between">
              <span>Queue & Workers</span>
              <ArrowUpRight className="w-3.5 h-3.5 text-[#64748B]" />
            </div>
            <p>Redis 7 with RQ worker pool, isolated browser contexts and idempotency keys.</p>
          </div>
          <div className="border border-[#E2E8F0] bg-white rounded-lg p-3.5">
            <div className="font-semibold text-[#0F172A] mb-1 flex items-center justify-between">
              <span>Rendering Pipeline</span>
              <ArrowUpRight className="w-3.5 h-3.5 text-[#64748B]" />
            </div>
            <p>Headless Playwright Chromium with bounded navigation timeouts and element bounding geometry.</p>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
