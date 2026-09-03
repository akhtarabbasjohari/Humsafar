"use client";

import React from "react";
import clsx from "clsx";
import { Compass, CheckCircle2, ShieldCheck, MapPin, Calendar, DollarSign, Mountain } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

export interface MessageProps {
  id: string;
  sender: "agent" | "user";
  content: string;
  timestamp: string;
  verifiedSource?: string;
  itineraryDraft?: {
    title: string;
    region: string;
    days: number;
    grade: string;
    estimatedPrice: string;
    highlights: string[];
    isApproved: boolean;
  };
}

export const MessageBubble: React.FC<MessageProps> = ({
  sender,
  content,
  timestamp,
  verifiedSource,
  itineraryDraft,
}) => {
  const isAgent = sender === "agent";

  return (
    <div
      className={clsx(
        "flex w-full gap-3 sm:gap-4 my-4 animate-in fade-in slide-in-from-bottom-2 duration-200",
        isAgent ? "justify-start" : "justify-end"
      )}
    >
      {/* Agent Avatar */}
      {isAgent && (
        <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-humsafar-header border border-humsafar-accent/40 flex items-center justify-center shrink-0 shadow-sm text-humsafar-accent">
          <Compass className="w-4 h-4 sm:w-5 sm:h-5 text-humsafar-accent" />
        </div>
      )}

      {/* Bubble Container */}
      <div
        className={clsx(
          "flex flex-col max-w-[88%] sm:max-w-[78%] md:max-w-[70%]",
          isAgent ? "items-start" : "items-end"
        )}
      >
        {/* Sender Info / Timestamp */}
        <div className="flex items-center gap-2 mb-1 px-1 text-[11px] text-humsafar-mutedText">
          <span className="font-semibold text-humsafar-slate">
            {isAgent ? "Humsafar AI" : "You"}
          </span>
          <span>•</span>
          <span>{timestamp}</span>
        </div>

        {/* Bubble Body */}
        <div
          className={clsx(
            "rounded-2xl px-4 py-3.5 sm:px-5 sm:py-4 text-sm leading-relaxed border transition-all",
            isAgent
              ? "bg-humsafar-agentBubble text-humsafar-charcoal border-humsafar-agentBubbleBorder rounded-tl-sm shadow-subtle"
              : "bg-humsafar-userBubble text-humsafar-charcoal border-humsafar-userBubbleBorder rounded-tr-sm shadow-card"
          )}
        >
          {/* Main Text Content */}
          <p className="whitespace-pre-line text-sm sm:text-[14.5px] leading-relaxed text-[#1D2B24]">
            {content}
          </p>

          {/* Sample Embedded Drafted Itinerary Card (Consumer AI Travel Feature) */}
          {itineraryDraft && (
            <div className="mt-4 pt-3 border-t border-humsafar-agentBubbleBorder/80">
              <div className="bg-white/90 backdrop-blur-sm rounded-xl p-4 border border-humsafar-agentBubbleBorder shadow-sm space-y-3">
                <div className="flex items-start justify-between gap-2 flex-wrap">
                  <div>
                    <h4 className="font-semibold text-base text-humsafar-header flex items-center gap-2">
                      <Mountain className="w-4 h-4 text-humsafar-accent" />
                      {itineraryDraft.title}
                    </h4>
                    <div className="flex items-center gap-3 text-xs text-humsafar-mutedText mt-1 flex-wrap">
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-humsafar-accent" />
                        {itineraryDraft.region}
                      </span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-humsafar-mainButton" />
                        {itineraryDraft.days} Days ({itineraryDraft.grade})
                      </span>
                    </div>
                  </div>

                  <Badge variant="draft">
                    Draft • Pending Approval
                  </Badge>
                </div>

                {/* Highlights */}
                <div className="bg-humsafar-surfaceParchment/70 rounded-lg p-3 text-xs space-y-1.5 border border-humsafar-subtleBorder/50">
                  <span className="font-semibold text-humsafar-slate block text-[11px] uppercase tracking-wider">
                    Key Highlights & Logistics
                  </span>
                  <ul className="space-y-1 text-humsafar-slate">
                    {itineraryDraft.highlights.map((h, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-humsafar-accent shrink-0" />
                        <span>{h}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Price & Human-in-the-Loop Confirmation Bar */}
                <div className="pt-2 flex items-center justify-between gap-3 flex-wrap border-t border-humsafar-subtleBorder/40">
                  <div>
                    <span className="text-[11px] text-humsafar-mutedText block">Estimated Package</span>
                    <span className="text-sm sm:text-base font-bold text-humsafar-header">
                      {itineraryDraft.estimatedPrice}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm">
                      Customize
                    </Button>
                    <Button
                      variant="approval"
                      size="sm"
                      icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                    >
                      Approve Itinerary
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Grounding & Verification Footnote */}
          {verifiedSource && (
            <div className="mt-2.5 pt-2 border-t border-humsafar-agentBubbleBorder/60 flex items-center gap-1.5 text-[11px] text-humsafar-mutedText">
              <ShieldCheck className="w-3.5 h-3.5 text-humsafar-mainButton shrink-0" />
              <span>{verifiedSource}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
