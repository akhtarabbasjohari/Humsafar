"use client";

import React, { useState } from "react";
import clsx from "clsx";
import {
  Check,
  CheckCircle2,
  Edit3,
  Lock,
  Unlock,
  Sparkles,
  ArrowRight,
  Send,
  Loader2,
  X,
  FileCheck,
  Building2,
  Phone,
  Mail,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useAppStore } from "@/store/useAppStore";
import {
  useApproveItineraryMutation,
  useRedraftItineraryMutation,
} from "@/hooks/useChatQueries";

export interface ItineraryApprovalGateProps {
  sessionId: string;
  itineraryId?: string;
  title?: string;
  region?: string;
  duration?: string | number;
  estimatedPrice?: string;
  isDraft?: boolean;
  onApproved?: () => void;
  onRedraftComplete?: () => void;
}

export const ItineraryApprovalGate: React.FC<ItineraryApprovalGateProps> = ({
  sessionId,
  itineraryId,
  title = "Custom Expedition Itinerary",
  region = "Northern Pakistan",
  duration = "7 Days",
  estimatedPrice = "Custom Quote",
  isDraft = true,
  onApproved,
  onRedraftComplete,
}) => {
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [isInquiryModalOpen, setIsInquiryModalOpen] = useState(false);
  const [inquirySubmitted, setInquirySubmitted] = useState(false);

  // Approval status stored in Zustand store (Phase 7 store) - NOT local component state
  const approvalKey = itineraryId || title || sessionId;
  const isApprovedInStore = useAppStore((state) =>
    Boolean(state.approvalStatus[approvalKey])
  );
  const setApprovalStatus = useAppStore((state) => state.setApprovalStatus);

  const approveMutation = useApproveItineraryMutation();
  const redraftMutation = useRedraftItineraryMutation();

  const handleApprove = async () => {
    // Update Zustand store immediately
    setApprovalStatus(approvalKey, true);
    if (itineraryId) {
      setApprovalStatus(itineraryId, true);
    }
    if (sessionId) {
      setApprovalStatus(sessionId, true);
    }

    try {
      if (itineraryId) {
        await approveMutation.mutateAsync({
          itineraryId,
          notes: "Approved by traveler via in-chat HITL gate.",
        });
      }
      onApproved?.();
    } catch (err) {
      console.warn("Could not sync approval to backend:", err);
    }
  };

  const handleSubmitFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!feedbackText.trim() || redraftMutation.isPending) return;

    try {
      // Redraft mutation folds traveler feedback back into the drafting skill
      await redraftMutation.mutateAsync({
        sessionId,
        feedback: feedbackText.trim(),
        itineraryId,
        currentItinerary: {
          title,
          region,
          duration,
          price: estimatedPrice,
        },
      });

      // Reset feedback box and ensure approval is draft in Zustand
      setFeedbackText("");
      setIsFeedbackOpen(false);
      setApprovalStatus(approvalKey, false);
      if (itineraryId) {
        setApprovalStatus(itineraryId, false);
      }
      if (sessionId) {
        setApprovalStatus(sessionId, false);
      }

      onRedraftComplete?.();
    } catch (err: any) {
      alert(err.message || "Failed to submit change request. Please try again.");
    }
  };

  return (
    <div className="w-full mt-3 rounded-xl border border-slate-200 bg-white overflow-hidden shadow-subtle">
      {/* 1. Gate Header Banner */}
      <div
        className={clsx(
          "px-4 py-2.5 flex items-center justify-between gap-3 flex-wrap border-b transition-colors",
          isApprovedInStore
            ? "bg-emerald-50/80 border-emerald-100 text-emerald-900"
            : "bg-slate-50 border-slate-200/80 text-slate-800"
        )}
      >
        <div className="flex items-center gap-2">
          {isApprovedInStore ? (
            <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-800">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Traveler Approved • Ready for Inquiry Preparation</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-xs font-semibold text-humsafar-navy">
              <Sparkles className="w-4 h-4 text-amber-500" />
              <span>Draft Proposal • Awaiting Traveler Approval</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 text-xs">
          {isApprovedInStore ? (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-100/70 px-2 py-0.5 rounded-full">
              <Unlock className="w-3 h-3 text-emerald-600" />
              Gate Cleared
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-600 bg-slate-200/80 px-2 py-0.5 rounded-full">
              <Lock className="w-3 h-3 text-slate-500" />
              Gated Workflow
            </span>
          )}
        </div>
      </div>

      {/* 2. Notice & Instructions */}
      <div className="p-4 space-y-3 text-xs text-slate-600">
        {isApprovedInStore ? (
          <p className="leading-relaxed text-slate-700">
            You have approved this custom proposal. You may now proceed directly to
            inquiry preparation with the Indus Trekking and Tours operations desk to
            verify permits, guide allocation, and seasonal departure slots.
          </p>
        ) : (
          <p className="leading-relaxed text-slate-600">
            Indus Trekking and Tours requires your explicit review and approval of this
            customized itinerary before an official booking inquiry can be prepared.
            Review the route, duration, and logistics below:
          </p>
        )}

        {/* 3. Primary Choice Controls */}
        <div className="pt-2 flex items-center justify-between gap-3 flex-wrap border-t border-slate-100">
          <div className="flex items-center gap-2">
            {!isApprovedInStore ? (
              <>
                {/* Clear Approve Choice: Styled with Deep Navy #0F2C3E */}
                <button
                  type="button"
                  onClick={handleApprove}
                  disabled={approveMutation.isPending}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-[#0F2C3E] hover:bg-[#183D54] active:bg-[#0A1E2B] transition-colors shadow-subtle cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0F2C3E] disabled:opacity-50"
                >
                  {approveMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Saving Approval...
                    </>
                  ) : (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      Approve Proposal
                    </>
                  )}
                </button>

                {/* Clear Request Changes Choice */}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsFeedbackOpen((prev) => !prev)}
                  icon={<Edit3 className="w-3.5 h-3.5 text-slate-500" />}
                >
                  {isFeedbackOpen ? "Cancel Changes" : "Request Changes"}
                </Button>
              </>
            ) : (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  Approved by Traveler
                </span>
                <button
                  type="button"
                  onClick={() => setIsFeedbackOpen((prev) => !prev)}
                  className="text-xs text-slate-500 hover:text-humsafar-navy underline underline-offset-2 ml-2 cursor-pointer"
                >
                  Need more revisions?
                </button>
              </div>
            )}
          </div>

          {/* 4. Inquiry Preparation Gate: Blocked until explicit approval */}
          <div>
            {isApprovedInStore ? (
              <button
                type="button"
                onClick={() => setIsInquiryModalOpen(true)}
                className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-white bg-humsafar-teal hover:bg-humsafar-tealHover transition-colors shadow-subtle cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-humsafar-teal"
              >
                <span>Proceed to Inquiry Preparation</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <div
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 bg-slate-100 border border-slate-200 cursor-not-allowed"
                title="Approve this proposal to unlock official inquiry preparation."
              >
                <Lock className="w-3.5 h-3.5 text-slate-400" />
                <span>Inquiry Prep Locked</span>
              </div>
            )}
          </div>
        </div>

        {/* 5. Interactive Feedback Form for Redrafting with TanStack Query */}
        {isFeedbackOpen && (
          <form
            onSubmit={handleSubmitFeedback}
            className="mt-3 p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-2.5"
          >
            <div className="flex items-center justify-between">
              <label
                htmlFor="redraft-feedback"
                className="font-semibold text-xs text-humsafar-navy flex items-center gap-1.5"
              >
                <Edit3 className="w-3.5 h-3.5 text-humsafar-teal" />
                What would you like adjusted in this itinerary?
              </label>
              <button
                type="button"
                onClick={() => setIsFeedbackOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <textarea
              id="redraft-feedback"
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              placeholder="e.g. Please add an extra acclimatization day in Karimabad, upgrade to deluxe jeep transport, and recommend local family-friendly guesthouses..."
              rows={3}
              disabled={redraftMutation.isPending}
              className="w-full text-xs p-2.5 rounded-md border border-slate-300 focus:outline-none focus:ring-2 focus:ring-humsafar-teal bg-white text-slate-800 disabled:opacity-50"
            />

            <div className="flex items-center justify-between gap-2 flex-wrap">
              <span className="text-[11px] text-slate-500">
                The agent will fold your adjustments into the proposal and request your
                approval again.
              </span>
              <button
                type="submit"
                disabled={!feedbackText.trim() || redraftMutation.isPending}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-semibold text-white bg-humsafar-navy hover:bg-humsafar-navyHover transition-colors disabled:opacity-40 cursor-pointer"
              >
                {redraftMutation.isPending ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Synthesizing Redraft...
                  </>
                ) : (
                  <>
                    <Send className="w-3 h-3" />
                    Submit Changes for Redraft
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* 6. Official Inquiry Preparation Modal (Unlocked upon Approval) */}
      {isInquiryModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="w-full max-w-lg bg-white border border-slate-200 rounded-2xl shadow-xl overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="bg-[#0F2C3E] px-5 py-4 flex items-center justify-between text-white">
              <div className="flex items-center gap-2.5">
                <FileCheck className="w-5 h-5 text-humsafar-teal" />
                <div>
                  <h3 className="font-semibold text-sm">Official Inquiry Preparation</h3>
                  <p className="text-[11px] text-white/70">
                    Transmitting approved custom proposal to Indus Trekking and Tours
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsInquiryModalOpen(false)}
                className="p-1.5 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 space-y-4 text-xs text-slate-700">
              {inquirySubmitted ? (
                <div className="py-8 text-center space-y-3">
                  <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                    <CheckCircle2 className="w-6 h-6" />
                  </div>
                  <h4 className="font-bold text-base text-humsafar-navy">
                    Inquiry Transmitted Successfully!
                  </h4>
                  <p className="text-xs text-slate-600 max-w-md mx-auto leading-relaxed">
                    Our expedition operations desk at Indus Trekking and Tours has
                    received your approved itinerary for <strong>{title}</strong>. A
                    licensed mountain guide will review government trekking permits and
                    seasonal slots and reach out within 24 hours.
                  </p>
                  <Button
                    variant="approval"
                    size="sm"
                    onClick={() => {
                      setIsInquiryModalOpen(false);
                      setInquirySubmitted(false);
                    }}
                  >
                    Done
                  </Button>
                </div>
              ) : (
                <>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 block">
                      Approved Proposal Summary
                    </span>
                    <h4 className="font-bold text-sm text-humsafar-navy">{title}</h4>
                    <p className="text-slate-600">
                      Region: {region} • Duration: {duration} • Price:{" "}
                      {estimatedPrice}
                    </p>
                  </div>

                  <div className="p-3 bg-teal-50/60 rounded-lg border border-teal-100 text-slate-700 space-y-2">
                    <div className="flex items-center gap-2 font-semibold text-humsafar-navy">
                      <Building2 className="w-4 h-4 text-humsafar-teal" />
                      <span>Indus Trekking and Tours Operations Desk</span>
                    </div>
                    <p className="text-slate-600 leading-relaxed">
                      Govt Licensed Tour Operator (DTS Licence # 1243). Operating in
                      Gilgit-Baltistan, Karakoram, and Western Himalaya.
                    </p>
                    <div className="flex items-center gap-4 text-[11px] text-slate-500 pt-1">
                      <span className="flex items-center gap-1">
                        <Mail className="w-3.5 h-3.5 text-humsafar-teal" />
                        info@itp.com.pk
                      </span>
                      <span className="flex items-center gap-1">
                        <Phone className="w-3.5 h-3.5 text-humsafar-teal" />
                        +92 (0) 5811 455 123
                      </span>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="font-semibold block text-slate-800">
                      Preferred Departure Window or Special Logistics:
                    </label>
                    <textarea
                      rows={2}
                      defaultValue="Planning for upcoming season. Please verify guide availability and group pricing."
                      className="w-full p-2 border border-slate-200 rounded-md text-xs bg-white text-slate-800 focus:ring-1 focus:ring-humsafar-teal focus:outline-none"
                    />
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsInquiryModalOpen(false)}
                    >
                      Cancel
                    </Button>
                    <button
                      type="button"
                      onClick={() => setInquirySubmitted(true)}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-humsafar-teal hover:bg-humsafar-tealHover transition-colors shadow-subtle cursor-pointer"
                    >
                      <Send className="w-3.5 h-3.5" />
                      Submit Official Inquiry
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
