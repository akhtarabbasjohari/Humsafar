"use client";

import React, { useState } from "react";
import Image from "next/image";

import {
  PanelLeft,
  ChevronDown,
  User,
  Lock,
  Bookmark,
  Pencil,
  Check,
  X,
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
  onOpenProfile?: () => void;
  onRenameActiveChat?: (newTitle: string) => void;
  onOpenEditModal?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  isSidebarOpen,
  onToggleSidebar,
  activeChatTitle,
  onOpenAuth,
  activeView,
  user,
  onViewItineraries,
  onOpenProfile,
  onRenameActiveChat,
  onOpenEditModal,
}) => {
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState(activeChatTitle);

  const handleStartEditing = () => {
    setEditedTitle(activeChatTitle);
    setIsEditingTitle(true);
  };

  const handleSaveTitle = () => {
    const trimmed = editedTitle.trim();
    if (trimmed && trimmed !== activeChatTitle && onRenameActiveChat) {
      onRenameActiveChat(trimmed);
    }
    setIsEditingTitle(false);
  };

  const handleCancelEditing = () => {
    setEditedTitle(activeChatTitle);
    setIsEditingTitle(false);
  };

  const handleProfileClick = () => {
    if (user && onOpenProfile) {
      onOpenProfile();
    } else {
      onOpenAuth();
    }
  };

  return (
    <header className="sticky top-0 z-30 h-14 bg-white border-b border-slate-200/80 px-4 flex items-center justify-between shrink-0">
      {/* Left: Sidebar Toggle and Active Chat Title with Inline Rename */}
      <div className="flex items-center gap-2 sm:gap-3 truncate">
        {!isSidebarOpen && (
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={onToggleSidebar}
              className="p-1.5 text-slate-500 hover:text-humsafar-navy hover:bg-slate-100 rounded-md transition-colors cursor-pointer shrink-0"
              title="Open sidebar"
            >
              <PanelLeft className="w-4 h-4" />
            </button>
            <div className="w-6 h-6 rounded-md bg-white border border-slate-200 flex items-center justify-center p-0.5 shrink-0 shadow-xs">
              <Image
                src="/logo.png"
                alt="Humsafar Logo"
                width={18}
                height={18}
                className="object-contain"
              />
            </div>
          </div>
        )}

        {/* Chat Title with Inline Editing */}
        {isEditingTitle ? (
          <div className="flex items-center gap-1.5">
            <input
              type="text"
              value={editedTitle}
              onChange={(e) => setEditedTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSaveTitle();
                if (e.key === "Escape") handleCancelEditing();
              }}
              autoFocus
              className="text-xs sm:text-sm font-semibold text-humsafar-navy px-2 py-0.5 rounded border border-humsafar-teal focus:outline-none focus:ring-1 focus:ring-humsafar-teal bg-teal-50/40 w-44 sm:w-64"
            />
            <button
              type="button"
              onClick={handleSaveTitle}
              className="p-1 text-emerald-600 hover:bg-emerald-50 rounded cursor-pointer"
              title="Save chat title"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleCancelEditing}
              className="p-1 text-slate-400 hover:bg-slate-100 rounded cursor-pointer"
              title="Cancel"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="group flex items-center gap-1.5 text-sm font-semibold text-humsafar-navy px-2 py-1 rounded-md truncate text-left">
            <span className="truncate max-w-[180px] sm:max-w-[380px]">
              {activeChatTitle}
            </span>
            {(onOpenEditModal || onRenameActiveChat) && (
              <button
                type="button"
                onClick={onOpenEditModal || handleStartEditing}
                className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-humsafar-teal hover:bg-slate-100 rounded transition-all cursor-pointer shrink-0"
                title="Rename this chat"
              >
                <Pencil className="w-3 h-3" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Right: Live Grounding Badge & Auth / Profile Status */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Live Grounding Status Pill */}
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>askoliadventure.com live</span>
        </div>

        {/* Member / Guest Status Pill */}
        {user ? (
          <button
            type="button"
            onClick={handleProfileClick}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-humsafar-tealTint text-humsafar-navy border border-humsafar-tealBorder text-xs font-semibold hover:bg-teal-100/60 transition-colors cursor-pointer"
            title="Click to view profile details"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-humsafar-teal" />
            <span className="hidden sm:inline">Member:</span>
            <span>{user.username}</span>
          </button>
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
          onClick={handleProfileClick}
          className="p-1.5 rounded-md border border-slate-200 hover:bg-slate-50 text-slate-700 transition-colors cursor-pointer"
          title={user ? "View Profile Details" : "Sign In / Register"}
        >
          <User className="w-4 h-4 text-humsafar-teal" />
        </button>
      </div>
    </header>
  );
};

