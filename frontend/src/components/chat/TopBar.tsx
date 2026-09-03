"use client";

import React from "react";
import {
  PanelLeft,
  ChevronDown,
  Share2,
  FileText,
  User,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

interface TopBarProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  activeChatTitle: string;
  onOpenAuth: () => void;
  activeView: "chat" | "auth";
}

export const TopBar: React.FC<TopBarProps> = ({
  isSidebarOpen,
  onToggleSidebar,
  activeChatTitle,
  onOpenAuth,
  activeView,
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

        {/* Chat Title with Dropdown (Claude Style) */}
        <button
          type="button"
          className="flex items-center gap-1.5 text-sm font-semibold text-humsafar-navy hover:bg-slate-100 px-2 py-1 rounded-md transition-colors truncate cursor-pointer text-left"
        >
          <span className="truncate max-w-[200px] sm:max-w-[400px]">
            {activeChatTitle}
          </span>
          <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
        </button>
      </div>

      {/* Right: Live Grounding Badge & Action Controls (Claude Style) */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Live Grounding Status Pill (matches 82% used pill in Claude) */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>itp.7scribes.com live</span>
        </div>

        {/* Share Button (Claude Style) */}
        <button
          type="button"
          onClick={() => {}}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-slate-200 hover:bg-slate-50 text-xs font-medium text-slate-700 transition-colors cursor-pointer"
        >
          <Share2 className="w-3.5 h-3.5 text-slate-500" />
          <span className="hidden sm:inline">Share</span>
        </button>

        {/* Account / Guest Toggle */}
        <button
          type="button"
          onClick={onOpenAuth}
          className="p-1.5 rounded-md border border-slate-200 hover:bg-slate-50 text-slate-700 transition-colors cursor-pointer"
          title="Account / Guest mode"
        >
          <User className="w-4 h-4 text-humsafar-teal" />
        </button>
      </div>
    </header>
  );
};
