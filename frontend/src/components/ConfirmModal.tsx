import React from 'react';
import { AlertTriangle } from 'lucide-react';

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  confirmVariant?: 'danger' | 'primary';
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  title,
  message,
  confirmText = 'Delete',
  confirmVariant = 'danger',
  loading = false,
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
      <div
        className="bg-surface-elevated rounded-2xl border border-warmborder shadow-luxury max-w-md w-full p-6 space-y-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <div className="flex items-start space-x-3.5">
          <div className="p-2.5 rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20 shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <h3 id="modal-title" className="text-base font-serif font-medium text-ivory-warm">
              {title}
            </h3>
            <p className="text-xs text-text-subtle mt-1 leading-relaxed">{message}</p>
          </div>
        </div>

        <div className="flex items-center justify-end space-x-2 pt-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-xs font-medium text-ivory-warm bg-surface-interactive border border-warmborder rounded-xl hover:bg-surface-elevated disabled:opacity-40 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={`px-4 py-2 text-xs font-medium rounded-xl transition-all disabled:opacity-40 ${
              confirmVariant === 'danger'
                ? 'bg-rose-600/90 hover:bg-rose-600 text-white shadow-luxury'
                : 'bg-gold-champagne hover:bg-gold-hover text-obsidian-deep shadow-gold'
            }`}
          >
            {loading ? 'Processing...' : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};
