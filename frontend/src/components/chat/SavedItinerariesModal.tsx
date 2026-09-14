"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Calendar,
  MapPin,
  Check,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Bookmark,
  FileText,
  Trash2,
  Download,
  Loader2,
  Compass,
  Backpack,
  ArrowLeft,
  ShieldCheck,
  Tag,
} from "lucide-react";
import { ConfidenceChip } from "@/components/ui/ConfidenceChip";
import { api } from "@/lib/api";

export interface SavedItineraryItem {
  id: string;
  title: string;
  region: string;
  duration_days: number | string;
  estimated_price_pkr?: string;
  confidence_label?: string;
  source_url?: string;
  status: "draft" | "approved" | "rejected";
  is_approved_by_user: boolean;
  approval_timestamp?: string;
  created_at?: string;
  itinerary_data?: {
    highlights?: string[];
    day_by_day?: Array<{
      day?: number | string;
      title?: string;
      description?: string;
      altitude?: string;
    }>;
    dayByDay?: Array<{
      day?: number | string;
      title?: string;
      description?: string;
      altitude?: string;
    }>;
    inclusions?: string[];
    exclusions?: string[];
    equipment?: string[];
    contact_details?: any;
    filename?: string;
  };
}

interface SavedItinerariesModalProps {
  isOpen: boolean;
  onClose: () => void;
  itineraries: SavedItineraryItem[];
  isLoading?: boolean;
  onDeleteItinerary?: (id: string) => void;
  selectedItinerary?: SavedItineraryItem | null;
  onSelectItinerary?: (item: SavedItineraryItem | null) => void;
}

