"use client";

import React, { useState } from "react";
import { ArrowUp, Sparkles, MapPin, Mountain, Compass, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface ChatInputProps {
  onSend?: (message: string) => void;
}

const QUICK_SUGGESTIONS = [
  { label: "Autumn in Hunza", icon: MapPin },
  { label: "K2 Base Camp Expedition", icon: Mountain },
  { label: "Fairy Meadows 5-Day Trek", icon: Compass },
  { label: "Skardu & Deosai Plains", icon: Sparkles },
];

export const ChatInput: React.FC<ChatInputProps> = ({ onSend }) => {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && onSend) {
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
    <div className="sticky bottom-0 w-full bg-gradient-to-t from-humsafar-background via-humsafar-background/95 to-transparent pt-3 pb-4 sm:pb-6 px-4 sm:px-6 z-20">
      <div className="max-w-4xl mx-auto space-y-2.5">
        {/* Quick Suggestion Chips (Claude/Kimi Pattern) */}
        <div className="flex items-center gap-1.5 sm:gap-2 overflow-x-auto pb-1 text-xs no-scrollbar">
          <span className="text-[11px] font-semibold text-humsafar-mutedText uppercase tracking-wider shrink-0 mr-1 flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-humsafar-accent" />
            Suggested:
          </span>
          {QUICK_SUGGESTIONS.map((chip, idx) => {
            const Icon = chip.icon;
            return (
              <button
                key={idx}
                type="button"
                onClick={() => setInput(`Tell me about planning a ${chip.label}`)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-humsafar-subtleBorder text-humsafar-slate text-xs font-medium hover:border-humsafar-mainButton hover:text-humsafar-header hover:bg-humsafar-surfaceParchment transition-all duration-150 shrink-0 shadow-subtle cursor-pointer"
              >
                <Icon className="w-3 h-3 text-humsafar-accent" />
                <span>{chip.label}</span>
              </button>
            );
          })}
        </div>

        {/* Floating Chat Input Container */}
        <form
          onSubmit={handleSubmit}
          className="relative bg-white border border-humsafar-subtleBorder rounded-2xl shadow-floating focus-within:border-humsafar-mainButton focus-within:ring-2 focus-within:ring-humsafar-mainButton/15 transition-all duration-150 p-2 sm:p-2.5"
        >
          <div className="flex items-end gap-2">
            {/* Action/Filter Icon in #D89B32 accent */}
            <button
              type="button"
              title="Expedition filters (dates, fitness, budget)"
              className="p-2 text-humsafar-accent hover:text-humsafar-accent/80 hover:bg-humsafar-surfaceParchment rounded-xl transition-colors shrink-0 mb-0.5 cursor-pointer"
            >
              <SlidersHorizontal className="w-4 h-4" />
            </button>

            {/* Expanding Textarea */}
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              placeholder="Ask Humsafar anything... (e.g., 'Plan a 10-day family tour across Skardu and Hunza in July')"
              className="flex-1 resize-none bg-transparent border-none text-sm text-humsafar-charcoal placeholder-humsafar-mutedText/70 focus:outline-none focus:ring-0 leading-relaxed py-1.5 px-1"
            />

            {/* Main Send Button in #0B6B50 */}
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={!input.trim()}
              className="!rounded-xl px-3 sm:px-3.5 py-2.5 shrink-0 mb-0.5"
              icon={<ArrowUp className="w-4 h-4" />}
            >
              <span className="hidden sm:inline">Send</span>
            </Button>
          </div>
        </form>

        {/* Disclaimer / Grounding Guarantee */}
        <p className="text-center text-[11px] text-humsafar-mutedText">
          Humsafar grounds all itineraries in live data from{" "}
          <span className="font-medium text-humsafar-slate underline decoration-dotted">itp.7scribes.com</span>. Custom drafts require your explicit approval.
        </p>
      </div>
    </div>
  );
};
