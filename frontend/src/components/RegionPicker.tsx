import React, { useState, useEffect, useRef } from 'react';
import {
  Crosshair,
  Eye,
  EyeOff,
  Plus,
  Trash2,
  Save,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Layers,
} from 'lucide-react';
import { MonitorRule, PickerData, PickerElement } from '../types';
import { api } from '../services/api';

interface RegionPickerProps {
  monitorId: string;
  initialRules: MonitorRule[];
  onRulesSaved: (updatedRules: MonitorRule[]) => void;
}

export const RegionPicker: React.FC<RegionPickerProps> = ({
  monitorId,
  initialRules,
  onRulesSaved,
}) => {
  const [pickerData, setPickerData] = useState<PickerData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [imageError, setImageError] = useState<boolean>(false);

  const [rules, setRules] = useState<{ rule_type: 'watch' | 'ignore'; css_selector: string; label?: string }[]>(
    initialRules.map((r) => ({
      rule_type: r.rule_type,
      css_selector: r.css_selector,
      label: r.label || undefined,
    }))
  );

  const [hoveredElement, setHoveredElement] = useState<PickerElement | null>(null);
  const [selectedMode, setSelectedMode] = useState<'watch' | 'ignore'>('watch');
  const [customSelector, setCustomSelector] = useState<string>('');
  const [customLabel, setCustomLabel] = useState<string>('');

  const imgRef = useRef<HTMLImageElement>(null);
  const [scale, setScale] = useState<{ x: number; y: number }>({ x: 1, y: 1 });

  const loadPickerData = async () => {
    setLoading(true);
    setError(null);
    setImageError(false);
    try {
      const data = await api.getPicker(monitorId);
      setPickerData(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load visual picker data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPickerData();
  }, [monitorId]);

  useEffect(() => {
    setRules(
      initialRules.map((r) => ({
        rule_type: r.rule_type,
        css_selector: r.css_selector,
        label: r.label || undefined,
      }))
    );
  }, [initialRules]);

  // Recalculate overlay coordinate scaling on image resize
  const updateScale = () => {
    if (imgRef.current && pickerData) {
      const renderedWidth = imgRef.current.clientWidth;
      const renderedHeight = imgRef.current.clientHeight;
      setScale({
        x: renderedWidth / (pickerData.width || 1440),
        y: renderedHeight / (pickerData.height || 900),
      });
    }
  };

  useEffect(() => {
    window.addEventListener('resize', updateScale);
    return () => window.removeEventListener('resize', updateScale);
  }, [pickerData]);

  const handleAddRule = (selector: string, label: string, mode: 'watch' | 'ignore') => {
    if (!selector.trim()) return;
    const trimmed = selector.trim();
    const existingIndex = rules.findIndex((r) => r.css_selector === trimmed);
    if (existingIndex !== -1) {
      if (rules[existingIndex].rule_type !== mode) {
        const updated = [...rules];
        updated[existingIndex] = { ...updated[existingIndex], rule_type: mode };
        setRules(updated);
        setError(null);
      } else {
        setError(`Rule for selector "${trimmed}" is already active as ${mode.toUpperCase()}.`);
      }
      return;
    }
    setError(null);
    setRules([...rules, { rule_type: mode, css_selector: trimmed, label: label.trim() || undefined }]);
  };

  const handleRemoveRule = (index: number) => {
    setRules(rules.filter((_, i) => i !== index));
  };

  const handleSaveRules = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await api.updateRules(monitorId, rules);
      onRulesSaved(updated);
      setSuccess('Target region rules updated successfully.');
      setTimeout(() => setSuccess(null), 3500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save rules');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl overflow-hidden shadow-sm space-y-0">
      {/* Header Bar */}
      <div className="p-5 border-b border-[#E2E8F0] bg-slate-50/70 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center font-semibold">
            <Crosshair className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#0F172A]">Visual Region Picker & Rules</h3>
            <p className="text-[11px] text-[#64748B]">
              Click elements on the screenshot overlay to watch specific areas or ignore noise
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={loadPickerData}
            disabled={loading}
            className="p-2 text-[#64748B] hover:text-[#0F172A] hover:bg-slate-200 rounded-lg transition-colors"
            title="Refresh picker elements"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={handleSaveRules}
            disabled={saving}
            className="inline-flex items-center space-x-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm transition-all"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{saving ? 'Saving Rules...' : 'Save Rules'}</span>
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="mx-5 mt-4 p-3.5 bg-rose-50 border border-rose-200 rounded-lg flex items-center space-x-2.5 text-rose-700 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="mx-5 mt-4 p-3.5 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center space-x-2.5 text-emerald-700 text-xs">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {/* Main Grid: Visual Overlay (left) + Rules Manager (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-5">
        {/* Left Column: Interactive Screenshot Overlay */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between text-xs text-[#64748B]">
            <span className="font-semibold text-[#0F172A]">Interactive Screenshot Viewport</span>
            <div className="flex items-center space-x-2">
              <span className="inline-flex items-center space-x-1 text-[11px] text-emerald-700 font-medium">
                <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500/50 border border-emerald-600 inline-block"></span>
                <span>Watch Rule</span>
              </span>
              <span className="inline-flex items-center space-x-1 text-[11px] text-amber-700 font-medium">
                <span className="w-2.5 h-2.5 rounded-sm bg-amber-500/50 border border-amber-600 inline-block"></span>
                <span>Ignore Rule</span>
              </span>
            </div>
          </div>

          <div className="relative border border-[#CBD5E1] rounded-xl overflow-hidden bg-slate-900 shadow-inner flex items-center justify-center min-h-[400px]">
            {loading && (
              <div className="absolute inset-0 z-30 bg-white/80 backdrop-blur-xs flex flex-col items-center justify-center text-[#64748B]">
                <RefreshCw className="w-6 h-6 animate-spin text-blue-600 mb-2" />
                <p className="text-xs font-medium">Analyzing DOM elements and geometry...</p>
              </div>
            )}

            {!loading && (error || !pickerData?.screenshot_url || imageError) && (
              <div className="p-8 text-center flex flex-col items-center justify-center max-w-md mx-auto text-white z-20">
                <div className="w-12 h-12 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center mb-3 text-rose-400">
                  <AlertCircle className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-semibold text-white">
                  {imageError ? 'Screenshot failed to render' : 'Target page preview unavailable'}
                </h4>
                <p className="text-xs text-slate-400 mt-1 mb-4 leading-relaxed">
                  {error || 'Unable to capture or display the screenshot artifact. You can retry loading or enter CSS selectors manually below.'}
                </p>
                <button
                  onClick={() => {
                    setImageError(false);
                    loadPickerData();
                  }}
                  className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Retry Capture</span>
                </button>
              </div>
            )}

            {!imageError && pickerData?.screenshot_url && (
              <div className="relative w-full">
                <img
                  ref={imgRef}
                  src={pickerData.screenshot_url}
                  alt="Picker target screenshot"
                  onLoad={() => {
                    setImageError(false);
                    updateScale();
                  }}
                  onError={() => {
                    setImageError(true);
                  }}
                  className="w-full h-auto block select-none"
                />

                {/* Interactive Element Bounding Box Overlays */}
                {pickerData.elements.map((el, idx) => {
                  const isWatched = rules.some((r) => r.rule_type === 'watch' && r.css_selector === el.selector);
                  const isIgnored = rules.some((r) => r.rule_type === 'ignore' && r.css_selector === el.selector);
                  const isHovered = hoveredElement?.selector === el.selector;

                  return (
                    <div
                      key={idx}
                      onMouseEnter={() => setHoveredElement(el)}
                      onMouseLeave={() => setHoveredElement(null)}
                      onClick={() => handleAddRule(el.selector, el.label, selectedMode)}
                      title={`Click to add as ${selectedMode.toUpperCase()} rule:\n${el.selector}`}
                      style={{
                        left: `${el.x * scale.x}px`,
                        top: `${el.y * scale.y}px`,
                        width: `${el.width * scale.x}px`,
                        height: `${el.height * scale.y}px`,
                      }}
                      className={`absolute cursor-pointer transition-all duration-75 z-10 ${
                        isWatched
                          ? 'border-2 border-emerald-500 bg-emerald-500/25 ring-2 ring-emerald-400/40'
                          : isIgnored
                          ? 'border-2 border-amber-500 bg-amber-500/25 ring-2 ring-amber-400/40'
                          : isHovered
                          ? 'border-2 border-blue-500 bg-blue-500/30 ring-2 ring-blue-300'
                          : 'border border-blue-400/20 hover:border-blue-400 hover:bg-blue-400/10'
                      }`}
                    />
                  );
                })}
              </div>
            )}
          </div>

          {/* Hovered Element Bar */}
          <div className="p-2.5 bg-slate-50 border border-[#E2E8F0] rounded-lg text-xs flex items-center justify-between">
            <span className="text-[#64748B]">
              {hoveredElement ? (
                <span>
                  Element: <code className="font-mono text-[#0F172A] font-semibold">{hoveredElement.selector}</code> (
                  {hoveredElement.label})
                </span>
              ) : (
                'Hover over any highlighted element on the screenshot to preview its selector.'
              )}
            </span>
            {hoveredElement && (
              <button
                onClick={() => handleAddRule(hoveredElement.selector, hoveredElement.label, selectedMode)}
                className="text-[11px] font-semibold text-blue-600 hover:text-blue-800"
              >
                + Add as {selectedMode.toUpperCase()}
              </button>
            )}
          </div>
        </div>

        {/* Right Column: Rule Management Panel */}
        <div className="space-y-5">
          {/* Add Rule Selector Mode */}
          <div className="bg-slate-50 border border-[#E2E8F0] rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#0F172A]">Click Action Mode</span>
              <span className="text-[10px] text-[#64748B]">Target when clicking screenshot</span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setSelectedMode('watch')}
                className={`py-2 px-3 rounded-lg text-xs font-semibold border flex items-center justify-center space-x-1.5 transition-all ${
                  selectedMode === 'watch'
                    ? 'border-emerald-500 bg-emerald-50 text-emerald-700 shadow-sm'
                    : 'border-[#CBD5E1] bg-white text-[#64748B] hover:bg-slate-100'
                }`}
              >
                <Eye className="w-3.5 h-3.5 text-emerald-600" />
                <span>Watch Region</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedMode('ignore')}
                className={`py-2 px-3 rounded-lg text-xs font-semibold border flex items-center justify-center space-x-1.5 transition-all ${
                  selectedMode === 'ignore'
                    ? 'border-amber-500 bg-amber-50 text-amber-700 shadow-sm'
                    : 'border-[#CBD5E1] bg-white text-[#64748B] hover:bg-slate-100'
                }`}
              >
                <EyeOff className="w-3.5 h-3.5 text-amber-600" />
                <span>Ignore Noise</span>
              </button>
            </div>
          </div>

          {/* Manual CSS Selector Form */}
          <div className="bg-slate-50 border border-[#E2E8F0] rounded-xl p-4 space-y-3 text-xs">
            <span className="font-semibold text-[#0F172A] block">Manual CSS Selector</span>

            <div className="space-y-2">
              <input
                type="text"
                placeholder="CSS Selector (e.g. #price, .stock, #timestamp)"
                value={customSelector}
                onChange={(e) => setCustomSelector(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-[#CBD5E1] rounded-lg font-mono text-[11px] text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <input
                type="text"
                placeholder="Label / Description (Optional)"
                value={customLabel}
                onChange={(e) => setCustomLabel(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-[#CBD5E1] rounded-lg text-[11px] text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={() => {
                  handleAddRule(customSelector, customLabel, selectedMode);
                  setCustomSelector('');
                  setCustomLabel('');
                }}
                disabled={!customSelector.trim()}
                className="w-full py-1.5 bg-slate-800 hover:bg-slate-900 disabled:opacity-40 text-white font-medium rounded-lg flex items-center justify-center space-x-1 text-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add {selectedMode === 'watch' ? 'Watch' : 'Ignore'} Rule</span>
              </button>
            </div>
          </div>

          {/* Active Rules List */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-1.5 text-xs font-semibold text-[#0F172A]">
                <Layers className="w-4 h-4 text-blue-600" />
                <span>Active Region Rules ({rules.length})</span>
              </div>
            </div>

            {rules.length === 0 ? (
              <p className="text-xs text-[#64748B] py-2">
                No custom region rules configured. The monitor will capture all body text.
              </p>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {rules.map((r, idx) => (
                  <div
                    key={idx}
                    className={`p-2.5 rounded-lg border text-xs flex items-center justify-between ${
                      r.rule_type === 'watch'
                        ? 'border-emerald-200 bg-emerald-50/50'
                        : 'border-amber-200 bg-amber-50/50'
                    }`}
                  >
                    <div className="min-w-0 flex-1 pr-2">
                      <div className="flex items-center space-x-1.5 mb-0.5">
                        <span
                          className={`uppercase text-[9px] font-bold px-1.5 py-0.5 rounded ${
                            r.rule_type === 'watch'
                              ? 'bg-emerald-200 text-emerald-800'
                              : 'bg-amber-200 text-amber-800'
                          }`}
                        >
                          {r.rule_type}
                        </span>
                        {r.label && <span className="font-semibold text-[#0F172A] truncate">{r.label}</span>}
                      </div>
                      <div className="font-mono text-[11px] text-[#475569] truncate">{r.css_selector}</div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleRemoveRule(idx)}
                      className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors"
                      title="Remove rule"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
