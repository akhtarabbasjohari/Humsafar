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
  AlertCircle,
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
  const displayContent = content
    ? content.replace(/<think>[\s\S]*?<\/think>/gi, "").replace(/^<think>[\s\S]*$/gi, "").trim()
    : "";

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

            {/* Main AI Text Body */}
            <div className="text-[15px] sm:text-[15.5px] leading-[1.75] text-slate-800 whitespace-pre-line">
              {displayContent}
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
            {itineraryDraft && (() => {
              const isDraft =
                itineraryDraft.confidenceType === "unverified" ||
                Boolean(itineraryDraft.confidenceLabel && itineraryDraft.confidenceLabel.includes("unverified"));

              return (
                <div className="mt-4 pt-1">
                  <div
                    className={clsx(
                      "border rounded-xl p-4 shadow-xs space-y-3.5",
                      isDraft
                        ? "bg-amber-50/25 border-amber-200/90"
                        : "bg-slate-50 border-slate-200/90"
                    )}
                  >
                    {/* Unverified Draft Advisory Banner */}
                    {isDraft && (
                      <div className="flex items-start gap-2.5 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-xs">
                        <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                        <div className="space-y-0.5">
                          <span className="font-semibold block text-amber-950">
                            Custom Expedition Proposal (Unverified)
                          </span>
                          <p className="text-[11.5px] text-amber-800 leading-relaxed">
                            Researched live from regional web sources for this serviced area. Route details, logistics, and pricing are draft estimates that must be verified by our tour operations team before final booking.
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Card Title & Download Bar */}
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <div className="flex items-center gap-3">
                        <div
                          className={clsx(
                            "w-10 h-10 rounded-lg flex items-center justify-center text-white shrink-0 shadow-xs",
                            isDraft ? "bg-amber-900" : "bg-humsafar-navy"
                          )}
                        >
                          <FileText
                            className={clsx("w-5 h-5", isDraft ? "text-amber-300" : "text-humsafar-teal")}
                          />
                        </div>
                        <div>
                          <h4 className="font-semibold text-sm sm:text-base text-humsafar-navy">
                            {itineraryDraft.title}
                          </h4>
                          <span className="text-xs text-slate-500">
                            {isDraft
                              ? "Custom Proposal • Web Research Synthesis"
                              : (itineraryDraft.filename || "Official Itinerary Document • MD")}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <ConfidenceChip
                          type={isDraft ? "unverified" : "official"}
                          label={itineraryDraft.confidenceLabel}
                          sourceUrl={itineraryDraft.sourceUrl || (isDraft ? "regional-sources" : "itp.7scribes.com")}
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
                          {itineraryDraft.days} Days ({itineraryDraft.grade || "Moderate"})
                        </span>
                      </div>

                      <ul className="space-y-1 text-slate-700">
                        {itineraryDraft.highlights.map((h, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span
                              className={clsx(
                                "w-1.5 h-1.5 rounded-full mt-1.5 shrink-0",
                                isDraft ? "bg-amber-600" : "bg-humsafar-teal"
                              )}
                            />
                            <span>{h}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Key Logistics: Inclusions & Gear Highlights */}
                    {(itineraryDraft.inclusions || itineraryDraft.equipment) && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11.5px]">
                        {itineraryDraft.inclusions && (
                          <div className="bg-slate-50 rounded-lg p-2.5 border border-slate-200/80 space-y-1">
                            <span className="font-semibold text-slate-700 block text-xs">Included Services:</span>
                            <ul className="space-y-0.5 text-slate-600 list-disc list-inside">
                              {itineraryDraft.inclusions.slice(0, 3).map((inc, i) => (
                                <li key={i} className="truncate">{inc}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {itineraryDraft.equipment && (
                          <div className="bg-slate-50 rounded-lg p-2.5 border border-slate-200/80 space-y-1">
                            <span className="font-semibold text-slate-700 block text-xs">Essential Gear:</span>
                            <ul className="space-y-0.5 text-slate-600 list-disc list-inside">
                              {itineraryDraft.equipment.slice(0, 3).map((eq, i) => (
                                <li key={i} className="truncate">{eq}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Pricing & Human-in-the-Loop Confirmation */}
                    <div className="pt-1 flex items-center justify-between gap-4 flex-wrap border-t border-slate-200/70">
                      <div>
                        <span className="text-[11px] text-slate-500 block">
                          {isDraft ? "Estimated custom quote (unverified)" : "Official package price"}
                        </span>
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
                            Approve Proposal
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}

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
