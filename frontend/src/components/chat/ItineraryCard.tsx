"use client";

import React, { useState } from "react";
import clsx from "clsx";
import {
  Calendar,
  MapPin,
  Tag,
  Check,
  CheckCircle2,
  XCircle,
  Sparkles,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  Backpack,
  Edit3,
  Compass,
  Loader2,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ConfidenceChip } from "@/components/ui/ConfidenceChip";
import { ItineraryDraftData } from "./MessageBubble";
import { api } from "@/lib/api";

interface ItineraryCardProps {
  data: ItineraryDraftData;
  onRequestChanges?: (title?: string) => void;
}

export const ItineraryCard: React.FC<ItineraryCardProps> = ({
  data,
  onRequestChanges,
}) => {
  const [isTimelineExpanded, setIsTimelineExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<"route" | "logistics" | "gear">("route");
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownloadPdf = async () => {
    try {
      setIsDownloading(true);
      await api.downloadItineraryPdf(data);
    } catch (err: any) {
      alert(err.message || "Failed to download itinerary PDF.");
    } finally {
      setIsDownloading(false);
    }
  };

  // Fallback safety for missing data
  if (!data || !data.title) {
    return (
      <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-700">
        <p className="font-semibold text-humsafar-navy">Expedition Summary</p>
        <p className="text-xs text-slate-500 mt-1">Detailed package specifications are being finalized by our operations team.</p>
      </div>
    );
  }

  const isOfficial = data.confidenceType === "official" || (data.confidenceLabel && data.confidenceLabel.includes("official"));
  const stages = data.dayByDay && Array.isArray(data.dayByDay) ? data.dayByDay : [];
  const displayStages = isTimelineExpanded ? stages : stages.slice(0, 3);
  const hasMultipleStages = stages.length > 3;

  return (
    <div className="w-full my-3.5 rounded-2xl border border-slate-200/90 bg-white shadow-subtle overflow-hidden transition-all duration-200">
      {/* 1. Header Banner & Status Badge */}
      <div className="px-4 py-3.5 sm:px-5 sm:py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50/70 to-white">
        <div className="flex items-center justify-between gap-2 flex-wrap mb-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={clsx(
                "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide",
                isOfficial
                  ? "bg-teal-50 text-humsafar-teal border border-teal-200/80"
                  : "bg-amber-50 text-amber-800 border border-amber-200/80"
              )}
            >
              {isOfficial ? (
                <>
                  <ShieldCheck className="w-3.5 h-3.5 text-humsafar-teal" />
                  Official Expedition Package
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-amber-600" />
                  Custom Proposal (Draft)
                </>
              )}
            </span>

            {/* Download PDF button in header */}
            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={isDownloading}
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 hover:border-humsafar-teal hover:text-humsafar-teal transition-all cursor-pointer shadow-2xs"
              title="Download official PDF itinerary"
            >
              {isDownloading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-humsafar-teal" />
              ) : (
                <Download className="w-3.5 h-3.5 text-slate-500 hover:text-humsafar-teal" />
              )}
              <span>PDF</span>
            </button>
          </div>

          <ConfidenceChip
            type={isOfficial ? "official" : "unverified"}
            label={data.confidenceLabel || (isOfficial ? "from our official listing" : "researched just now, unverified, please confirm with our team")}
            sourceUrl={data.sourceUrl || "https://askoliadventure.com"}
          />
        </div>

        {/* Title */}
        <h3 className="text-base sm:text-lg font-bold text-humsafar-navy tracking-tight mt-1">
          {data.title}
        </h3>

        {/* Metadata Chips: Duration, Price, Region */}
        <div className="flex items-center gap-2 mt-2.5 flex-wrap">
          <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-700 bg-slate-100/90 px-2.5 py-1 rounded-md border border-slate-200/60">
            <Calendar className="w-3.5 h-3.5 text-humsafar-teal" />
            {data.days || "Multi-Day"}
          </span>

          <span className="inline-flex items-center gap-1 text-xs font-semibold text-humsafar-navy bg-slate-100/90 px-2.5 py-1 rounded-md border border-slate-200/60">
            <Tag className="w-3.5 h-3.5 text-humsafar-teal" />
            {data.estimatedPrice || "Market Rate Calculated"}
          </span>

          {data.region && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 bg-slate-100/90 px-2.5 py-1 rounded-md border border-slate-200/60">
              <MapPin className="w-3.5 h-3.5 text-slate-500" />
              {data.region}
            </span>
          )}
        </div>
      </div>

      {/* 2. Interactive Navigation Tabs */}
      <div className="flex border-b border-slate-100 bg-slate-50/50 px-4 sm:px-5">
        <button
          onClick={() => setActiveTab("route")}
          className={clsx(
            "py-2.5 px-3 text-xs sm:text-[13px] font-semibold transition-colors border-b-2 flex items-center gap-1.5",
            activeTab === "route"
              ? "border-humsafar-teal text-humsafar-navy"
              : "border-transparent text-slate-500 hover:text-slate-700"
          )}
        >
          <Compass className="w-3.5 h-3.5" />
          Route Itinerary {stages.length > 0 && `(${stages.length} Days)`}
        </button>

        <button
          onClick={() => setActiveTab("logistics")}
          className={clsx(
            "py-2.5 px-3 text-xs sm:text-[13px] font-semibold transition-colors border-b-2 flex items-center gap-1.5",
            activeTab === "logistics"
              ? "border-humsafar-teal text-humsafar-navy"
              : "border-transparent text-slate-500 hover:text-slate-700"
          )}
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          Inclusions & Exclusions
        </button>

        <button
          onClick={() => setActiveTab("gear")}
          className={clsx(
            "py-2.5 px-3 text-xs sm:text-[13px] font-semibold transition-colors border-b-2 flex items-center gap-1.5",
            activeTab === "gear"
              ? "border-humsafar-teal text-humsafar-navy"
              : "border-transparent text-slate-500 hover:text-slate-700"
          )}
        >
          <Backpack className="w-3.5 h-3.5" />
          Gear Checklist
        </button>
      </div>

      {/* 3. Tab Contents */}
      <div className="p-4 sm:p-5">
        {/* TAB 1: Route Itinerary Timeline */}
        {activeTab === "route" && (
          <div className="space-y-3">
            {stages.length > 0 ? (
              <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                {displayStages.map((stage, idx) => (
                  <div key={idx} className="relative group">
                    {/* Circle timeline pin */}
                    <div className="absolute -left-6 top-0.5 w-5 h-5 rounded-full bg-white border-2 border-humsafar-teal flex items-center justify-center text-[10px] font-bold text-humsafar-navy shadow-2xs group-hover:bg-humsafar-teal group-hover:text-white transition-colors">
                      {stage.day || idx + 1}
                    </div>

                    <div className="flex items-start justify-between gap-2 flex-wrap">
                      <h4 className="text-xs sm:text-[13.5px] font-bold text-humsafar-navy leading-snug">
                        Day {stage.day || idx + 1}: {stage.title}
                      </h4>
                      {stage.altitude && (
                        <span className="text-[10.5px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200/60">
                          {stage.altitude}
                        </span>
                      )}
                    </div>
                    {stage.description && (
                      <p className="text-xs text-slate-600 leading-relaxed mt-0.5">
                        {stage.description}
                      </p>
                    )}
                  </div>
                ))}

                {/* Expand / Collapse Control */}
                {hasMultipleStages && (
                  <div className="pt-2">
                    <button
                      onClick={() => setIsTimelineExpanded(!isTimelineExpanded)}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold text-humsafar-teal hover:text-teal-700 transition-colors py-1 px-2 rounded-md hover:bg-teal-50"
                    >
                      {isTimelineExpanded ? (
                        <>
                          <ChevronUp className="w-3.5 h-3.5" />
                          Collapse itinerary outline
                        </>
                      ) : (
                        <>
                          <ChevronDown className="w-3.5 h-3.5" />
                          View full {stages.length}-day expedition route
                        </>
                      )}
                    </button>
                  </div>
                )}
              </div>
            ) : (
              /* Fallback plain text route */
              <div className="space-y-2 text-xs sm:text-[13px] text-slate-700 leading-relaxed">
                <p>{data.highlights?.[0] || "Standard expedition pacing with daily route details coordinated by native mountain guides."}</p>
                <p className="text-slate-500 italic">Day-by-day staging is finalized upon reservation according to seasonal trail conditions.</p>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: Inclusions & Exclusions */}
        {activeTab === "logistics" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Inclusions */}
            <div className="p-3.5 rounded-xl bg-emerald-50/40 border border-emerald-100 space-y-2">
              <span className="text-xs font-bold text-emerald-900 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                Included Services
              </span>
              <ul className="space-y-1.5 text-xs text-slate-700">
                {(data.inclusions && data.inclusions.length > 0 ? data.inclusions : [
                  "Licensed mountain guide & Balti porters",
                  "All camp meals, dining tent, and all-weather tents",
                  "Dedicated 4x4 mountain jeep transfers",
                  "National park entry and trekking permits",
                ]).map((inc, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <Check className="w-3 h-3 text-emerald-600 mt-0.5 shrink-0" />
                    <span>{inc}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Exclusions */}
            <div className="p-3.5 rounded-xl bg-slate-50/80 border border-slate-200/80 space-y-2">
              <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <XCircle className="w-3.5 h-3.5 text-slate-400" />
                Excluded Services
              </span>
              <ul className="space-y-1.5 text-xs text-slate-600">
                {(data.exclusions && data.exclusions.length > 0 ? data.exclusions : [
                  "International flights and Pakistan visa fees",
                  "Mandatory high-altitude evacuation insurance",
                  "Personal trekking equipment (-15°C sleeping bag, boots)",
                  "Staff gratuities and personal expenses",
                ]).map((exc, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-300 mt-1.5 shrink-0" />
                    <span>{exc}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* TAB 3: Mountain Gear Checklist */}
        {activeTab === "gear" && (
          <div className="space-y-2.5">
            <p className="text-xs text-slate-500">Essential high-altitude equipment required for safe participation:</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-700">
              {(data.equipment && data.equipment.length > 0 ? data.equipment : [
                "Sturdy, broken-in high-altitude trekking boots",
                "4-season (-15°C) sleeping bag with insulated pad",
                "Layering system (merino wool base, fleece, Gore-Tex shell)",
                "Category 4 UV glacier sunglasses and SPF 50+ sunblock",
                "Telescopic trekking poles and headlamp with spare batteries",
                "Personal first aid kit with altitude medication (Diamox)",
              ]).map((eq, i) => (
                <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-slate-50 border border-slate-100">
                  <Backpack className="w-3.5 h-3.5 text-humsafar-teal shrink-0 mt-0.5" />
                  <span className="leading-snug">{eq}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 4. Action Bar (Rule 5: Approve and Request Changes Real UI Controls) */}
      <div className="px-4 py-3 sm:px-5 sm:py-3.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="italic">
            {data.contactDetails?.advisory || "Permit processing and logistics require 6–8 weeks advance booking."}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Download PDF Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadPdf}
            disabled={isDownloading}
            icon={
              isDownloading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-humsafar-teal" />
              ) : (
                <Download className="w-3.5 h-3.5" />
              )
            }
            className="!text-slate-700 hover:!text-humsafar-teal hover:!border-humsafar-teal"
          >
            {isDownloading ? "Exporting..." : "Download PDF"}
          </Button>
        </div>
      </div>
    </div>
  );
};
