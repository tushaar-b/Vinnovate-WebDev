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
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            Content Changed
          </span>
        );
      case 'baseline_created':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-indigo-100 text-indigo-800 border border-indigo-200">
            Baseline Created
          </span>
        );
      case 'content_unchanged':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            Unchanged
          </span>
        );
      case 'monitoring_failed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200">
            Monitoring Failed
          </span>
        );
      case 'monitoring_blocked':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            Monitoring Blocked
          </span>
        );
      case 'alert_delivered':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            Alert Delivered
          </span>
        );
      case 'alert_failed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
            Alert Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-800">
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
          <h2 className="text-xl font-bold text-slate-900">Activity Feed</h2>
          <p className="text-sm text-slate-500 mt-1">
            Real-time chronological events from monitoring runs and external alert deliveries.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={loadActivity}
            disabled={loading}
            className="inline-flex items-center px-3 py-1.5 text-xs font-medium border border-slate-300 rounded-lg bg-white text-slate-700 hover:bg-slate-50 shadow-sm disabled:opacity-50"
          >
            <svg
              className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin text-blue-600' : 'text-slate-500'}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* Filter Tabs & Search */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-3">
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
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                filter === tab.id
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
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
            className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Feed List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden divide-y divide-slate-100">
        {loading && items.length === 0 ? (
          <div className="py-20 text-center text-slate-500 text-xs">
            <svg className="animate-spin h-6 w-6 mx-auto mb-2 text-blue-600" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Loading real events from database...
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="py-20 text-center text-slate-400 text-xs">
            No activity events recorded matching this filter.
          </div>
        ) : (
          filteredItems.map((item) => (
            <div
              key={item.id}
              className="p-5 hover:bg-slate-50/70 transition-colors flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
            >
              <div className="flex items-start space-x-3.5">
                <span className="text-2xl mt-0.5 select-none">{getEventIcon(item.event_type)}</span>
                <div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => onNavigateToMonitor && onNavigateToMonitor(item.monitor_id)}
                      className="font-semibold text-sm text-slate-900 hover:text-blue-600 transition-colors text-left"
                    >
                      {item.monitor_name}
                    </button>
                    {getEventBadge(item.event_type)}
                  </div>
                  <p className="text-xs text-slate-600 mt-1 font-normal leading-relaxed">{item.summary}</p>
                  <div className="flex items-center space-x-3 mt-2 text-[11px] text-slate-400">
                    <span>{new Date(item.timestamp).toLocaleString()}</span>
                    <span>•</span>
                    <a
                      href={item.monitor_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline truncate max-w-xs"
                    >
                      {item.monitor_url}
                    </a>
                  </div>
                </div>
              </div>

              {item.event_type === 'content_changed' && onNavigateToMonitor && (
                <button
                  onClick={() => onNavigateToMonitor(item.monitor_id, 'compare')}
                  className="shrink-0 inline-flex items-center px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition-colors"
                >
                  View Comparison
                  <svg className="w-3.5 h-3.5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