export const SavedItinerariesModal: React.FC<SavedItinerariesModalProps> = ({
  isOpen,
  onClose,
  itineraries,
  isLoading = false,
  onDeleteItinerary,
  selectedItinerary = null,
  onSelectItinerary,
}) => {
  const [activeItem, setActiveItem] = useState<SavedItineraryItem | null>(selectedItinerary);
  const [activeTab, setActiveTab] = useState<"route" | "logistics" | "gear">("route");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  useEffect(() => {
    if (selectedItinerary) {
      setActiveItem(selectedItinerary);
    }
  }, [selectedItinerary]);

  if (!isOpen) return null;

  const handleDownloadPdf = async (item: SavedItineraryItem) => {
    try {
      setDownloadingId(item.id);
      await api.downloadItineraryPdf(item);
    } catch (err: any) {
      alert(err.message || "Failed to download itinerary PDF.");
    } finally {
      setDownloadingId(null);
    }
  };

  const handleClose = () => {
    setActiveItem(null);
    onSelectItinerary?.(null);
    onClose();
  };

  const handleBackToList = () => {
    setActiveItem(null);
    onSelectItinerary?.(null);
  };

  // Helper to resolve stages from either day_by_day or dayByDay or fallback
  const getStages = (item: SavedItineraryItem) => {
    const raw = item.itinerary_data?.day_by_day || item.itinerary_data?.dayByDay;
    if (Array.isArray(raw) && raw.length > 0) return raw;
    const daysCount = parseInt(String(item.duration_days).replace(/[^0-9]/g, "")) || 5;
    const fallback = [];
    for (let i = 1; i <= daysCount; i++) {
      fallback.push({
        day: i,
        title: i === 1 ? `Departure & Staging in ${item.region}` : i === daysCount ? `Return & Debrief in ${item.region}` : `Expedition Trail Stage ${i}`,
        description: `Full day guided trek across ${item.region} coordinated by certified high-altitude guides. All camp amenities and meals arranged.`,
        altitude: `${2200 + i * 350}m`,
      });
    }
    return fallback;
  };

  const getInclusions = (item: SavedItineraryItem) => {
    const inc = item.itinerary_data?.inclusions;
    if (Array.isArray(inc) && inc.length > 0) return inc;
    return [
      "Licensed mountain guide & Balti porters",
      "All camp meals, dining tent, and all-weather tents",
      "Dedicated 4x4 mountain jeep transfers",
      "National park entry and trekking permits",
    ];
  };

  const getExclusions = (item: SavedItineraryItem) => {
    const exc = item.itinerary_data?.exclusions;
    if (Array.isArray(exc) && exc.length > 0) return exc;
    return [
      "International flights and Pakistan visa fees",
      "Mandatory high-altitude evacuation insurance",
      "Personal trekking equipment (-15°C sleeping bag, boots)",
      "Staff gratuities and personal expenses",
    ];
  };

  const getGear = (item: SavedItineraryItem) => {
    const eq = item.itinerary_data?.equipment;
    if (Array.isArray(eq) && eq.length > 0) return eq;
    return [
      "Sturdy, broken-in high-altitude trekking boots",
      "4-season (-15°C) sleeping bag with insulated pad",
      "Layering system (merino wool base, fleece, Gore-Tex shell)",
      "Category 4 UV glacier sunglasses and SPF 50+ sunblock",
      "Telescopic trekking poles and headlamp with spare batteries",
      "Personal first aid kit with altitude medication (Diamox)",
    ];
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/50 backdrop-blur-xs">
      <div className="w-full max-w-3xl bg-white border border-slate-200 rounded-2xl shadow-xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="bg-humsafar-navy px-5 sm:px-6 py-4 flex items-center justify-between text-white shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {activeItem ? (
              <button
                type="button"
                onClick={handleBackToList}
                className="p-1.5 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors cursor-pointer mr-1"
                title="Back to saved itineraries list"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
            ) : (
              <Bookmark className="w-5 h-5 text-humsafar-teal shrink-0" />
            )}

            <div className="min-w-0">
              <h3 className="font-semibold text-base truncate">
                {activeItem ? activeItem.title : "My Saved Itineraries"}
              </h3>
              <p className="text-[11px] text-white/70 truncate">
                {activeItem
                  ? `${activeItem.region} • ${activeItem.duration_days} Days Plan`
                  : "Verified travel plans and approved expedition itineraries"}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={handleClose}
            className="p-1.5 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors cursor-pointer shrink-0 ml-2"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body: Either Detail Popup (activeItem) or List View */}
        {activeItem ? (
          /* --- DETAILED ITINERARY POPUP --- */
          <div className="flex-1 overflow-y-auto flex flex-col">
            {/* Top Details & Tab Navigation */}
            <div className="px-5 sm:px-6 pt-4 pb-2 bg-slate-50/70 border-b border-slate-200 shrink-0 space-y-3">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2 flex-wrap text-xs">
                  <span className="inline-flex items-center gap-1 font-semibold text-humsafar-navy bg-white px-2.5 py-1 rounded-md border border-slate-200 shadow-2xs">
                    <MapPin className="w-3.5 h-3.5 text-humsafar-teal" />
                    {activeItem.region}
                  </span>
                  <span className="inline-flex items-center gap-1 font-semibold text-slate-700 bg-white px-2.5 py-1 rounded-md border border-slate-200 shadow-2xs">
                    <Calendar className="w-3.5 h-3.5 text-humsafar-teal" />
                    {activeItem.duration_days} Days
                  </span>
                  {activeItem.estimated_price_pkr && (
                    <span className="inline-flex items-center gap-1 font-semibold text-humsafar-navy bg-white px-2.5 py-1 rounded-md border border-slate-200 shadow-2xs">
                      <Tag className="w-3.5 h-3.5 text-humsafar-teal" />
                      PKR {activeItem.estimated_price_pkr}
                    </span>
                  )}
                </div>

                <ConfidenceChip
                  type="official"
                  label={activeItem.confidence_label || "from our official listing"}
                  sourceUrl={activeItem.source_url || "https://askoliadventure.com"}
                />
              </div>

              {/* Navigation Tabs inside popup */}
              <div className="flex gap-1 border-b border-slate-200 pt-1">
                <button
                  type="button"
                  onClick={() => setActiveTab("route")}
                  className={`pb-2 px-3 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 cursor-pointer ${
                    activeTab === "route"
                      ? "border-humsafar-teal text-humsafar-navy"
                      : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                >
                  <Compass className="w-3.5 h-3.5" />
                  Day-to-Day Route
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("logistics")}
                  className={`pb-2 px-3 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 cursor-pointer ${
                    activeTab === "logistics"
                      ? "border-humsafar-teal text-humsafar-navy"
                      : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Inclusions & Exclusions
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("gear")}
                  className={`pb-2 px-3 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 cursor-pointer ${
                    activeTab === "gear"
                      ? "border-humsafar-teal text-humsafar-navy"
                      : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                >
                  <Backpack className="w-3.5 h-3.5" />
                  Gear Checklist
                </button>
              </div>
            </div>

            {/* Tab Body */}
            <div className="p-5 sm:p-6 flex-1 space-y-4">
              {/* TAB 1: Route Itinerary */}
              {activeTab === "route" && (
                <div className="space-y-3">
                  <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                    {getStages(activeItem).map((stage: any, idx: number) => (
                      <div key={idx} className="relative group">
                        <div className="absolute -left-6 top-0.5 w-5 h-5 rounded-full bg-white border-2 border-humsafar-teal flex items-center justify-center text-[10px] font-bold text-humsafar-navy shadow-2xs group-hover:bg-humsafar-teal group-hover:text-white transition-colors">
                          {stage.day || idx + 1}
                        </div>
                        <div className="flex items-start justify-between gap-2 flex-wrap">
                          <h4 className="text-xs sm:text-[13.5px] font-bold text-humsafar-navy">
                            Day {stage.day || idx + 1}: {stage.title}
                          </h4>
                          {stage.altitude && (
                            <span className="text-[10.5px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200/60">
                              {stage.altitude}
                            </span>
                          )}
                        </div>
                        {stage.description && (
                          <p className="text-xs text-slate-600 leading-relaxed mt-1">
                            {stage.description}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 2: Inclusions & Exclusions */}
              {activeTab === "logistics" && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-emerald-50/50 border border-emerald-100 space-y-2.5">
                    <span className="text-xs font-bold text-emerald-900 flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      Included Services
                    </span>
                    <ul className="space-y-2 text-xs text-slate-700">
                      {getInclusions(activeItem).map((inc: string, i: number) => (
                        <li key={i} className="flex items-start gap-2">
                          <Check className="w-3.5 h-3.5 text-emerald-600 mt-0.5 shrink-0" />
                          <span>{inc}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2.5">
                    <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                      <XCircle className="w-3.5 h-3.5 text-slate-400" />
                      Excluded Services
                    </span>
                    <ul className="space-y-2 text-xs text-slate-600">
                      {getExclusions(activeItem).map((exc: string, i: number) => (
                        <li key={i} className="flex items-start gap-2">
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
                <div className="space-y-3">
                  <p className="text-xs text-slate-500">
                    High-altitude equipment required for safety on this expedition:
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs text-slate-700">
                    {getGear(activeItem).map((eq: string, i: number) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-50 border border-slate-200/70"
                      >
                        <Backpack className="w-3.5 h-3.5 text-humsafar-teal shrink-0 mt-0.5" />
                        <span className="leading-snug">{eq}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Popup Action Footer with Working PDF Download */}
            <div className="px-5 sm:px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex items-center justify-between gap-3 shrink-0">
              <button
                type="button"
                onClick={handleBackToList}
                className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-humsafar-navy hover:bg-slate-200/60 rounded-lg transition-colors cursor-pointer"
              >
                ← Back to List
              </button>

              <div className="flex items-center gap-2">
                {/* Working PDF Download Button inside Popup */}
                <button
                  type="button"
                  onClick={() => handleDownloadPdf(activeItem)}
                  disabled={downloadingId === activeItem.id}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-humsafar-teal hover:bg-humsafar-tealHover text-white text-xs font-semibold shadow-xs transition-all cursor-pointer disabled:opacity-50"
                  title="Download itinerary PDF"
                >
                  {downloadingId === activeItem.id ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Download className="w-3.5 h-3.5" />
                  )}
                  <span>
                    {downloadingId === activeItem.id ? "Exporting PDF..." : "Download PDF"}
                  </span>
                </button>

                <button
                  type="button"
                  onClick={handleClose}
                  className="px-3.5 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* --- LIST OF SAVED ITINERARIES --- */
          <>
            <div className="p-5 sm:p-6 overflow-y-auto space-y-3.5 flex-1">
              {isLoading ? (
                <div className="py-12 text-center text-xs text-slate-500 animate-pulse">
                  Loading your saved itineraries...
                </div>
              ) : itineraries.length === 0 ? (
                <div className="py-12 text-center space-y-2">
                  <FileText className="w-10 h-10 text-slate-300 mx-auto" />
                  <h4 className="font-semibold text-sm text-humsafar-navy">No saved itineraries yet</h4>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto">
                    When an expedition itinerary is generated in chat, click the &quot;Save&quot; option on the itinerary card to bookmark it here in your member account.
                  </p>
                </div>
              ) : (
                itineraries.map((item) => (
                  <div
                    key={item.id}
                    className="bg-slate-50 hover:bg-slate-100/70 border border-slate-200 rounded-xl p-4 space-y-3 shadow-xs transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2 flex-wrap">
                      <div
                        onClick={() => setActiveItem(item)}
                        className="cursor-pointer group flex-1 min-w-[200px]"
                      >
                        <h4 className="font-bold text-sm text-humsafar-navy group-hover:text-humsafar-teal transition-colors">
                          {item.title}
                        </h4>
                        <div className="flex items-center gap-3 text-xs text-slate-500 mt-1 flex-wrap">
                          <span className="flex items-center gap-1">
                            <MapPin className="w-3.5 h-3.5 text-humsafar-teal" />
                            {item.region}
                          </span>
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3.5 h-3.5 text-humsafar-teal" />
                            {item.duration_days} Days
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <ConfidenceChip
                          type="official"
                          label={item.confidence_label || "from our official listing"}
                          sourceUrl={item.source_url || "https://askoliadventure.com"}
                        />
                      </div>
                    </div>

                    <div className="pt-2 border-t border-slate-200/80 flex items-center justify-between gap-3 text-xs flex-wrap">
                      <div>
                        <span className="text-[11px] text-slate-500 block">Estimated Price</span>
                        <span className="font-bold text-sm text-humsafar-navy">
                          {item.estimated_price_pkr
                            ? `PKR ${item.estimated_price_pkr}`
                            : "Price upon request"}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        {/* View Route & Details Popup Trigger */}
                        <button
                          type="button"
                          onClick={() => setActiveItem(item)}
                          className="px-2.5 py-1 rounded-md text-xs font-semibold text-humsafar-teal bg-white border border-humsafar-teal/40 hover:bg-teal-50 transition-colors cursor-pointer"
                        >
                          View Details
                        </button>

                        {/* Working PDF Download Button */}
                        <button
                          type="button"
                          onClick={() => handleDownloadPdf(item)}
                          disabled={downloadingId === item.id}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-slate-700 bg-white border border-slate-300 hover:border-humsafar-teal hover:text-humsafar-teal transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
                          title="Download PDF"
                        >
                          {downloadingId === item.id ? (
                            <Loader2 className="w-3 h-3 animate-spin text-humsafar-teal" />
                          ) : (
                            <Download className="w-3 h-3 text-slate-500" />
                          )}
                          <span>PDF</span>
                        </button>

                        {item.source_url && (
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 text-slate-500 hover:text-humsafar-navy hover:bg-slate-200/60 rounded-md transition-colors"
                            title="View on askoliadventure.com"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        )}

                        {/* Delete Itinerary */}
                        {onDeleteItinerary && (
                          confirmDeleteId === item.id ? (
                            <div className="flex items-center gap-1 bg-rose-50 border border-rose-200 px-2 py-1 rounded-md">
                              <span className="text-[11px] text-rose-800 font-medium">Remove?</span>
                              <button
                                type="button"
                                onClick={() => {
                                  onDeleteItinerary(item.id);
                                  setConfirmDeleteId(null);
                                }}
                                className="text-[11px] font-bold text-rose-700 hover:text-rose-900 underline ml-1 cursor-pointer"
                              >
                                Yes
                              </button>
                              <button
                                type="button"
                                onClick={() => setConfirmDeleteId(null)}
                                className="text-[11px] text-slate-500 hover:text-slate-700 ml-1 cursor-pointer"
                              >
                                No
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setConfirmDeleteId(item.id)}
                              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer"
                              title="Remove itinerary"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 text-right shrink-0">
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
