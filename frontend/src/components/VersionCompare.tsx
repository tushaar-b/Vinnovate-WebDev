import React, { useState, useEffect } from 'react';
import {
  GitCompare,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  FileText,
  Image as ImageIcon,
  Sliders,
} from 'lucide-react';

import { VersionSummary, VersionComparison } from '../types';
import { api } from '../services/api';

interface VersionCompareProps {
  monitorId: string;
  versions: VersionSummary[];
  initialFromId?: string;
  initialToId?: string;
}

export const VersionCompare: React.FC<VersionCompareProps> = ({
  monitorId,
  versions,
  initialFromId,
  initialToId,
}) => {
  // Sort versions by sequence number asc for intuitive from -> to comparison
  const sortedVersions = [...versions].sort((a, b) => a.sequence_number - b.sequence_number);

  // Default: compare penultimate to ultimate if available, else first two
  const defaultFrom =
    initialFromId ||
    (sortedVersions.length >= 2 ? sortedVersions[sortedVersions.length - 2].id : sortedVersions[0]?.id || '');
  const defaultTo =
    initialToId ||
    (sortedVersions.length >= 2 ? sortedVersions[sortedVersions.length - 1].id : sortedVersions[0]?.id || '');

  const [fromId, setFromId] = useState<string>(defaultFrom);
  const [toId, setToId] = useState<string>(defaultTo);
  const [comparison, setComparison] = useState<VersionComparison | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'text' | 'visual' | 'side-by-side'>('text');

  const fetchComparison = async (from: string, to: string) => {
    if (!from || !to) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.compareVersions(monitorId, from, to);
      setComparison(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to compare versions');
      setComparison(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (fromId && toId) {
      fetchComparison(fromId, toId);
    }
  }, [fromId, toId, monitorId]);

  if (versions.length < 2) {
    return (
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-8 text-center text-[#64748B]">
        <GitCompare className="w-10 h-10 text-slate-400 mx-auto mb-3" />
        <h4 className="text-sm font-semibold text-[#0F172A]">Multiple Versions Required</h4>
        <p className="text-xs text-[#64748B] mt-1 max-w-sm mx-auto">
          At least two distinct saved snapshots are needed to compute text and visual difference comparisons.
        </p>
      </div>
    );
  }

  const additionsCount = comparison?.text_diff.filter((d) => d.kind === 'add').length || 0;
  const removalsCount = comparison?.text_diff.filter((d) => d.kind === 'remove').length || 0;

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl overflow-hidden shadow-sm space-y-0">
      {/* Selector Header Bar */}
      <div className="p-5 border-b border-[#E2E8F0] bg-slate-50/70 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center font-semibold">
            <GitCompare className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#0F172A]">Version Comparison</h3>
            <p className="text-[11px] text-[#64748B]">Compare any two captured versions across timeline</p>
          </div>
        </div>

        {/* Version Pickers */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="flex items-center space-x-1.5 bg-white border border-[#CBD5E1] rounded-lg px-2.5 py-1.5 shadow-sm">
            <span className="text-[#64748B] font-medium text-[11px]">Base:</span>
            <select
              value={fromId}
              onChange={(e) => setFromId(e.target.value)}
              className="bg-transparent font-semibold text-[#0F172A] focus:outline-none cursor-pointer"
            >
              {sortedVersions.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.sequence_number} ({new Date(v.captured_at).toLocaleTimeString()})
                </option>
              ))}
            </select>
          </div>

          <ArrowRight className="w-4 h-4 text-[#94A3B8]" />

          <div className="flex items-center space-x-1.5 bg-white border border-[#CBD5E1] rounded-lg px-2.5 py-1.5 shadow-sm">
            <span className="text-[#64748B] font-medium text-[11px]">Target:</span>
            <select
              value={toId}
              onChange={(e) => setToId(e.target.value)}
              className="bg-transparent font-semibold text-[#0F172A] focus:outline-none cursor-pointer"
            >
              {sortedVersions.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.sequence_number} ({new Date(v.captured_at).toLocaleTimeString()})
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => fetchComparison(fromId, toId)}
            disabled={loading}
            className="p-2 text-[#64748B] hover:text-[#0F172A] hover:bg-slate-200 rounded-lg transition-colors"
            title="Refresh comparison"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabs & Metrics */}
      <div className="px-5 py-3 border-b border-[#E2E8F0] flex flex-wrap items-center justify-between gap-3 bg-white">
        <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-lg">
          <button
            onClick={() => setActiveTab('text')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
              activeTab === 'text'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            <span className="flex items-center space-x-1.5">
              <FileText className="w-3.5 h-3.5" />
              <span>Text Difference</span>
            </span>
          </button>
          <button
            onClick={() => setActiveTab('side-by-side')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
              activeTab === 'side-by-side'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            <span className="flex items-center space-x-1.5">
              <ImageIcon className="w-3.5 h-3.5" />
              <span>Side-by-Side Snapshots</span>
            </span>
          </button>
          <button
            onClick={() => setActiveTab('visual')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
              activeTab === 'visual'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            <span className="flex items-center space-x-1.5">
              <Sliders className="w-3.5 h-3.5" />
              <span>Visual Overlay Diff</span>
            </span>
          </button>
        </div>

        {/* Change Indicators */}
        {comparison && (
          <div className="flex items-center space-x-3 text-xs">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              +{additionsCount} additions
            </span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full font-medium bg-rose-50 text-rose-700 border border-rose-200">
              -{removalsCount} removals
            </span>
            {comparison.change_ratio > 0 && (
              <span className="text-[#64748B] text-[11px] font-mono">
                Visual change: {(comparison.change_ratio * 100).toFixed(2)}%
              </span>
            )}
          </div>
        )}
      </div>

      {/* Content Area */}
      <div className="p-5">
        {loading && (
          <div className="py-20 flex flex-col items-center justify-center text-[#64748B]">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600 mb-2" />
            <p className="text-xs font-medium">Computing diff between selected versions...</p>
          </div>
        )}

        {error && (
          <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-3 text-rose-700 text-xs">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && comparison && (
          <div>
            {/* 1. Text Diff View */}
            {activeTab === 'text' && (
              <div className="border border-[#E2E8F0] rounded-lg overflow-hidden bg-white">
                <div className="px-4 py-2.5 bg-slate-50 border-b border-[#E2E8F0] text-xs font-semibold text-[#0F172A] flex justify-between items-center">
                  <span>Structured Normalized Text Diff</span>
                  <span className="text-[11px] text-[#64748B]">
                    Comparing v{comparison.old_version.sequence_number} → v{comparison.new_version.sequence_number}
                  </span>
                </div>
                <div className="divide-y divide-[#F1F5F9] font-mono text-xs max-h-[500px] overflow-y-auto">
                  {comparison.text_diff.length === 0 ? (
                    <div className="p-8 text-center text-[#64748B]">No text changes detected between these versions.</div>
                  ) : (
                    comparison.text_diff.map((item, idx) => {
                      if (item.kind === 'add') {
                        return (
                          <div key={idx} className="bg-emerald-50 text-emerald-900 px-4 py-2 flex items-start space-x-3">
                            <span className="font-bold text-emerald-600 select-none w-4 shrink-0">+</span>
                            <span className="whitespace-pre-wrap break-words flex-1">{item.text}</span>
                          </div>
                        );
                      }
                      if (item.kind === 'remove') {
                        return (
                          <div key={idx} className="bg-rose-50 text-rose-900 px-4 py-2 flex items-start space-x-3">
                            <span className="font-bold text-rose-600 select-none w-4 shrink-0">-</span>
                            <span className="whitespace-pre-wrap break-words flex-1 line-through opacity-85">
                              {item.text}
                            </span>
                          </div>
                        );
                      }
                      return (
                        <div key={idx} className="bg-white text-slate-700 px-4 py-1.5 flex items-start space-x-3">
                          <span className="text-slate-300 select-none w-4 shrink-0"> </span>
                          <span className="whitespace-pre-wrap break-words flex-1">{item.text}</span>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}

            {/* 2. Side-by-Side Screenshots */}
            {activeTab === 'side-by-side' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="border border-[#E2E8F0] rounded-xl overflow-hidden bg-slate-50 shadow-sm">
                  <div className="px-3.5 py-2 border-b border-[#E2E8F0] bg-white flex justify-between items-center text-xs">
                    <span className="font-semibold text-[#0F172A]">
                      Base (v{comparison.old_version.sequence_number})
                    </span>
                    <span className="text-[#64748B] text-[10px]">
                      {new Date(comparison.old_version.captured_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="p-3 flex items-center justify-center">
                    <img
                      src={comparison.image_old_url}
                      alt="Base version screenshot"
                      className="max-h-[480px] w-full object-cover object-top rounded-lg border border-[#CBD5E1]"
                    />
                  </div>
                </div>

                <div className="border border-[#E2E8F0] rounded-xl overflow-hidden bg-slate-50 shadow-sm">
                  <div className="px-3.5 py-2 border-b border-[#E2E8F0] bg-white flex justify-between items-center text-xs">
                    <span className="font-semibold text-[#0F172A]">
                      Target (v{comparison.new_version.sequence_number})
                    </span>
                    <span className="text-[#64748B] text-[10px]">
                      {new Date(comparison.new_version.captured_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="p-3 flex items-center justify-center">
                    <img
                      src={comparison.image_new_url}
                      alt="Target version screenshot"
                      className="max-h-[480px] w-full object-cover object-top rounded-lg border border-[#CBD5E1]"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* 3. Visual Difference Highlight Overlay */}
            {activeTab === 'visual' && (
              <div className="border border-[#E2E8F0] rounded-xl overflow-hidden bg-slate-50 shadow-sm">
                <div className="px-4 py-2.5 border-b border-[#E2E8F0] bg-white flex justify-between items-center text-xs">
                  <div className="flex items-center space-x-2">
                    <span className="font-semibold text-[#0F172A]">Pillow Pixel Difference Overlay</span>
                    <span className="text-[11px] text-rose-600 bg-rose-50 px-2 py-0.5 rounded font-medium">
                      Red pixels indicate visual changes
                    </span>
                  </div>
                  {comparison.change_ratio !== undefined && (
                    <span className="text-[#64748B] text-[11px] font-mono">
                      Delta: {(comparison.change_ratio * 100).toFixed(2)}%
                    </span>
                  )}
                </div>

                <div className="p-4 flex items-center justify-center bg-slate-100 min-h-[380px]">
                  {comparison.image_diff_url ? (
                    <img
                      src={comparison.image_diff_url}
                      alt="Visual diff overlay"
                      className="max-h-[500px] w-auto max-w-full rounded-lg border border-[#CBD5E1] shadow-sm"
                    />
                  ) : (
                    <div className="text-center text-[#64748B] p-8 text-xs">
                      Visual diff unavailable for these screenshots.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
