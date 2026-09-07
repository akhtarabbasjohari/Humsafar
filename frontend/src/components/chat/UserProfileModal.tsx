"use client";

import React, { useEffect } from "react";
import { X, Mail, Phone, ShieldCheck, Bookmark, LogOut, Mountain } from "lucide-react";
import { UserProfile } from "@/lib/api";

interface UserProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserProfile | null;
  savedCount?: number;
  onLogout?: () => void;
  onViewSavedItineraries?: () => void;
}

export const UserProfileModal: React.FC<UserProfileModalProps> = ({
  isOpen,
  onClose,
  user,
  savedCount = 0,
  onLogout,
  onViewSavedItineraries,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !user) return null;

  const initials = user.username ? user.username.slice(0, 2).toUpperCase() : "HU";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="fixed inset-0" onClick={onClose} />

      <div className="relative w-full max-w-sm bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden z-10 animate-in zoom-in-95 duration-150">
        <div className="bg-gradient-to-r from-humsafar-navy via-[#163a50] to-humsafar-navy px-6 pt-6 pb-8 text-white relative">
          <button
            type="button"
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-full text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-3.5">
            <div className="w-14 h-14 rounded-full bg-humsafar-teal text-white flex items-center justify-center text-lg font-bold shadow-md border-2 border-white/20 shrink-0">
              {initials}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <h3 className="text-base font-bold text-white truncate leading-tight">
                  {user.username}
                </h3>
                <span title="Verified Member" className="inline-flex items-center">
                  <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-0.5 truncate">
                Member Traveler
              </p>
            </div>
          </div>
        </div>

        <div className="p-5 space-y-4">
          <div className="space-y-3 text-xs">
            <div className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-50 border border-slate-100">
              <div className="w-7 h-7 rounded-lg bg-teal-50 text-humsafar-teal flex items-center justify-center shrink-0">
                <Mail className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0 flex-1">
                <span className="block text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                  Email Address
                </span>
                <span className="block font-semibold text-slate-700 truncate">
                  {user.email || "No email on file"}
                </span>
              </div>
            </div>

            {user.phone_number && (
              <div className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                  <Phone className="w-3.5 h-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <span className="block text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                    Phone / WhatsApp
                  </span>
                  <span className="block font-semibold text-slate-700 truncate">
                    {user.phone_number}
                  </span>
                </div>
              </div>
            )}

            <div className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-50 border border-slate-100">
              <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                <Mountain className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0 flex-1">
                <span className="block text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                  Expedition Portal
                </span>
                <span className="block font-semibold text-slate-700 truncate">
                  Askoli Adventure Partner
                </span>
              </div>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                Active
              </span>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100 space-y-2">
            {onViewSavedItineraries && (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onViewSavedItineraries();
                }}
                className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold text-humsafar-navy bg-humsafar-tealTint hover:bg-teal-100/60 transition-colors cursor-pointer border border-humsafar-tealBorder"
              >
                <div className="flex items-center gap-2">
                  <Bookmark className="w-3.5 h-3.5 text-humsafar-teal" />
                  <span>Saved Itineraries</span>
                </div>
                <span className="px-2 py-0.5 rounded-full bg-white text-humsafar-navy text-[11px] font-bold shadow-xs">
                  {savedCount}
                </span>
              </button>
            )}

            {onLogout && (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onLogout();
                }}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-rose-600 hover:bg-rose-50 hover:text-rose-700 transition-colors cursor-pointer border border-transparent hover:border-rose-200"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Sign Out of Account</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
