"use client";

import React, { useState, useRef, useEffect } from "react";
import { Zap, Cpu, ChevronDown, Check } from "lucide-react";
import { useAppStore, LLMModelChoice } from "@/store/useAppStore";

interface ModelSelectorProps {
  sessionId?: string;
  className?: string;
}

interface ModelOption {
  id: LLMModelChoice;
  name: string;
  badge: string;
  tagline: string;
  icon: React.ComponentType<{ className?: string }>;
}

const MODEL_OPTIONS: ModelOption[] = [
  {
    id: "groq",
    name: "Groq",
    badge: "Cloud",
    tagline: "Faster, cloud-based",
    icon: Zap,
  },
  {
    id: "ollama",
    name: "Ollama",
    badge: "Local",
    tagline: "Local, more private, possibly slower",
    icon: Cpu,
  },
];

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  sessionId,
  className = "",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const activeSessionId = useAppStore((state) => state.activeSessionId);
  const targetSessionId = sessionId || activeSessionId;

  const currentModel = useAppStore((state) =>
    state.getSessionModel(targetSessionId)
  );
  const setSessionModel = useAppStore((state) => state.setSessionModel);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const activeOption =
    MODEL_OPTIONS.find((opt) => opt.id === currentModel) || MODEL_OPTIONS[0];
  const ActiveIcon = activeOption.icon;

  const handleSelect = (modelId: LLMModelChoice) => {
    if (targetSessionId) {
      setSessionModel(targetSessionId, modelId);
    }
    setIsOpen(false);
  };

  return (
    <div ref={dropdownRef} className={`relative inline-block ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium text-slate-700 hover:text-slate-900 bg-slate-100/90 hover:bg-slate-200/80 border border-slate-200/80 transition-all cursor-pointer shadow-2xs"
        title="Choose language model for this conversation"
        aria-label="Model selector"
        aria-expanded={isOpen}
      >
        <ActiveIcon
          className={`w-3.5 h-3.5 ${
            activeOption.id === "groq" ? "text-amber-500" : "text-humsafar-teal"
          }`}
        />
        <span className="font-semibold text-slate-800">{activeOption.name}</span>
        <span className="text-[10px] text-slate-600 bg-white/80 px-1.5 py-0.5 rounded-sm border border-slate-200/60 font-medium">
          {activeOption.badge}
        </span>
        <ChevronDown
          className={`w-3 h-3 text-slate-600 transition-transform duration-150 ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {isOpen && (
        <div className="absolute right-0 bottom-full mb-2 w-64 bg-white rounded-xl shadow-lg border border-slate-200 p-1.5 z-50 animate-in fade-in zoom-in-95 duration-100">
          <div className="px-2 py-1 text-[10px] font-semibold tracking-wider uppercase text-slate-600 border-b border-slate-100 mb-1">
            Conversation Model
          </div>
          <div className="flex flex-col gap-1">
            {MODEL_OPTIONS.map((opt) => {
              const Icon = opt.icon;
              const isSelected = opt.id === currentModel;
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => handleSelect(opt.id)}
                  className={`w-full flex items-start gap-2.5 p-2 rounded-lg text-left transition-all cursor-pointer ${
                    isSelected
                      ? "bg-slate-100/90 text-slate-900 ring-1 ring-slate-300"
                      : "hover:bg-slate-50 text-slate-700"
                  }`}
                >
                  <div
                    className={`p-1.5 rounded-md mt-0.5 shrink-0 ${
                      opt.id === "groq"
                        ? "bg-amber-100 text-amber-600"
                        : "bg-teal-100 text-teal-700"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-semibold text-slate-800">
                        {opt.name}
                      </span>
                      <span className="text-[10px] text-slate-600 bg-slate-100 px-1 rounded border border-slate-200/60 font-medium">
                        {opt.badge}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-600 leading-snug mt-0.5">
                      {opt.tagline}
                    </p>
                  </div>
                  {isSelected && (
                    <Check className="w-3.5 h-3.5 text-humsafar-teal shrink-0 mt-1" />
                  )}
                </button>
              );
            })}
          </div>
          <div className="mt-1.5 pt-1.5 border-t border-slate-100 px-2 text-[10px] text-slate-500 leading-tight">
            Affects subsequent messages in this chat. Earlier messages remain untouched.
          </div>
        </div>
      )}
    </div>
  );
};
