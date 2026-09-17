"use client";

import React from "react";
import clsx from "clsx";
import {
  Sparkles,
  Compass,
  FileText,
} from "lucide-react";
import { ConfidenceChip } from "@/components/ui/ConfidenceChip";
import { MarkdownContent } from "./MarkdownContent";
import { ItineraryCard } from "./ItineraryCard";

export interface MessageAttachment {
  name: string;
  size?: string;
}

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
  attachments?: MessageAttachment[];
  sessionId?: string;
  itineraryId?: string;
  isStreaming?: boolean;
  confidenceType?: "official" | "unverified";
  confidenceLabel?: string;
  sourceUrl?: string;
  itineraryDraft?: ItineraryDraftData;
  onRequestChanges?: (title?: string) => void;
}

export const MessageBubble: React.FC<MessageProps> = ({
  sender,
  content,
  timestamp,
  attachments,
  sessionId,
  itineraryId,
  isStreaming,
  confidenceType,
  confidenceLabel,
  sourceUrl,
  itineraryDraft,
  onRequestChanges,
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

  // When an interactive itinerary card is attached, strip duplicate day-by-day text blocks from the text bubble so ItineraryCard is sole display
  if (itineraryDraft && displayContent) {
    displayContent = displayContent
      .replace(/(?:\r?\n|^)#{1,4}\s*(?:Official|Day-by-Day|Route|Trek|Expedition)?\s*Itinerary[\s\S]*?(?=(?:\r?\n#{1,4}\s+[A-Za-z]|\Z))/gi, "")
      .replace(/(?:\r?\n|^)\s*(?:[\*\-\•\–\—]|\d+\.)?\s*\*{0,2}Day[\s\u00a0\u202f]*\d+[\s\S]*?(?=(?:\r?\n#{1,4}\s+[A-Za-z]|\Z))/gi, "")
      .trim();

    const lines = displayContent.split("\n");
    const filteredLines = lines.filter(line => {
      const trimmed = line.trim();
      return !/^(?:[\*\-\•\–\—]|\d+\.)?\s*\*{0,2}Day[\s\u00a0\u202f]*\d+/i.test(trimmed);
    });
    displayContent = filteredLines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
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
          <div className="space-y-2">
            {attachments && attachments.length > 0 && (
              <div className="flex flex-col gap-1.5 mb-1">
                {attachments.map((doc, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-2.5 px-3 py-2 bg-slate-50 border border-slate-200/90 rounded-xl text-xs text-slate-700 shadow-2xs"
                  >
                    <div className="w-7 h-7 rounded-lg bg-humsafar-navy/10 flex items-center justify-center text-humsafar-navy shrink-0">
                      <FileText className="w-4 h-4 text-humsafar-teal" />
                    </div>
                    <div className="flex flex-col min-w-0 pr-1">
                      <span className="font-semibold text-slate-800 truncate max-w-[240px]" title={doc.name}>
                        {doc.name}
                      </span>
                      <span className="text-[10.5px] text-slate-400 font-mono">
                        {doc.size || "Uploaded document"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {displayContent ? (
              <p className="text-[15px] leading-relaxed text-slate-800 font-normal">
                {displayContent}
              </p>
            ) : null}
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

            {/* Itinerary Draft Card */}
            {!isStreaming && itineraryDraft && (
              <div className="mt-3">
                <ItineraryCard
                  data={itineraryDraft}
                  onRequestChanges={onRequestChanges}
                />
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
