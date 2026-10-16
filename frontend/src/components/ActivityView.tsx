import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { ActivityItem } from '../types';

interface ActivityViewProps {
  onNavigateToMonitor?: (monitorId: string, tab?: string) => void;
}

export const ActivityView: React.FC<ActivityViewProps> = ({ onNavigateToMonitor }) => {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');

  useEffect(() => {
    loadActivity();
  }, [filter]);

  const loadActivity = async () => {
    setLoading(true);
    try {
      const data = await api.getActivity(100, filter);
      setItems(data.items || []);
    } catch (e) {
      console.error('Failed to load activity feed:', e);
    } finally {
      setLoading(false);
    }
  };

  const getEventBadge = (eventType: string) => {
    switch (eventType) {
      case 'content_changed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/15 text-amber-300 border border-amber-500/30">
            Content Changed
          </span>
        );
      case 'baseline_created':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-gold-champagne/15 text-gold-champagne border border-gold-champagne/30">
            Baseline Created
          </span>
        );
      case 'content_unchanged':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Unchanged
          </span>
        );
      case 'monitoring_failed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/15 text-rose-400 border border-rose-500/30">
            Monitoring Failed
          </span>
        );
      case 'monitoring_blocked':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30">
            Monitoring Blocked
          </span>
        );
      case 'alert_delivered':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            Alert Delivered
          </span>
        );
      case 'alert_failed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/15 text-rose-400 border border-rose-500/30">
            Alert Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-surface-interactive text-ivory-warm border border-warmborder">
            {eventType}
          </span>
        );
    }
  };

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'content_changed':
        return '🚨';
      case 'baseline_created':
        return '🏁';
      case 'content_unchanged':
        return '✔️';
      case 'monitoring_failed':
        return '❌';
      case 'monitoring_blocked':
        return '🛡️';
      case 'alert_delivered':
        return '🔔';
      case 'alert_failed':
        return '⚠️';
      default:
        return '📌';
    }
  };

  const filteredItems = items.filter((item) => {
    if (!search) return true;
    const term = search.toLowerCase();
    return (
      item.monitor_name.toLowerCase().includes(term) ||
      item.title.toLowerCase().includes(term) ||
      item.summary.toLowerCase().includes(term) ||
      item.monitor_url.toLowerCase().includes(term)
    );
  });

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-serif font-medium text-ivory-warm">Activity Audit Stream</h2>
          <p className="text-xs text-text-subtle mt-1">
            Real-time chronological events from monitoring executions, hash changes, and webhook alerts.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={loadActivity}
            disabled={loading}
            className="inline-flex items-center px-3.5 py-2 text-xs font-medium border border-warmborder rounded-xl bg-surface-elevated text-ivory-warm hover:bg-surface-interactive shadow-luxury transition-all disabled:opacity-50"
          >
            <svg
              className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin text-gold-champagne' : 'text-gold-champagne'}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh Stream
          </button>
        </div>
      </div>

      {/* Filter Tabs & Search */}
      <div className="bg-surface-elevated p-4 rounded-2xl border border-warmborder shadow-luxury flex flex-col md:flex-row items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5 w-full md:w-auto">
          {[
            { id: 'all', label: 'All Events' },
            { id: 'content_changed', label: 'Changes' },
            { id: 'baseline_created', label: 'Baselines' },
            { id: 'content_unchanged', label: 'Unchanged' },
            { id: 'monitoring_failed', label: 'Errors' },
            { id: 'monitoring_blocked', label: 'Blocked' },
            { id: 'alert_delivered', label: 'Alerts' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                filter === tab.id
                  ? 'bg-gold-champagne text-obsidian-deep shadow-gold'
                  : 'bg-surface-interactive text-text-muted hover:text-ivory-warm border border-warmborder/30'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="w-full md:w-64">
          <input
            type="text"
            placeholder="Search activity..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full text-xs px-3.5 py-2 bg-surface-interactive border border-warmborder rounded-xl text-ivory-warm placeholder:text-text-subtle focus:outline-none focus:border-gold-champagne/60 transition-colors"
          />
        </div>
      </div>

      {/* Feed List */}
      <div className="bg-surface-elevated rounded-2xl border border-warmborder shadow-luxury overflow-hidden divide-y divide-warmborder/30">
        {loading && items.length === 0 ? (
          <div className="py-20 text-center text-text-subtle text-xs">
            <svg className="animate-spin h-6 w-6 mx-auto mb-2 text-gold-champagne" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Streaming real audit events from database...
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="py-20 text-center text-text-subtle text-xs">
            No activity events recorded matching this filter.
          </div>
        ) : (
          filteredItems.map((item) => (
            <div
              key={item.id}
              className="p-5 hover:bg-surface-interactive/40 transition-colors flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
            >
              <div className="flex items-start space-x-3.5">
                <span className="text-2xl mt-0.5 select-none">{getEventIcon(item.event_type)}</span>
                <div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => onNavigateToMonitor && onNavigateToMonitor(item.monitor_id)}
                      className="font-serif font-medium text-sm text-ivory-warm hover:text-gold-champagne transition-colors text-left"
                    >
                      {item.monitor_name}
                    </button>
                    {getEventBadge(item.event_type)}
                  </div>
                  <p className="text-xs text-text-muted mt-1 font-normal leading-relaxed">{item.summary}</p>
                  <div className="flex items-center space-x-3 mt-2 text-[11px] text-text-subtle">
                    <span className="font-mono">{new Date(item.timestamp).toLocaleString()}</span>
                    <span>•</span>
                    <a
                      href={item.monitor_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-gold-champagne hover:underline truncate max-w-xs font-mono"
                    >
                      {item.monitor_url}
                    </a>
                  </div>
                </div>
              </div>

              {item.event_type === 'content_changed' && onNavigateToMonitor && (
                <button
                  onClick={() => onNavigateToMonitor(item.monitor_id, 'compare')}
                  className="shrink-0 inline-flex items-center px-3.5 py-1.5 text-xs font-medium rounded-xl bg-gold-champagne/15 text-gold-champagne hover:bg-gold-champagne/25 border border-gold-champagne/30 shadow-gold transition-all"
                >
                  View Comparison
                  <svg className="w-3.5 h-3.5 ml-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
