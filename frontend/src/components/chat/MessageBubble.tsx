"use client";

import React from "react";
import clsx from "clsx";
import {
  Check,
  Sparkles,
  Compass,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ConfidenceChip } from "@/components/ui/ConfidenceChip";
import { MarkdownContent } from "./MarkdownContent";

export interface ItineraryDraftData {
  title: string;
  region: string;
  days: number | string;
  grade?: string;
  estimatedPrice: string;
  highlights: string[];
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
  isStreaming?: boolean;
  confidenceType?: "official" | "unverified";
  confidenceLabel?: string;
  sourceUrl?: string;
  itineraryDraft?: ItineraryDraftData;
  onApproveItinerary?: () => void;
}

export const MessageBubble: React.FC<MessageProps> = ({
  sender,
  content,
  timestamp,
  isStreaming,
  confidenceType,
  confidenceLabel,
  sourceUrl,
  itineraryDraft,
  onApproveItinerary,
}) => {
  const isUser = sender === "user";

  // Defense-in-depth: strip any residual reasoning thought blocks from client display
  let displayContent = content
    ? content.replace(/<think>[\s\S]*?<\/think>/gi, "").replace(/^<think>[\s\S]*$/gi, "").trim()
    : "";

  // Extract trailing [Confidence: ... | Source: ... | Verified: ...] metadata if present
  let extractedConfidence = confidenceLabel;
  let extractedSource = sourceUrl;
  let extractedTimestamp = timestamp;

  const confidencePattern = /\n*\[Confidence:\s*([^|\]]+?)\s*\|\s*Source:\s*([^|\]]+?)\s*\|\s*Verified:\s*([^\]]+?)\]\s*$/i;
  const match = displayContent.match(confidencePattern);
  if (match) {
    if (!extractedConfidence) extractedConfidence = match[1].trim();
    if (!extractedSource) extractedSource = match[2].trim();
    if (!extractedTimestamp || extractedTimestamp.length < 5) extractedTimestamp = match[3].trim();
    // Clean raw bracketed metadata from the visible markdown body
    displayContent = displayContent.replace(confidencePattern, "").trim();
  } else {
    displayContent = displayContent.replace(/\n*\[Confidence:[\s\S]*?\]\s*$/gi, "").trim();
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

            {/* Seamless Action & Verification Bar */}
            {!isStreaming && (extractedConfidence || confidenceType || itineraryDraft || extractedSource) && (
              <div className="pt-2 flex items-center justify-between gap-3 flex-wrap border-t border-slate-100 mt-2">
                <div className="flex items-center gap-2">
                  <ConfidenceChip
                    type={confidenceType || (itineraryDraft?.confidenceType as any)}
                    label={extractedConfidence || itineraryDraft?.confidenceLabel}
                    sourceUrl={extractedSource || itineraryDraft?.sourceUrl || "https://itp.7scribes.com"}
                    timestamp={extractedTimestamp}
                  />
                </div>

                {itineraryDraft && onApproveItinerary && (
                  <div>
                    {itineraryDraft.isApproved ? (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                        Approved by traveler
                      </span>
                    ) : (
                      <Button
                        variant="approval"
                        size="sm"
                        onClick={onApproveItinerary}
                        icon={<Check className="w-3.5 h-3.5" />}
                      >
                        Approve Proposal
                      </Button>
                    )}
                  </div>
                )}
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
