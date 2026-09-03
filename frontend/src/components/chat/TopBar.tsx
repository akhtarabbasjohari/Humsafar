"use client";

import React from "react";
import {
  PanelLeft,
  ChevronDown,
  Share2,
  User,
  Lock,
  Bookmark,
} from "lucide-react";
import { UserProfile } from "@/lib/api";

interface TopBarProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  activeChatTitle: string;
  onOpenAuth: () => void;
  activeView: "chat" | "auth";
  user?: UserProfile | null;
  onViewItineraries?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  isSidebarOpen,
  onToggleSidebar,
  activeChatTitle,
  onOpenAuth,
  activeView,
  user,
  onViewItineraries,
}) => {
  return (
    <header className="sticky top-0 z-30 h-14 bg-white border-b border-slate-200/80 px-4 flex items-center justify-between shrink-0">
      {/* Left: Sidebar Toggle and Active Chat Title Dropdown */}
      <div className="flex items-center gap-3 truncate">
        {!isSidebarOpen && (
          <button
            type="button"
            onClick={onToggleSidebar}
            className="p-1.5 text-slate-500 hover:text-humsafar-navy hover:bg-slate-100 rounded-md transition-colors cursor-pointer shrink-0"
            title="Open sidebar"
          >
            <PanelLeft className="w-4 h-4" />
          </button>
        )}

        {/* Chat Title with Dropdown */}
        <div className="flex items-center gap-1.5 text-sm font-semibold text-humsafar-navy px-2 py-1 rounded-md truncate text-left">
          <span className="truncate max-w-[200px] sm:max-w-[400px]">
            {activeChatTitle}
          </span>
        </div>
      </div>

      {/* Right: Live Grounding Badge & Auth Status */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Live Grounding Status Pill */}
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>itp.7scribes.com live</span>
        </div>

        {/* Member / Guest Status Pill */}
        {user ? (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-humsafar-tealTint text-humsafar-navy border border-humsafar-tealBorder text-xs font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-humsafar-teal" />
            <span className="hidden sm:inline">Member:</span>
            <span>{user.username}</span>
          </div>
        ) : (
          <button
            type="button"
            onClick={onOpenAuth}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 text-amber-900 border border-amber-200 text-xs font-medium hover:bg-amber-100 transition-colors cursor-pointer"
            title="Click to sign in and unlock multiple chats"
          >
            <Lock className="w-3 h-3 text-amber-600 shrink-0" />
            <span className="hidden sm:inline">Guest Mode •</span>
            <span>Sign In</span>
          </button>
        )}

        {/* User Profile Button */}
        <button
          type="button"
          onClick={onOpenAuth}
          className="p-1.5 rounded-md border border-slate-200 hover:bg-slate-50 text-slate-700 transition-colors cursor-pointer"
          title={user ? "Account Settings" : "Sign In / Register"}
        >
          <User className="w-4 h-4 text-humsafar-teal" />
        </button>
      </div>
    </header>
  );
};
