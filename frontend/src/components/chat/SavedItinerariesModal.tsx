"use client";

import React from "react";
import { X, Calendar, MapPin, Check, ExternalLink, Bookmark, FileText } from "lucide-react";
import { ConfidenceChip } from "@/components/ui/ConfidenceChip";

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
}

interface SavedItinerariesModalProps {
  isOpen: boolean;
  onClose: () => void;
  itineraries: SavedItineraryItem[];
  isLoading?: boolean;
}

export const SavedItinerariesModal: React.FC<SavedItinerariesModalProps> = ({
  isOpen,
  onClose,
  itineraries,
  isLoading = false,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/50 backdrop-blur-xs">
      <div className="w-full max-w-2xl bg-white border border-slate-200 rounded-2xl shadow-xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="bg-humsafar-navy px-6 py-4 flex items-center justify-between text-white shrink-0">
          <div className="flex items-center gap-2.5">
            <Bookmark className="w-5 h-5 text-humsafar-teal" />
            <div>
              <h3 className="font-semibold text-base">My Saved Itineraries</h3>
              <p className="text-[11px] text-white/70">
                Verified travel plans and approved expedition itineraries
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-4">
          {isLoading ? (
            <div className="py-12 text-center text-xs text-slate-500 animate-pulse">
              Loading your saved itineraries...
            </div>
          ) : itineraries.length === 0 ? (
            <div className="py-12 text-center space-y-2">
              <FileText className="w-10 h-10 text-slate-300 mx-auto" />
              <h4 className="font-semibold text-sm text-humsafar-navy">No saved itineraries yet</h4>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                When you plan a trip in chat and approve an itinerary card, it will be automatically saved here in your member account.
              </p>
            </div>
          ) : (
            itineraries.map((item) => (
              <div
                key={item.id}
                className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3 shadow-xs"
              >
                <div className="flex items-start justify-between gap-2 flex-wrap">
                  <div>
                    <h4 className="font-bold text-sm text-humsafar-navy">
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
                      sourceUrl={item.source_url || "itp.7scribes.com"}
                    />
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-200/80 flex items-center justify-between gap-4 text-xs">
                  <div>
                    <span className="text-[11px] text-slate-500 block">Estimated Price</span>
                    <span className="font-bold text-sm text-humsafar-navy">
                      {item.estimated_price_pkr ? `PKR ${item.estimated_price_pkr}` : "Price upon request"}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {item.is_approved_by_user ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                        Approved by traveler
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
                        Draft Pending
                      </span>
                    )}

                    {item.source_url && (
                      <a
                        href={item.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 text-slate-500 hover:text-humsafar-navy hover:bg-slate-200/60 rounded-md transition-colors"
                        title="View on itp.7scribes.com"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
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
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
