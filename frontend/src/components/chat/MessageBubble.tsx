"use client";

import React from "react";
import clsx from "clsx";
import { Check, Calendar, MapPin } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ConfidenceChip } from "@/components/ui/ConfidenceChip";

export interface ItineraryDraftData {
  title: string;
  region: string;
  days: number;
  grade: string;
  estimatedPrice: string;
  highlights: string[];
  isApproved: boolean;
  confidenceType?: "official" | "unverified";
  sourceUrl?: string;
}

export interface MessageProps {
  id: string;
  sender: "agent" | "user";
  content: string;
  timestamp: string;
  isStreaming?: boolean;
  confidenceType?: "official" | "unverified";
  sourceUrl?: string;
  itineraryDraft?: ItineraryDraftData;
  onApproveItinerary?: () => void;
}

export const MessageBubble: React.FC<MessageProps> = ({
  sender,
  content,
  timestamp,
  isStreaming = false,
  confidenceType,
  sourceUrl,
  itineraryDraft,
  onApproveItinerary,
}) => {
  const isAgent = sender === "agent";

  return (
    <div
      className={clsx(
        "flex w-full my-6 sm:my-8",
        isAgent ? "justify-start" : "justify-end"
      )}
    >
      <div
        className={clsx(
          "flex flex-col w-full",
          isAgent ? "items-start max-w-full" : "items-end max-w-[85%] sm:max-w-[75%]"
        )}
      >
        {/* Turn Sub-header: Sender and Timestamp without middot */}
        <div className="flex items-center gap-2 mb-1.5 px-1 text-xs text-humsafar-mutedText">
          <span className="font-semibold text-humsafar-navy">
            {isAgent ? "Humsafar" : "You"}
          </span>
          <span className="text-[11px] text-humsafar-mutedText/70">{timestamp}</span>
        </div>

        {/* Turn Bubble: Generous Claude-style rhythm */}
        <div
          className={clsx(
            "w-full rounded-xl px-4 py-3.5 sm:px-5 sm:py-4.5 text-[15px] leading-relaxed border transition-colors",
            isAgent
              ? "bg-humsafar-tealTint border-humsafar-tealBorder text-humsafar-bodyText"
              : "bg-white border-humsafar-neutralBorder text-humsafar-bodyText shadow-subtle"
          )}
        >
          {/* Message Text with Streaming Cursor if active */}
          <div className="whitespace-pre-line text-[15px] leading-relaxed text-slate-800">
            {content}
            {isStreaming && <span className="streaming-cursor" />}
          </div>

          {/* Inline Perplexity-Style Confidence Chip for Agent Claim */}
          {isAgent && confidenceType && (
            <div className="mt-3 pt-2.5 border-t border-humsafar-tealBorder/70 flex items-center justify-between gap-3 flex-wrap">
              <ConfidenceChip
                type={confidenceType}
                sourceUrl={sourceUrl || "itp.7scribes.com"}
              />
              <span className="text-xs text-humsafar-mutedText">
                {confidenceType === "official"
                  ? "Ground truth from live tour catalog"
                  : "External research fallback"}
              </span>
            </div>
          )}

          {/* Functional Itinerary Draft Card with Navy Approval Button */}
          {itineraryDraft && (
            <div className="mt-4 pt-3 border-t border-humsafar-tealBorder">
              <div className="bg-white rounded-lg p-4 border border-humsafar-tealBorder/90 shadow-subtle space-y-3.5">
                {/* Itinerary Header and Source Chip */}
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <h4 className="font-semibold text-base text-humsafar-navy tracking-tight">
                      {itineraryDraft.title}
                    </h4>
                    <div className="flex items-center gap-3 text-xs text-humsafar-mutedText mt-1 flex-wrap">
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-humsafar-teal" />
                        {itineraryDraft.region}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-humsafar-teal" />
                        {itineraryDraft.days} days ({itineraryDraft.grade})
                      </span>
                    </div>
                  </div>

                  <ConfidenceChip
                    type={itineraryDraft.confidenceType || "official"}
                    sourceUrl={itineraryDraft.sourceUrl || "itp.7scribes.com"}
                  />
                </div>

                {/* Day-by-Day Logistics */}
                <div className="space-y-1.5 text-xs text-slate-700 bg-slate-50/80 rounded-md p-3 border border-slate-200/60">
                  <p className="font-semibold text-humsafar-navy text-xs mb-1">
                    Route logistics
                  </p>
                  <ul className="space-y-1">
                    {itineraryDraft.highlights.map((highlight, index) => (
                      <li key={index} className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-humsafar-teal mt-1.5 shrink-0" />
                        <span>{highlight}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Pricing & Visually Distinct Approval Button (#0F2C3E Navy) */}
                <div className="pt-2 flex items-center justify-between gap-4 flex-wrap border-t border-slate-100">
                  <div>
                    <span className="text-xs text-humsafar-mutedText block">Estimated price</span>
                    <span className="text-base font-bold text-humsafar-navy">
                      {itineraryDraft.estimatedPrice}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {itineraryDraft.isApproved ? (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                        <Check className="w-4 h-4 text-emerald-600" />
                        Approved by traveler
                      </span>
                    ) : (
                      <Button
                        variant="approval"
                        size="sm"
                        onClick={onApproveItinerary}
                        icon={<Check className="w-3.5 h-3.5" />}
                      >
                        Approve Itinerary
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
