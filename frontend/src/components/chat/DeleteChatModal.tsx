"use client";

import React from "react";
import { X, Trash2, AlertTriangle } from "lucide-react";

interface DeleteChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionTitle: string;
  onConfirm: () => void;
}

export const DeleteChatModal: React.FC<DeleteChatModalProps> = ({
  isOpen,
  onClose,
  sessionTitle,
  onConfirm,
}) => {
  if (!isOpen) return null;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
    }
  };

  const handleDelete = () => {
    onConfirm();
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs transition-opacity"
      onClick={onClose}
      onKeyDown={handleKeyDown}
    >
      <div
        className="w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-xl overflow-hidden transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="bg-rose-950/90 px-5 py-3.5 flex items-center justify-between text-white">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-rose-500/20 flex items-center justify-center">
              <Trash2 className="w-3.5 h-3.5 text-rose-300" />
            </div>
            <div>
              <h3 className="font-semibold text-sm text-white">Delete Expedition Chat</h3>
              <p className="text-[11px] text-rose-200/80">Permanent chat removal</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-white/70 hover:text-white hover:bg-white/10 rounded-md transition-colors cursor-pointer"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 space-y-3">
          <div className="flex items-start gap-3 p-3 rounded-xl bg-rose-50/70 border border-rose-100">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div className="text-xs text-rose-900 leading-relaxed">
              Are you sure you want to delete this expedition chat?
              <div className="font-semibold text-rose-950 mt-1 truncate max-w-xs">
                "{sessionTitle}"
              </div>
            </div>
          </div>

          <p className="text-[11px] text-slate-500 leading-relaxed">
            All messages, research hops, and route plans discussed in this session will be permanently deleted. This action cannot be undone.
          </p>

          {/* Modal Actions */}
          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleDelete}
              className="px-4 py-1.5 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-xs transition-colors cursor-pointer"
            >
              Delete Chat
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
