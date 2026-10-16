import React, { useState, useEffect } from 'react';
import { X, Globe, AlertCircle, Loader2, Sparkles } from 'lucide-react';
import { CreateMonitorInput, SensitivityLevel } from '../types';

interface AddMonitorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (input: CreateMonitorInput) => Promise<void>;
  isJudge?: boolean;
  maxMonitorsReached?: boolean;
}

export const AddMonitorModal: React.FC<AddMonitorModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  isJudge = false,
  maxMonitorsReached = false,
}) => {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [intervalMinutes, setIntervalMinutes] = useState<number>(30);
  const [sensitivity, setSensitivity] = useState<SensitivityLevel>('medium');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Close on ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (isJudge && maxMonitorsReached) {
      setError('Maximum 2 monitors allowed for temporary evaluation session. Please remove an existing monitor first.');
      return;
    }

    const trimmedName = name.trim();
    const trimmedUrl = url.trim();

    if (!trimmedName) {
      setError('Please provide a name or label for this monitor.');
      return;
    }

    if (!trimmedUrl) {
      setError('Please enter a target webpage URL.');
      return;
    }

    if (!trimmedUrl.startsWith('http://') && !trimmedUrl.startsWith('https://')) {
      setError('URL must start with http:// or https://');
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit({
        name: trimmedName,
        url: trimmedUrl,
        interval_minutes: intervalMinutes,
        sensitivity,
      });
      // Reset form
      setName('');
      setUrl('');
      setIntervalMinutes(30);
      setSensitivity('medium');
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create monitor.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUseFixture = () => {
    if (isJudge) {
      setName('Example Domain');
      setUrl('https://example.com');
      setIntervalMinutes(15);
      setSensitivity('medium');
      setError(null);
    } else {
      setName('AcuTime Chronometer Fixture');
      setUrl(`http://127.0.0.1:8000/fixture/product`);
      setIntervalMinutes(15);
      setSensitivity('medium');
      setError(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#141210]/80 backdrop-blur-md animate-in fade-in">
      <div 
        className="bg-[#211D19] rounded-2xl max-w-lg w-full shadow-luxury border border-[#40372D] overflow-hidden text-left"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#40372D] flex items-center justify-between bg-[#1A1714]">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#342B20] border border-[#C5A474]/30 text-[#C5A474] flex items-center justify-center">
              <Globe className="w-4 h-4" />
            </div>
            <div>
              <h2 id="modal-title" className="font-serif text-base font-medium text-[#F5EFE5]">
                {isJudge ? 'Add Website (Judge Evaluation)' : 'Add Website Monitor'}
              </h2>
              <p className="text-xs text-[#8F8579] font-sans">
                {isJudge
                  ? 'Enter any safe public HTTP/HTTPS URL (max 2 monitors, min 15m interval)'
                  : 'Configure target URL, check schedule and sensitivity'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={submitting}
            className="text-[#8F8579] hover:text-[#F5EFE5] p-1.5 rounded-lg hover:bg-[#2A2520] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 font-sans">
          {error && (
            <div className="p-3 rounded-lg bg-[#ED7777]/10 border border-[#ED7777]/30 text-xs text-[#ED7777] flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-[#ED7777]" />
              <span>{error}</span>
            </div>
          )}

          {/* Quick preset chip */}
          <div className="flex items-center justify-between pb-1">
            <span className="text-xs text-[#8F8579] font-medium">Quick Preset:</span>
            <button
              type="button"
              onClick={handleUseFixture}
              className="inline-flex items-center space-x-1 text-xs text-[#C5A474] hover:text-[#D8BB8E] font-medium bg-[#342B20] border border-[#C5A474]/30 px-2.5 py-1 rounded-md transition-colors"
            >
              <Sparkles className="w-3 h-3" />
              <span>{isJudge ? 'Load example.com' : 'Load Local Test Fixture'}</span>
            </button>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#BDB3A7] mb-1.5">
              Monitor Name / Label
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Competitor Pricing, Product Launch Page"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={submitting}
              className="w-full px-3 py-2 text-sm bg-[#141210] border border-[#40372D] rounded-lg text-[#F5EFE5] placeholder-[#8F8579] focus:outline-none focus:ring-1 focus:ring-[#C5A474] focus:border-[#C5A474] transition-all"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[#BDB3A7] mb-1.5">
              Target Webpage URL
            </label>
            <input
              type="url"
              required
              placeholder="https://example.com/pricing"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={submitting}
              className="w-full px-3 py-2 text-sm bg-[#141210] border border-[#40372D] rounded-lg text-[#F5EFE5] placeholder-[#8F8579] focus:outline-none focus:ring-1 focus:ring-[#C5A474] focus:border-[#C5A474] transition-all font-mono text-xs"
            />
            <p className="text-[11px] text-[#8F8579] mt-1">
              Protected against SSRF. Internal RFC1918 and metadata endpoints are blocked.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-[#BDB3A7] mb-1.5">
                Check Frequency
              </label>
              <select
                value={intervalMinutes}
                onChange={(e) => setIntervalMinutes(Number(e.target.value))}
                disabled={submitting}
                className="w-full px-3 py-2 text-sm bg-[#141210] border border-[#40372D] rounded-lg text-[#F5EFE5] focus:outline-none focus:ring-1 focus:ring-[#C5A474] transition-all"
              >
                <option value={15}>Every 15 minutes</option>
                <option value={30}>Every 30 minutes</option>
                <option value={60}>Every 1 hour</option>
                <option value={360}>Every 6 hours</option>
                <option value={1440}>Every 24 hours</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-[#BDB3A7] mb-1.5">
                Sensitivity
              </label>
              <select
                value={sensitivity}
                onChange={(e) => setSensitivity(e.target.value as SensitivityLevel)}
                disabled={submitting}
                className="w-full px-3 py-2 text-sm bg-[#141210] border border-[#40372D] rounded-lg text-[#F5EFE5] focus:outline-none focus:ring-1 focus:ring-[#C5A474] transition-all"
              >
                <option value="high">High (immediate change)</option>
                <option value="medium">Medium (standard)</option>
                <option value="low">Low (significant changes)</option>
              </select>
            </div>
          </div>

          {/* Footer Actions */}
          <div className="pt-4 border-t border-[#40372D] flex items-center justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-xs font-medium text-[#8F8579] hover:text-[#F5EFE5] hover:bg-[#2A2520] rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center space-x-2 bg-[#C5A474] hover:bg-[#D8BB8E] disabled:opacity-50 text-[#141210] text-xs font-semibold px-4 py-2 rounded-lg shadow-gold transition-all"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Validating & Saving...</span>
                </>
              ) : (
                <span>Save & Start Monitoring</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddMonitorModal;
