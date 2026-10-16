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
    <div className="bg-surface-elevated border border-warmborder rounded-2xl overflow-hidden shadow-luxury space-y-0">
      {/* Header Bar */}
      <div className="p-5 border-b border-warmborder bg-obsidian-deep/80 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-gold-champagne/15 text-gold-champagne flex items-center justify-center border border-gold-champagne/25 shadow-gold">
            <Crosshair className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-serif font-medium text-ivory-warm">Visual Region Picker & DOM Scoping</h3>
            <p className="text-[11px] text-text-subtle">
              Click elements on the screenshot overlay to watch specific areas or ignore noise
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={loadPickerData}
            disabled={loading}
            className="p-2 text-text-subtle hover:text-ivory-warm hover:bg-surface-interactive rounded-xl border border-transparent hover:border-warmborder transition-all"
            title="Refresh picker elements"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-gold-champagne' : ''}`} />
          </button>
          <button
            onClick={handleSaveRules}
            disabled={saving}
            className="inline-flex items-center space-x-1.5 bg-gold-champagne hover:bg-gold-hover disabled:opacity-50 text-obsidian-deep text-xs font-medium px-4 py-2 rounded-xl shadow-gold transition-all"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{saving ? 'Saving Rules...' : 'Save Rules'}</span>
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="mx-5 mt-4 p-3.5 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-center space-x-2.5 text-rose-400 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="mx-5 mt-4 p-3.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center space-x-2.5 text-emerald-400 text-xs">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {/* Main Grid: Visual Overlay (left) + Rules Manager (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-5">
        {/* Left Column: Interactive Screenshot Overlay */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between text-xs text-text-subtle">
            <span className="font-serif font-medium text-ivory-warm">Interactive Screenshot Viewport</span>
            <div className="flex items-center space-x-3">
              <span className="inline-flex items-center space-x-1.5 text-[11px] text-emerald-400 font-medium">
                <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500/30 border border-emerald-500 inline-block"></span>
                <span>Watch Region</span>
              </span>
              <span className="inline-flex items-center space-x-1.5 text-[11px] text-amber-400 font-medium">
                <span className="w-2.5 h-2.5 rounded-sm bg-amber-500/30 border border-amber-500 inline-block"></span>
                <span>Ignore Region</span>
              </span>
            </div>
          </div>

          <div className="relative border border-warmborder rounded-xl overflow-hidden bg-obsidian-base shadow-inner flex items-center justify-center min-h-[400px]">
            {loading && (
              <div className="absolute inset-0 z-30 bg-obsidian-base/80 backdrop-blur-xs flex flex-col items-center justify-center text-text-subtle">
                <RefreshCw className="w-6 h-6 animate-spin text-gold-champagne mb-2" />
                <p className="text-xs font-medium">Analyzing DOM elements and geometry...</p>
              </div>
            )}

            {!loading && (error || !pickerData?.screenshot_url || imageError) && (
              <div className="p-8 text-center flex flex-col items-center justify-center max-w-md mx-auto text-ivory-warm z-20">
                <div className="w-12 h-12 rounded-2xl bg-surface-elevated border border-warmborder flex items-center justify-center mb-3 text-rose-400 shadow-luxury">
                  <AlertCircle className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-serif font-medium text-ivory-warm">
                  {imageError ? 'Screenshot failed to render' : 'Target page preview unavailable'}
                </h4>
                <p className="text-xs text-text-subtle mt-1 mb-4 leading-relaxed">
                  {error || 'Unable to capture or display the screenshot artifact. You can retry loading or enter CSS selectors manually below.'}
                </p>
                <button
                  onClick={() => {
                    setImageError(false);
                    loadPickerData();
                  }}
                  className="inline-flex items-center space-x-1.5 px-4 py-2 bg-gold-champagne hover:bg-gold-hover text-obsidian-deep rounded-xl text-xs font-medium shadow-gold transition-all"
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
          <div className="p-3 bg-obsidian-deep/80 border border-warmborder rounded-xl text-xs flex items-center justify-between text-text-subtle">
            <span className="truncate mr-2">
              {hoveredElement ? (
                <span>
                  Element: <code className="font-mono text-gold-champagne font-medium">{hoveredElement.selector}</code>{' '}
                  <span className="text-text-muted">({hoveredElement.label})</span>
                </span>
              ) : (
                'Hover over any highlighted element on the screenshot to preview its selector.'
              )}
            </span>
            {hoveredElement && (
              <button
                onClick={() => handleAddRule(hoveredElement.selector, hoveredElement.label, selectedMode)}
                className="text-[11px] font-medium text-gold-champagne hover:text-gold-hover shrink-0 transition-colors"
              >
                + Add as {selectedMode.toUpperCase()}
              </button>
            )}
          </div>
        </div>

        {/* Right Column: Rule Management Panel */}
        <div className="space-y-5">
          {/* Add Rule Selector Mode */}
          <div className="bg-obsidian-deep/60 border border-warmborder rounded-xl p-4 space-y-3 shadow-luxury">
            <div className="flex items-center justify-between">
              <span className="text-xs font-serif font-medium text-ivory-warm">Click Action Mode</span>
              <span className="text-[10px] text-text-subtle">Target when clicking screenshot</span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setSelectedMode('watch')}
                className={`py-2 px-3 rounded-xl text-xs font-medium border flex items-center justify-center space-x-1.5 transition-all ${
                  selectedMode === 'watch'
                    ? 'border-emerald-500/50 bg-emerald-500/15 text-emerald-300 shadow-sm'
                    : 'border-warmborder bg-surface-interactive text-text-muted hover:text-ivory-warm'
                }`}
              >
                <Eye className="w-3.5 h-3.5 text-emerald-400" />
                <span>Watch Region</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedMode('ignore')}
                className={`py-2 px-3 rounded-xl text-xs font-medium border flex items-center justify-center space-x-1.5 transition-all ${
                  selectedMode === 'ignore'
                    ? 'border-amber-500/50 bg-amber-500/15 text-amber-300 shadow-sm'
                    : 'border-warmborder bg-surface-interactive text-text-muted hover:text-ivory-warm'
                }`}
              >
                <EyeOff className="w-3.5 h-3.5 text-amber-400" />
                <span>Ignore Noise</span>
              </button>
            </div>
          </div>

          {/* Manual CSS Selector Form */}
          <div className="bg-obsidian-deep/60 border border-warmborder rounded-xl p-4 space-y-3 text-xs shadow-luxury">
            <span className="font-serif font-medium text-ivory-warm block">Manual CSS Selector</span>

            <div className="space-y-2">
              <input
                type="text"
                placeholder="CSS Selector (e.g. #price, .stock, #timestamp)"
                value={customSelector}
                onChange={(e) => setCustomSelector(e.target.value)}
                className="w-full px-3 py-2 bg-surface-interactive border border-warmborder rounded-xl font-mono text-[11px] text-ivory-warm placeholder:text-text-subtle focus:outline-none focus:border-gold-champagne/60 transition-colors"
              />
              <input
                type="text"
                placeholder="Label / Description (Optional)"
                value={customLabel}
                onChange={(e) => setCustomLabel(e.target.value)}
                className="w-full px-3 py-2 bg-surface-interactive border border-warmborder rounded-xl text-[11px] text-ivory-warm placeholder:text-text-subtle focus:outline-none focus:border-gold-champagne/60 transition-colors"
              />
              <button
                type="button"
                onClick={() => {
                  handleAddRule(customSelector, customLabel, selectedMode);
                  setCustomSelector('');
                  setCustomLabel('');
                }}
                disabled={!customSelector.trim()}
                className="w-full py-2 bg-gold-champagne/15 hover:bg-gold-champagne/25 disabled:opacity-40 text-gold-champagne border border-gold-champagne/30 font-medium rounded-xl flex items-center justify-center space-x-1.5 text-xs transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add {selectedMode === 'watch' ? 'Watch' : 'Ignore'} Rule</span>
              </button>
            </div>
          </div>

          {/* Active Rules List */}
          <div className="bg-surface-elevated border border-warmborder rounded-xl p-4 shadow-luxury space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-xs font-serif font-medium text-ivory-warm">
                <Layers className="w-4 h-4 text-gold-champagne" />
                <span>Active Region Rules ({rules.length})</span>
              </div>
            </div>

            {rules.length === 0 ? (
              <p className="text-xs text-text-subtle py-2">
                No custom region rules configured. The monitor will capture all body text.
              </p>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {rules.map((r, idx) => (
                  <div
                    key={idx}
                    className={`p-2.5 rounded-xl border text-xs flex items-center justify-between transition-colors ${
                      r.rule_type === 'watch'
                        ? 'border-emerald-500/30 bg-emerald-950/20 text-ivory-warm'
                        : 'border-amber-500/30 bg-amber-950/20 text-ivory-warm'
                    }`}
                  >
                    <div className="min-w-0 flex-1 pr-2">
                      <div className="flex items-center space-x-2 mb-0.5">
                        <span
                          className={`uppercase text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded ${
                            r.rule_type === 'watch'
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                              : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                          }`}
                        >
                          {r.rule_type}
                        </span>
                        {r.label && <span className="font-medium text-ivory-warm truncate">{r.label}</span>}
                      </div>
                      <div className="font-mono text-[11px] text-text-muted truncate">{r.css_selector}</div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleRemoveRule(idx)}
                      className="p-1.5 text-text-subtle hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
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
