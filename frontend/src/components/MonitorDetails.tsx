import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  ExternalLink,
  RefreshCw,
  Trash2,
  FileText,
  Image as ImageIcon,
  ShieldAlert,
  Hash,
  Terminal,
  Layers,
  GitCompare,
  Crosshair,
  AlertCircle,
} from 'lucide-react';
import { MonitorDetail, CheckRun, VersionSummary } from '../types';
import { api, attachAuthToMediaUrl } from '../services/api';
import { VersionCompare } from './VersionCompare';
import { RegionPicker } from './RegionPicker';
import { ConfirmModal } from './ConfirmModal';




interface MonitorDetailsProps {
  monitorId: string;
  initialTab?: 'overview' | 'compare' | 'rules';
  onBack: () => void;
  onDeleted: () => void;
}

export const MonitorDetails: React.FC<MonitorDetailsProps> = ({
  monitorId,
  initialTab = 'overview',
  onBack,
  onDeleted,
}) => {
  const [monitor, setMonitor] = useState<MonitorDetail | null>(null);
  const [checks, setChecks] = useState<CheckRun[]>([]);
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<VersionSummary | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'compare' | 'rules'>(initialTab);
  const [compareFromId, setCompareFromId] = useState<string>('');
  const [compareToId, setCompareToId] = useState<string>('');
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [imageRetryCount, setImageRetryCount] = useState(0);

  const loadData = async () => {
    try {
      const [m, c, v] = await Promise.all([
        api.getMonitor(monitorId),
        api.getChecks(monitorId),
        api.getVersions(monitorId),
      ]);
      setMonitor(m);
      setChecks(c.items);
      setVersions(v.items);
      setSelectedVersion((prev) => {
        if (!prev || prev.monitor_id !== monitorId) {
          return v.items.length > 0 ? v.items[0] : null;
        }
        const matched = v.items.find((item) => item.id === prev.id);
        return matched || prev;
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load monitor details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setSelectedVersion(null);
    setImageError(false);
    setImageRetryCount(0);
    loadData();
    const pollTimer = setInterval(() => {
      loadData();
    }, 5000);
    return () => clearInterval(pollTimer);
  }, [monitorId]);

  const latestVersion = versions.length > 0 ? versions[0] : null;
  const displayVersion = selectedVersion || latestVersion;
  const activeCheck = checks.find((c) => c.state === 'queued' || c.state === 'running');
  const isCheckingOrActive = checking || !!activeCheck;

  const rawScreenshotUrl = displayVersion?.screenshot_url || '';
  const resolvedScreenshotUrl = React.useMemo(() => {
    if (!rawScreenshotUrl) return '';
    let url = attachAuthToMediaUrl(rawScreenshotUrl);
    if (imageRetryCount > 0) {
      const sep = url.includes('?') ? '&' : '?';
      url = `${url}${sep}_retry=${imageRetryCount}`;
    }
    return url;
  }, [rawScreenshotUrl, imageRetryCount]);

  // Handle manual "Check Now"
  const handleCheckNow = async () => {
    setChecking(true);
    try {
      const res = await api.queueCheck(monitorId);
      // Poll until check run is finished
      const pollInterval = setInterval(async () => {
        try {
          const run = await api.getCheck(res.check_run_id);
          if (run.state !== 'queued' && run.state !== 'running') {
            clearInterval(pollInterval);
            setChecking(false);
            loadData();
          }
        } catch {
          clearInterval(pollInterval);
          setChecking(false);
        }
      }, 1000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to trigger check run');
      setChecking(false);
    }
  };

  const handleDelete = () => {
    setIsDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    setDeleteLoading(true);
    try {
      await api.deleteMonitor(monitorId);
      setIsDeleteModalOpen(false);
      onDeleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete monitor');
      setIsDeleteModalOpen(false);
    } finally {
      setDeleteLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-24 text-[#64748B]">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mb-3" />
        <p className="text-sm font-medium">Loading monitor details...</p>
      </div>
    );
  }

  if (error || !monitor) {
    return (
      <div className="p-8 max-w-xl mx-auto text-center">
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl mb-4 text-sm">
          {error || 'Monitor not found.'}
        </div>
        <button
          onClick={onBack}
          className="inline-flex items-center space-x-2 text-sm text-blue-600 hover:underline"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Dashboard</span>
        </button>
      </div>
    );
  }



  return (

    <div className="space-y-6">
      {/* Top Breadcrumb & Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#E2E8F0]">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-white border border-[#E2E8F0] shadow-sm transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2.5">
              <h1 className="text-xl font-bold text-[#0F172A]">{monitor.name}</h1>
              <span
                className={`text-[11px] font-semibold uppercase px-2.5 py-0.5 rounded-full border ${
                  monitor.status === 'ok'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : monitor.status === 'changed'
                    ? 'bg-blue-50 text-blue-700 border-blue-200'
                    : monitor.status === 'blocked'
                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                    : monitor.status === 'error'
                    ? 'bg-rose-50 text-rose-700 border-rose-200'
                    : 'bg-slate-100 text-slate-700 border-slate-200'
                }`}
              >
                {monitor.status}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[#64748B] mt-1">
              <a
                href={monitor.url}
                target="_blank"
                rel="noreferrer"
                className="hover:text-blue-600 flex items-center space-x-1"
              >
                <span>{monitor.url}</span>
                <ExternalLink className="w-3 h-3" />
              </a>
              <span>•</span>
              <span>Every {monitor.interval_minutes}m</span>
              <span>•</span>
              <span>Last Check: {monitor.last_checked_at ? new Date(monitor.last_checked_at).toLocaleTimeString() : 'Never'}</span>
              <span>•</span>
              <span>Next Check: {monitor.next_check_at ? new Date(monitor.next_check_at).toLocaleTimeString() : 'Pending'}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={handleCheckNow}
            disabled={isCheckingOrActive}
            className="inline-flex items-center space-x-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold px-3.5 py-2 rounded-lg shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isCheckingOrActive ? 'animate-spin' : ''}`} />
            <span>
              {activeCheck?.state === 'queued'
                ? 'Queued in Worker...'
                : isCheckingOrActive
                ? 'Running Check...'
                : 'Check Now'}
            </span>
          </button>

          <button
            onClick={handleDelete}
            className="inline-flex items-center space-x-1 text-xs font-medium text-rose-600 hover:text-rose-700 hover:bg-rose-50 px-3 py-2 rounded-lg border border-transparent hover:border-rose-200 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete</span>
          </button>
        </div>
      </div>

      {/* Live Queued or Running Worker Banner */}
      {activeCheck && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-3.5 flex items-center justify-between text-blue-900 text-xs shadow-sm">
          <div className="flex items-center space-x-2.5">
            <RefreshCw className="w-4 h-4 animate-spin text-blue-600" />
            <div>
              <span className="font-semibold">
                {activeCheck.state === 'queued'
                  ? 'Check is queued in worker job queue'
                  : 'Check is executing in Playwright worker...'}
              </span>
              <span className="ml-2 text-[11px] text-blue-700 font-mono">
                Run ID: {activeCheck.id.slice(0, 8)}
              </span>
            </div>
          </div>
          <span
            className={`px-2.5 py-0.5 rounded-full text-[10px] uppercase font-bold border ${
              activeCheck.state === 'queued'
                ? 'bg-amber-100 text-amber-800 border-amber-300'
                : 'bg-blue-100 text-blue-800 border-blue-300'
            }`}
          >
            {activeCheck.state}
          </span>
        </div>
      )}

      {/* Error or Blocked Banner */}
      {monitor.last_error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-start space-x-3 text-rose-800">
          <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5 text-rose-600" />
          <div className="text-xs">
            <span className="font-semibold">Recent Check Notice: </span>
            <span>{monitor.last_error}</span>
          </div>
        </div>
      )}

      {/* View Mode Navigation Tabs */}
      <div className="flex items-center space-x-2 border-b border-[#E2E8F0] pb-2">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex items-center space-x-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === 'overview'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-[#64748B] hover:text-[#0F172A] hover:bg-slate-100'
          }`}
        >
          <ImageIcon className="w-3.5 h-3.5" />
          <span>Snapshot Overview</span>
        </button>

        <button
          onClick={() => setActiveTab('compare')}
          className={`flex items-center space-x-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === 'compare'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-[#64748B] hover:text-[#0F172A] hover:bg-slate-100'
          }`}
        >
          <GitCompare className="w-3.5 h-3.5" />
          <span>Compare Versions ({versions.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('rules')}
          className={`flex items-center space-x-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === 'rules'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-[#64748B] hover:text-[#0F172A] hover:bg-slate-100'
          }`}
        >
          <Crosshair className="w-3.5 h-3.5" />
          <span>Region Rules & Picker ({monitor.rules?.length || 0})</span>
        </button>
      </div>

      {/* Main Content: Overview vs Compare vs Rules */}
      {activeTab === 'rules' ? (
        <RegionPicker
          monitorId={monitorId}
          initialRules={monitor.rules || []}
          onRulesSaved={(updated) => {
            setMonitor({ ...monitor, rules: updated });
            loadData();
          }}
        />
      ) : activeTab === 'compare' ? (
        <VersionCompare
          monitorId={monitorId}
          versions={versions}
          initialFromId={compareFromId}
          initialToId={compareToId}
        />
      ) : (
        /* Main Grid */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Left Column: Screenshot & Extracted Content (2 cols) */}
          <div className="lg:col-span-2 space-y-6">
            {/* Display Selected or Latest Screenshot Card */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl overflow-hidden shadow-sm">
              <div className="px-5 py-3.5 border-b border-[#E2E8F0] flex items-center justify-between bg-slate-50/50">
                <div className="flex items-center space-x-2 text-xs font-semibold text-[#0F172A]">
                  <ImageIcon className="w-4 h-4 text-blue-600" />
                  <span>
                    Captured Webpage Snapshot {displayVersion ? `(Version #${displayVersion.sequence_number})` : ''}
                  </span>
                </div>
                {displayVersion && (
                  <span className="text-[11px] text-[#64748B]">
                    Captured {new Date(displayVersion.captured_at).toLocaleTimeString()}
                  </span>
                )}
              </div>

              <div className="p-4 bg-slate-100 flex items-center justify-center min-h-[360px]">
                {displayVersion ? (
                  imageError ? (
                    <div className="text-center p-8 text-[#64748B] flex flex-col items-center">
                      <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center mb-2.5">
                        <AlertCircle className="w-5 h-5" />
                      </div>
                      <p className="text-xs font-semibold text-[#0F172A]">Screenshot failed to render</p>
                      <p className="text-[11px] text-[#64748B] mt-1 mb-3 max-w-xs">
                        Unable to load the captured snapshot image. Verify network access or retry.
                      </p>
                      <button
                        onClick={() => {
                          setImageError(false);
                          setImageRetryCount((prev) => prev + 1);
                        }}
                        className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-medium shadow-sm transition-all"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                        <span>Retry Screenshot</span>
                      </button>
                    </div>
                  ) : (
                    <div className="relative border border-[#CBD5E1] rounded-lg overflow-hidden bg-white shadow-sm max-w-full">
                      <img
                        key={`${displayVersion.id}-${imageRetryCount}`}
                        src={resolvedScreenshotUrl}
                        alt={`Screenshot for ${monitor.name}`}
                        onLoad={() => setImageError(false)}
                        onError={() => setImageError(true)}
                        className="w-full h-auto object-top max-h-[500px] object-cover"
                      />
                    </div>
                  )
                ) : (

                <div className="text-center p-12 text-[#64748B]">
                  <ImageIcon className="w-12 h-12 stroke-[1.5] mx-auto mb-2 text-slate-400" />
                  <p className="text-xs font-semibold text-[#0F172A]">No snapshot captured yet</p>
                  <p className="text-[11px] text-[#64748B] mt-1 mb-4">
                    Click "Check Now" to execute the first Playwright Chromium capture.
                  </p>
                  <button
                    onClick={handleCheckNow}
                    disabled={checking}
                    className="inline-flex items-center space-x-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium px-3.5 py-1.5 rounded-lg"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${checking ? 'animate-spin' : ''}`} />
                    <span>Run Baseline Check</span>
                  </button>
                </div>
              )}
            </div>
          </div>

            {/* Extracted Content & Hashes */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center space-x-2 text-xs font-semibold text-[#0F172A]">
                <FileText className="w-4 h-4 text-blue-600" />
                <span>
                  Extracted Web Content Details {displayVersion ? `(v${displayVersion.sequence_number})` : ''}
                </span>
              </div>

              {displayVersion ? (
                <div className="space-y-3 text-xs">
                  <div>
                    <span className="text-[#64748B] block font-medium mb-1">SHA-256 Content Hash:</span>
                    <div className="flex items-center space-x-1.5 bg-slate-50 border border-[#E2E8F0] px-3 py-1.5 rounded-lg font-mono text-[11px] text-[#0F172A]">
                      <Hash className="w-3.5 h-3.5 text-[#64748B] shrink-0" />
                      <span className="truncate">{displayVersion.content_hash}</span>
                    </div>
                  </div>

                  <div>
                    <span className="text-[#64748B] block font-medium mb-1">Normalized Text Preview:</span>
                    <div className="bg-slate-50 border border-[#E2E8F0] rounded-lg p-3 font-mono text-[11px] text-slate-800 whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed">
                      {displayVersion.short_preview}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-[#64748B]">Content metadata will appear after the first successful check.</p>
              )}
            </div>
          </div>


        {/* Right Column: Check Activity Log & Versions (1 col) */}
        <div className="space-y-6">
          {/* Versions Timeline */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2 text-xs font-semibold text-[#0F172A]">
                <Layers className="w-4 h-4 text-blue-600" />
                <span>Captured Versions ({versions.length})</span>
              </div>
            </div>

            {versions.length === 0 ? (
              <p className="text-xs text-[#64748B]">No versions saved yet.</p>
            ) : (
              <div className="space-y-2">
                {versions.map((v, idx) => (
                  <div
                    key={v.id}
                    onClick={() => {
                      setSelectedVersion(v);
                      setImageError(false);
                    }}
                    className={`p-3 rounded-lg border text-xs cursor-pointer transition-all ${
                      selectedVersion?.id === v.id
                        ? 'border-blue-500 bg-blue-50/50'
                        : 'border-[#E2E8F0] hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center space-x-1.5">
                        <span className="font-semibold text-[#0F172A]">Version #{v.sequence_number}</span>
                        {idx === 0 && (
                          <span className="text-[9px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-medium">
                            Latest
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-[#64748B]">
                        {new Date(v.captured_at).toLocaleTimeString()}
                      </span>
                    </div>

                    <p className="text-[11px] text-[#475569] line-clamp-2 my-1 leading-relaxed">
                      {v.short_preview || 'No content preview available'}
                    </p>

                    <div className="flex items-center justify-between pt-1 border-t border-slate-100 mt-1.5 text-[10px]">
                      <span className="text-[#64748B] font-mono truncate max-w-[140px]">
                        {v.content_hash.slice(0, 14)}...
                      </span>

                      {versions.length >= 2 && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            // If there is an adjacent earlier version, compare with it
                            const baseIdx = Math.min(idx + 1, versions.length - 1);
                            setCompareFromId(versions[baseIdx].id);
                            setCompareToId(v.id);
                            setActiveTab('compare');
                          }}
                          className="inline-flex items-center space-x-1 text-blue-600 hover:text-blue-800 font-medium hover:underline"
                        >
                          <GitCompare className="w-3 h-3" />
                          <span>Compare</span>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>


          {/* Check History / Run Log */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-sm">
            <div className="flex items-center space-x-2 text-xs font-semibold text-[#0F172A] mb-4">
              <Terminal className="w-4 h-4 text-blue-600" />
              <span>Check Execution Activity</span>
            </div>

            {checks.length === 0 ? (
              <p className="text-xs text-[#64748B]">No checks logged yet.</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {checks.map((c) => (
                  <div key={c.id} className="p-3 rounded-lg bg-slate-50 border border-[#E2E8F0] text-xs">
                    <div className="flex items-center justify-between mb-1">
                      <span
                        className={`font-semibold uppercase text-[10px] px-2 py-0.5 rounded-full border ${
                          c.state === 'queued'
                            ? 'bg-amber-50 text-amber-800 border-amber-300'
                            : c.state === 'running'
                            ? 'bg-blue-50 text-blue-800 border-blue-300'
                            : c.state === 'baseline' || c.state === 'unchanged' || c.state === 'changed'
                            ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                            : c.state === 'error'
                            ? 'bg-rose-50 text-rose-800 border-rose-300'
                            : c.state === 'blocked'
                            ? 'bg-amber-50 text-amber-800 border-amber-300'
                            : 'bg-slate-100 text-slate-800 border-slate-300'
                        }`}
                      >
                        {c.state === 'queued'
                          ? 'QUEUED'
                          : c.state === 'running'
                          ? 'RUNNING'
                          : c.state === 'baseline' || c.state === 'unchanged' || c.state === 'changed'
                          ? `SUCCESSFUL (${c.state})`
                          : c.state === 'error' || c.state === 'blocked'
                          ? `FAILED (${c.state})`
                          : c.state}
                      </span>
                      <span className="text-[10px] text-[#64748B]">
                        {c.finished_at ? new Date(c.finished_at).toLocaleTimeString() : c.state === 'running' ? 'In Progress' : 'Queued'}
                      </span>
                    </div>

                    <div className="text-[11px] text-[#64748B] mt-1 flex items-center justify-between">
                      <span>HTTP {c.http_status || '---'}</span>
                      {c.duration_ms && <span>{c.duration_ms} ms</span>}
                    </div>

                    {c.error_message && (
                      <p className="text-[11px] text-rose-600 mt-1.5 font-medium leading-snug">
                        {c.error_message}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    )}

    {/* Confirmation Dialog for Destructive Action */}
    <ConfirmModal
      isOpen={isDeleteModalOpen}
      title="Delete Monitor"
      message={`Are you sure you want to delete "${monitor?.name}"? This action cannot be undone and will remove all version history, check runs, rules, and outbox logs.`}
      confirmText="Yes, Delete Monitor"
      confirmVariant="danger"
      loading={deleteLoading}
      onConfirm={handleConfirmDelete}
      onCancel={() => setIsDeleteModalOpen(false)}
    />
  </div>
);
};


