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

  const formatChangePercent = (ratio: number): string => {
    if (ratio === 0) return '0.00%';
    const pct = ratio * 100;
    if (pct < 0.01) {
      return `${pct.toFixed(4)}%`;
    }
    return `${pct.toFixed(2)}%`;
  };

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
      <div className="bg-surface-elevated border border-warmborder rounded-2xl p-10 text-center text-text-muted shadow-luxury">
        <GitCompare className="w-10 h-10 text-gold-champagne/40 mx-auto mb-3" />
        <h4 className="text-sm font-serif font-medium text-ivory-warm">Multiple Versions Required</h4>
        <p className="text-xs text-text-subtle mt-1 max-w-sm mx-auto">
          At least two distinct saved snapshots are needed to compute text and visual difference comparisons.
        </p>
      </div>
    );
  }

  const additionsCount = comparison?.text_diff.filter((d) => d.kind === 'add').length || 0;
  const removalsCount = comparison?.text_diff.filter((d) => d.kind === 'remove').length || 0;

  return (
    <div className="bg-surface-elevated border border-warmborder rounded-2xl overflow-hidden shadow-luxury space-y-0">
      {/* Selector Header Bar */}
      <div className="p-5 border-b border-warmborder bg-obsidian-deep/80 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-gold-champagne/15 text-gold-champagne flex items-center justify-center border border-gold-champagne/25 shadow-gold">
            <GitCompare className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-serif font-medium text-ivory-warm">Version Comparison Engine</h3>
            <p className="text-[11px] text-text-subtle">Compare any two captured versions across your timeline</p>
          </div>
        </div>

        {/* Version Pickers */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="flex items-center space-x-2 bg-surface-interactive border border-warmborder rounded-xl px-3 py-1.5 focus-within:border-gold-champagne/50 transition-colors">
            <span className="text-text-subtle font-medium text-[11px]">Base:</span>
            <select
              value={fromId}
              onChange={(e) => setFromId(e.target.value)}
              className="bg-transparent font-medium text-ivory-warm focus:outline-none cursor-pointer"
            >
              {sortedVersions.map((v) => (
                <option key={v.id} value={v.id} className="bg-surface-elevated text-ivory-warm">
                  v{v.sequence_number} ({new Date(v.captured_at).toLocaleTimeString()})
                </option>
              ))}
            </select>
          </div>

          <ArrowRight className="w-4 h-4 text-gold-champagne/50" />

          <div className="flex items-center space-x-2 bg-surface-interactive border border-warmborder rounded-xl px-3 py-1.5 focus-within:border-gold-champagne/50 transition-colors">
            <span className="text-text-subtle font-medium text-[11px]">Target:</span>
            <select
              value={toId}
              onChange={(e) => setToId(e.target.value)}
              className="bg-transparent font-medium text-ivory-warm focus:outline-none cursor-pointer"
            >
              {sortedVersions.map((v) => (
                <option key={v.id} value={v.id} className="bg-surface-elevated text-ivory-warm">
                  v{v.sequence_number} ({new Date(v.captured_at).toLocaleTimeString()})
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => fetchComparison(fromId, toId)}
            disabled={loading}
            className="p-2 text-text-subtle hover:text-ivory-warm hover:bg-surface-interactive rounded-xl border border-transparent hover:border-warmborder transition-all"
            title="Refresh comparison"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-gold-champagne' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabs & Metrics */}
      <div className="px-5 py-3 border-b border-warmborder flex flex-wrap items-center justify-between gap-3 bg-obsidian-deep/50">
        <div className="flex items-center space-x-1.5 bg-obsidian-base p-1 rounded-xl border border-warmborder">
          <button
            onClick={() => setActiveTab('text')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
              activeTab === 'text'
                ? 'bg-surface-interactive text-gold-champagne shadow-sm border border-gold-champagne/30'
                : 'text-text-muted hover:text-ivory-warm border border-transparent'
            }`}
          >
            <span className="flex items-center space-x-1.5">
              <FileText className="w-3.5 h-3.5" />
              <span>Text Difference</span>
            </span>
          </button>
          <button
            onClick={() => setActiveTab('side-by-side')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
              activeTab === 'side-by-side'
                ? 'bg-surface-interactive text-gold-champagne shadow-sm border border-gold-champagne/30'
                : 'text-text-muted hover:text-ivory-warm border border-transparent'
            }`}
          >
            <span className="flex items-center space-x-1.5">
              <ImageIcon className="w-3.5 h-3.5" />
              <span>Side-by-Side Snapshots</span>
            </span>
          </button>
          <button
            onClick={() => setActiveTab('visual')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
              activeTab === 'visual'
                ? 'bg-surface-interactive text-gold-champagne shadow-sm border border-gold-champagne/30'
                : 'text-text-muted hover:text-ivory-warm border border-transparent'
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
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              +{additionsCount} additions
            </span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
              -{removalsCount} removals
            </span>
            {comparison.change_ratio > 0 && (
              <span className="text-text-subtle text-[11px] font-mono">
                Visual delta: {formatChangePercent(comparison.change_ratio)}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Content Area */}
      <div className="p-5">
        {loading && (
          <div className="py-20 flex flex-col items-center justify-center text-text-subtle">
            <RefreshCw className="w-6 h-6 animate-spin text-gold-champagne mb-2" />
            <p className="text-xs font-medium">Computing difference between selected versions...</p>
          </div>
        )}

        {error && (
          <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-center space-x-3 text-rose-400 text-xs">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && comparison && (
          <div>
            {/* 1. Text Diff View */}
            {activeTab === 'text' && (
              <div className="border border-warmborder rounded-xl overflow-hidden bg-obsidian-deep">
                <div className="px-4 py-2.5 bg-surface-elevated border-b border-warmborder text-xs font-medium text-ivory-warm flex justify-between items-center">
                  <span className="font-serif">Normalized Text Diff (DOM Text Stream)</span>
                  <span className="text-[11px] text-text-subtle font-mono">
                    v{comparison.old_version.sequence_number} → v{comparison.new_version.sequence_number}
                  </span>
                </div>
                <div className="divide-y divide-warmborder/30 font-mono text-xs max-h-[500px] overflow-y-auto">
                  {comparison.text_diff.length === 0 ? (
                    <div className="p-8 text-center text-text-subtle">No text changes detected between these versions.</div>
                  ) : (
                    comparison.text_diff.map((item, idx) => {
                      if (item.kind === 'add') {
                        return (
                          <div key={idx} className="bg-emerald-950/20 text-emerald-300 px-4 py-2 flex items-start space-x-3">
                            <span className="font-bold text-emerald-400 select-none w-4 shrink-0">+</span>
                            <span className="whitespace-pre-wrap break-words flex-1">{item.text}</span>
                          </div>
                        );
                      }
                      if (item.kind === 'remove') {
                        return (
                          <div key={idx} className="bg-rose-950/20 text-rose-300 px-4 py-2 flex items-start space-x-3">
                            <span className="font-bold text-rose-400 select-none w-4 shrink-0">-</span>
                            <span className="whitespace-pre-wrap break-words flex-1 line-through opacity-80">
                              {item.text}
                            </span>
                          </div>
                        );
                      }
                      return (
                        <div key={idx} className="bg-obsidian-deep/80 text-ivory-warm/80 px-4 py-1.5 flex items-start space-x-3">
                          <span className="text-text-subtle select-none w-4 shrink-0"> </span>
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
                <div className="border border-warmborder rounded-xl overflow-hidden bg-surface-elevated shadow-luxury">
                  <div className="px-3.5 py-2.5 border-b border-warmborder bg-obsidian-deep flex justify-between items-center text-xs">
                    <span className="font-serif font-medium text-ivory-warm">
                      Base Snapshot (v{comparison.old_version.sequence_number})
                    </span>
                    <span className="text-text-subtle text-[11px] font-mono">
                      {new Date(comparison.old_version.captured_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="p-3 flex items-center justify-center bg-obsidian-base">
                    <img
                      src={comparison.image_old_url}
                      alt="Base version screenshot"
                      className="max-h-[480px] w-full object-cover object-top rounded-lg border border-warmborder"
                    />
                  </div>
                </div>

                <div className="border border-warmborder rounded-xl overflow-hidden bg-surface-elevated shadow-luxury">
                  <div className="px-3.5 py-2.5 border-b border-warmborder bg-obsidian-deep flex justify-between items-center text-xs">
                    <span className="font-serif font-medium text-ivory-warm">
                      Target Snapshot (v{comparison.new_version.sequence_number})
                    </span>
                    <span className="text-text-subtle text-[11px] font-mono">
                      {new Date(comparison.new_version.captured_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="p-3 flex items-center justify-center bg-obsidian-base">
                    <img
                      src={comparison.image_new_url}
                      alt="Target version screenshot"
                      className="max-h-[480px] w-full object-cover object-top rounded-lg border border-warmborder"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* 3. Visual Difference Highlight Overlay */}
            {activeTab === 'visual' && (
              <div className="border border-warmborder rounded-xl overflow-hidden bg-surface-elevated shadow-luxury">
                <div className="px-4 py-2.5 border-b border-warmborder bg-obsidian-deep flex justify-between items-center text-xs">
                  <div className="flex items-center space-x-2">
                    <span className="font-serif font-medium text-ivory-warm">Pillow Pixel Difference Overlay</span>
                    <span className="text-[11px] text-rose-300 bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded font-medium">
                      Red pixels highlight visual delta
                    </span>
                  </div>
                  {comparison.change_ratio !== undefined && (
                    <span className="text-text-subtle text-[11px] font-mono">
                      Delta: {formatChangePercent(comparison.change_ratio)}
                    </span>
                  )}
                </div>

                <div className="p-4 flex items-center justify-center bg-obsidian-base min-h-[380px]">
                  {comparison.image_diff_url ? (
                    <img
                      src={comparison.image_diff_url}
                      alt="Visual diff overlay"
                      className="max-h-[500px] w-auto max-w-full rounded-lg border border-warmborder shadow-luxury"
                    />
                  ) : (
                    <div className="text-center text-text-subtle p-8 text-xs">
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
