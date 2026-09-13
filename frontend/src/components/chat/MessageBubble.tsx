"use client";

import React from "react";
import clsx from "clsx";
import {
  Sparkles,
  Compass,
  Bookmark,
} from "lucide-react";
import { ConfidenceChip } from "@/components/ui/ConfidenceChip";
import { MarkdownContent } from "./MarkdownContent";
import { ItineraryCard } from "./ItineraryCard";

export interface DayScheduleItem {
  day: number;
  title: string;
  description: string;
  altitude?: string;
  stage?: string;
}

export interface ItineraryDraftData {
  title: string;
  region: string;
  days: number | string;
  grade?: string;
  estimatedPrice: string;
  highlights: string[];
  dayByDay?: DayScheduleItem[];
  inclusions?: string[];
  exclusions?: string[];
  equipment?: string[];
  contactDetails?: {
    company?: string;
    website?: string;
    email?: string;
    advisory?: string;
  };
  isApproved: boolean;
  confidenceType?: "official" | "unverified";
  confidenceLabel?: string;
  sourceUrl?: string;
  filename?: string;
}

export interface MessageProps {
  id: string;
  sender: "user" | "agent";
  content: string;
  timestamp: string;
  sessionId?: string;
  itineraryId?: string;
  isStreaming?: boolean;
  confidenceType?: "official" | "unverified";
  confidenceLabel?: string;
  sourceUrl?: string;
  itineraryDraft?: ItineraryDraftData;
  onApproveItinerary?: () => void;
  onRequestChanges?: (title?: string) => void;
  onSaveItinerary?: (itinerary: ItineraryDraftData) => void;
  isItinerarySaved?: boolean;
  isSavingItinerary?: boolean;
}

