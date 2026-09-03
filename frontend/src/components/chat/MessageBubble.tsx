"use client";

import React from "react";
import clsx from "clsx";
import {
  FileText,
  Download,
  Check,
  Calendar,
  MapPin,
  ChevronDown,
  Sparkles,
  Compass,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ConfidenceChip } from "@/components/ui/ConfidenceChip";

export interface ItineraryDraftData {
  title: string;
  region: string;
  days: number | string;
  grade?: string;
  estimatedPrice: string;
  highlights: string[];
  isApproved: boolean;
  confidenceType?: "official" | "unverified";
  confidenceLabel?: string;
  sourceUrl?: string;
  filename?: string;
}

export interface MessageProps {
  id: string;
  sender: "agent" | "user";
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
  isStreaming = false,
  confidenceType,
  confidenceLabel,
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
        {/* User Prompt (Clean Claude Style right-aligned) */}
        {!isAgent ? (
          <div className="bg-slate-100/90 hover:bg-slate-100 text-slate-800 px-4 py-3 rounded-2xl text-[15px] leading-relaxed max-w-full transition-colors">
            {content}
          </div>
        ) : (
          /* Agent Turn (Open Claude Style with typography and document cards) */
          <div className="w-full space-y-4">
            {/* Agent Text */}
            <div className="text-[15px] sm:text-[15.5px] leading-[1.75] text-slate-800 whitespace-pre-line">
              {content}
              {isStreaming && <span className="streaming-cursor" />}
            </div>

            {/* Inline Confidence Chip if present */}
            {(confidenceLabel || confidenceType) && (
              <div className="pt-1 flex items-center gap-3">
                <ConfidenceChip
                  type={confidenceType}
                  label={confidenceLabel}
                  sourceUrl={sourceUrl || "itp.7scribes.com"}
                />
              </div>
            )}

            {/* Claude-Style Artifact / Itinerary Document Card */}
            {itineraryDraft && (
              <div className="mt-4 pt-1">
                <div className="bg-slate-50 border border-slate-200/90 rounded-xl p-4 shadow-xs space-y-3.5">
                  {/* Card Title & Download Bar (matches Claude screenshot) */}
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-humsafar-navy flex items-center justify-center text-white shrink-0 shadow-xs">
                        <FileText className="w-5 h-5 text-humsafar-teal" />
                      </div>
                      <div>
                        <h4 className="font-semibold text-sm sm:text-base text-humsafar-navy">
                          {itineraryDraft.title}
                        </h4>
                        <span className="text-xs text-slate-500">
                          {itineraryDraft.filename || "Itinerary Document • MD"}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <ConfidenceChip
                        type={itineraryDraft.confidenceType || "official"}
                        label={itineraryDraft.confidenceLabel}
                        sourceUrl={itineraryDraft.sourceUrl || "itp.7scribes.com"}
                      />

                      <button
                        type="button"
                        onClick={() => {}}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 transition-colors cursor-pointer"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>Download</span>
                        <ChevronDown className="w-3 h-3 text-slate-400" />
                      </button>
                    </div>
                  </div>

                  {/* Route Highlights & Logistics */}
                  <div className="bg-white rounded-lg p-3.5 border border-slate-200 text-xs space-y-2">
                    <div className="flex items-center justify-between text-slate-500 pb-2 border-b border-slate-100 flex-wrap gap-2">
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-humsafar-teal" />
                        {itineraryDraft.region}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-humsafar-teal" />
                        {itineraryDraft.days} Days ({itineraryDraft.grade})
                      </span>
                    </div>

                    <ul className="space-y-1 text-slate-700">
                      {itineraryDraft.highlights.map((h, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-humsafar-teal mt-1.5 shrink-0" />
                          <span>{h}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Pricing & Human-in-the-Loop Confirmation */}
                  <div className="pt-1 flex items-center justify-between gap-4 flex-wrap border-t border-slate-200/70">
                    <div>
                      <span className="text-[11px] text-slate-500 block">Package price</span>
                      <span className="text-base font-bold text-humsafar-navy">
                        {itineraryDraft.estimatedPrice}
                      </span>
                    </div>

                    <div>
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

            {/* Subtle Claude-Style Sunburst / Compass Mark at end of response */}
            {!isStreaming && (
              <div className="pt-2 flex items-center gap-2 text-slate-400">
                <Compass className="w-4 h-4 text-humsafar-teal opacity-70 animate-spin-slow" />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
