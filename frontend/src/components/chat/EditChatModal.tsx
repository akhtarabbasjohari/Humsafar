"use client";

import React, { useState, useEffect, useRef } from "react";
import { X, Pencil } from "lucide-react";

interface EditChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentTitle: string;
  onSave: (newTitle: string) => void;
}

export const EditChatModal: React.FC<EditChatModalProps> = ({
  isOpen,
  onClose,
  currentTitle,
  onSave,
}) => {
  const [title, setTitle] = useState(currentTitle);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTitle(currentTitle);
      setTimeout(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      }, 50);
    }
  }, [isOpen, currentTitle]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = title.trim();
    if (trimmed) {
      onSave(trimmed);
      onClose();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
    }
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
        <div className="bg-humsafar-navy px-5 py-3.5 flex items-center justify-between text-white">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-white/10 flex items-center justify-center">
              <Pencil className="w-3.5 h-3.5 text-humsafar-teal" />
            </div>
            <div>
              <h3 className="font-semibold text-sm">Rename Expedition Chat</h3>
              <p className="text-[11px] text-white/70">Update the title for this planning session</p>
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
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label htmlFor="chat-title-input" className="block text-xs font-semibold text-humsafar-navy mb-1.5">
              Chat Title
            </label>
            <div className="relative">
              <input
                id="chat-title-input"
                ref={inputRef}
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={80}
                placeholder="e.g. 5-Day K2 Expedition Plan"
                className="w-full text-xs sm:text-sm font-medium text-slate-800 px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-humsafar-teal focus:border-transparent bg-white shadow-xs"
              />
              <span className="absolute right-2.5 top-2.5 text-[10px] text-slate-400 font-mono">
                {title.length}/80
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-1.5">
              A clear title helps you easily identify this route in your expedition list.
            </p>
          </div>

          {/* Modal Actions */}
          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!title.trim() || title.trim() === currentTitle}
              className="px-4 py-1.5 text-xs font-semibold text-white bg-humsafar-teal hover:bg-humsafar-tealHover disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-xs transition-colors cursor-pointer"
            >
              Save Changes
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
