"use client";

import React, { useState } from "react";
import { Plus, ArrowUp, Square, Mic, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop: () => void;
  isStreaming?: boolean;
  inputText?: string;
  setInputText?: (val: string) => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onStop,
  isStreaming = false,
  inputText,
  setInputText,
}) => {
  const [localInput, setLocalInput] = useState("");
  const input = inputText !== undefined ? inputText : localInput;
  const setInputValue = setInputText || setLocalInput;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isStreaming) {
      onStop();
      return;
    }
    if (input.trim()) {
      onSend(input);
      setInputValue("");
    }
  };


  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="sticky bottom-0 w-full bg-gradient-to-t from-white via-white/95 to-transparent pt-3 pb-4 sm:pb-6 px-4 sm:px-6 z-20">
      <div className="max-w-chat mx-auto space-y-2">
        {/* Floating Claude-Style Composer */}
        <form
          onSubmit={handleSubmit}
          className="relative bg-white border border-slate-300/90 rounded-2xl shadow-composer focus-within:border-humsafar-teal focus-within:ring-2 focus-within:ring-humsafar-teal/20 transition-all p-2 sm:p-2.5"
        >
          <div className="flex items-center gap-2">
            {/* + Button for Expedition Preferences / Attachments */}
            <button
              type="button"
              title="Add expedition details (budget, dates, fitness)"
              className="p-1.5 text-slate-500 hover:text-humsafar-navy hover:bg-slate-100 rounded-lg transition-colors cursor-pointer shrink-0"
            >
              <Plus className="w-4 h-4" />
            </button>

            {/* Expanding Textarea */}
            <textarea
              value={input}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isStreaming}
              placeholder={
                isStreaming
                  ? "Humsafar is synthesizing verified itinerary data..."
                  : "Write a message..."
              }
              className="flex-1 resize-none bg-transparent border-none text-[15px] text-humsafar-bodyText placeholder-slate-400 focus:outline-none focus:ring-0 leading-relaxed py-1.5 px-1 max-h-36 overflow-y-auto disabled:opacity-60"
            />

            {/* Right Action Icons: Mic + Send/Stop */}
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg transition-colors cursor-pointer hidden sm:inline-flex"
                title="Voice input"
              >
                <Mic className="w-4 h-4" />
              </button>

              {isStreaming ? (
                <button
                  type="button"
                  onClick={onStop}
                  className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-humsafar-navy border border-slate-300 transition-colors cursor-pointer"
                  title="Stop generating"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  className="p-2 rounded-xl bg-humsafar-teal hover:bg-humsafar-tealHover disabled:opacity-30 disabled:pointer-events-none text-white transition-all shadow-xs cursor-pointer"
                  title="Send message"
                >
                  <ArrowUp className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        </form>

        {/* Footer: Disclaimer + Tech Stack Model Indicator (Claude Style) */}
        <div className="flex items-center justify-between text-[11px] text-slate-500 px-1 pt-0.5">
          <p className="truncate">
            Humsafar is AI grounded in live data from <span className="font-medium text-slate-700">askoliadventure.com</span>.
          </p>

          <div className="flex items-center gap-1.5 text-slate-600 font-medium shrink-0 ml-3">
            <span className="w-1.5 h-1.5 rounded-full bg-humsafar-teal" />
            <span>Groq LLaMA 3.3 70B</span>
          </div>
        </div>
      </div>
    </div>
  );
};
