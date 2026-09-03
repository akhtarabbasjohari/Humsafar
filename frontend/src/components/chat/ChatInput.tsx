"use client";

import React, { useState } from "react";
import { ArrowUp, Square } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop: () => void;
  isStreaming?: boolean;
}

const STARTER_PROMPTS = [
  "Autumn foliage tour in Hunza Valley",
  "K2 Base Camp expedition requirements",
  "Fairy Meadows 5-day trekking plan",
  "Skardu cultural and lake tour",
];

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onStop,
  isStreaming = false,
}) => {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isStreaming) {
      onStop();
      return;
    }
    if (input.trim()) {
      onSend(input);
      setInput("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="sticky bottom-0 w-full bg-gradient-to-t from-white via-white/95 to-transparent pt-3 pb-5 sm:pb-7 px-4 sm:px-6 z-20">
      <div className="max-w-chat mx-auto space-y-3">
        {/* Starter Prompt Chips */}
        {!isStreaming && (
          <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs no-scrollbar">
            <span className="text-xs font-medium text-humsafar-mutedText shrink-0 mr-0.5">
              Popular inquiries:
            </span>
            {STARTER_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setInput(`Tell me about: ${prompt}`)}
                className="px-3 py-1.5 rounded-full bg-slate-50 border border-slate-200 text-slate-700 text-xs font-medium hover:border-humsafar-teal hover:text-humsafar-navy hover:bg-white transition-colors shrink-0 shadow-subtle cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-humsafar-teal"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {/* Substantial, Confident Composer Box */}
        <form
          onSubmit={handleSubmit}
          className="relative bg-white border border-slate-300 rounded-xl shadow-composer focus-within:border-humsafar-teal focus-within:ring-2 focus-within:ring-humsafar-teal/20 transition-all p-2.5 sm:p-3"
        >
          <div className="flex items-end gap-2.5">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              disabled={isStreaming}
              placeholder={
                isStreaming
                  ? "Humsafar is synthesizing verified itinerary data..."
                  : "Ask about trekking routes, seasons, permits, or custom itineraries..."
              }
              className="flex-1 resize-none bg-transparent border-none text-[15px] text-humsafar-bodyText placeholder-slate-400 focus:outline-none focus:ring-0 leading-relaxed py-1 px-1.5 disabled:opacity-60"
            />

            {/* Stop or Send Action Button */}
            {isStreaming ? (
              <Button
                type="button"
                variant="stop"
                size="sm"
                onClick={onStop}
                icon={<Square className="w-3.5 h-3.5 fill-current" />}
                className="shrink-0 mb-0.5"
              >
                Stop generating
              </Button>
            ) : (
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={!input.trim()}
                className="!rounded-lg px-3.5 py-2 shrink-0 mb-0.5"
                icon={<ArrowUp className="w-4 h-4" />}
                title="Send message"
              >
                Send
              </Button>
            )}
          </div>
        </form>

        <p className="text-center text-xs text-humsafar-mutedText">
          Live data sourced from <span className="font-medium text-humsafar-navy">itp.7scribes.com</span>. Custom drafted itineraries require traveler approval.
        </p>
      </div>
    </div>
  );
};