export const MessageBubble: React.FC<MessageProps> = ({
  sender,
  content,
  timestamp,
  sessionId,
  itineraryId,
  isStreaming,
  confidenceType,
  confidenceLabel,
  sourceUrl,
  itineraryDraft,
  onApproveItinerary,
  onRequestChanges,
  onSaveItinerary,
  isItinerarySaved = false,
  isSavingItinerary = false,
}) => {

  const isUser = sender === "user";

  // Defense-in-depth: strip any residual reasoning thought blocks or raw brackets from client display
  let displayContent = content
    ? content
        .replace(/<think>[\s\S]*?<\/think>/gi, "")
        .replace(/^<think>[\s\S]*$/gi, "")
        .replace(/\n*\[Confidence:[\s\S]*?(\]|$)/gi, "")
        .trim()
    : "";

  // When an interactive itinerary card is attached, strip duplicate day-by-day text blocks from the text bubble
  if (itineraryDraft && displayContent) {
    displayContent = displayContent
      .replace(/(?:\r?\n|^)#{1,4}\s*(?:Official|Day-by-Day|Route|Trek|Expedition)?\s*Itinerary[\s\S]*?(?=(?:\r?\n#{1,4}\s+[A-Za-z]|\Z))/i, "")
      .replace(/(?:\r?\n|^)\s*-\s*\*\*Day\s*\d+[\s\S]*?(?=(?:\r?\n#{1,4}\s+[A-Za-z]|\Z))/i, "")
      .trim();
  }

  return (
    <div
      className={clsx(
        "flex w-full group transition-colors",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={clsx(
          "max-w-[85%] sm:max-w-[78%] md:max-w-[72%] transition-all",
          isUser
            ? "bg-white text-slate-800 rounded-2xl rounded-tr-sm px-4 py-3 sm:px-5 sm:py-3.5 border border-slate-200/90 shadow-subtle"
            : "w-full space-y-3"
        )}
      >
        {isUser ? (
          <div className="space-y-1">
            <p className="text-[15px] leading-relaxed text-slate-800 font-normal">
              {displayContent}
            </p>
            <span className="text-[11px] text-slate-400 block text-right font-mono">
              {timestamp}
            </span>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Agent Header: Identity & Timestamp */}
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 rounded-md bg-humsafar-navy flex items-center justify-center text-white shadow-xs">
                <Sparkles className="w-3.5 h-3.5 text-humsafar-teal" />
              </div>
              <span className="text-xs font-semibold text-humsafar-navy tracking-tight">
                Humsafar Expedition AI
              </span>
              <span className="text-[11px] text-slate-400 font-mono">
                {timestamp}
              </span>
            </div>

            {/* Main AI Text Body with proper rich styling (no raw markdown characters) */}
            <MarkdownContent content={displayContent} isStreaming={isStreaming} />

            {/* Itinerary Draft Card with Direct Approval Action & Save */}
            {!isStreaming && itineraryDraft && (
              <div className="mt-3">
                <ItineraryCard
                  data={itineraryDraft}
                  onApprove={onApproveItinerary}
                  onRequestChanges={onRequestChanges}
                  onSave={onSaveItinerary ? () => onSaveItinerary(itineraryDraft) : undefined}
                  isSaved={isItinerarySaved}
                  isSaving={isSavingItinerary}
                />
              </div>
            )}

            {/* Direct Save Option for text-based itineraries without separate card */}
            {!isStreaming && !itineraryDraft && /(?:Day\s*\d+\b|\*\*Day\s*\d+\b|Day-by-Day|###\s*Day\s*\d+)/i.test(content) && onSaveItinerary && (
              <div className="pt-2 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const titleMatch = content.match(/#+\s*([^\n]+)/) || content.match(/\*\*([^\*\n]+)\*\*/);
                    const rawTitle = titleMatch ? titleMatch[1].replace(/itinerary/i, "").trim() : "Custom Expedition";
                    const title = `${rawTitle} Itinerary`;
                    const daysMatch = content.match(/(\d+)\s*[- ]?days?/i);
                    const days = daysMatch ? parseInt(daysMatch[1], 10) : 7;
                    const priceMatch = content.match(/(?:PKR|USD|\$)\s*[\d,]+/i);
                    const estimatedPrice = priceMatch ? priceMatch[0] : "Market Standard";

                    onSaveItinerary({
                      title,
                      region: "Northern Pakistan",
                      days,
                      estimatedPrice,
                      highlights: [content.slice(0, 200).replace(/[*#]/g, "").trim()],
                      isApproved: true,
                      confidenceType: "official",
                      sourceUrl: sourceUrl || "https://askoliadventure.com",
                    });
                  }}
                  disabled={isItinerarySaved || isSavingItinerary}
                  className={clsx(
                    "inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-all shadow-2xs cursor-pointer",
                    isItinerarySaved
                      ? "bg-teal-50 border-teal-200 text-teal-700 cursor-default"
                      : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:text-humsafar-teal hover:border-teal-300"
                  )}
                >
                  <Bookmark className={clsx("w-3.5 h-3.5", isItinerarySaved && "fill-teal-600 text-teal-600")} />
                  <span>{isItinerarySaved ? "Itinerary Saved" : isSavingItinerary ? "Saving..." : "Save Itinerary"}</span>
                </button>
              </div>
            )}

            {/* Official Source & Verification Chip (only for verified official catalog listings) */}
            {!isStreaming &&
              confidenceType === "official" &&
              confidenceLabel &&
              confidenceLabel.includes("official") && (
                <div className="pt-2 flex items-center justify-between gap-3 flex-wrap border-t border-slate-100 mt-2">
                  <div className="flex items-center gap-2">
                    <ConfidenceChip
                      type="official"
                      label={confidenceLabel}
                      sourceUrl={sourceUrl || "https://askoliadventure.com"}
                    />
                  </div>
                </div>
              )}


            {/* Subtle Claude-Style Sunburst / Compass Mark at end of response */}
            {!isStreaming && (
              <div className="pt-1 flex items-center gap-2 text-slate-400">
                <Compass className="w-3.5 h-3.5 text-humsafar-teal opacity-70" />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
