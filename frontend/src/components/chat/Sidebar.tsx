"use client";

import React, { useState } from "react";
import Image from "next/image";

import {
  Plus,
  Compass,
  Bookmark,
  PanelLeftClose,
  ChevronDown,
  ExternalLink,
  MessageSquare,
  Sparkles,
  Lock,
  Trash2,
  LogOut,
  Pencil,
  Check,
  X,
} from "lucide-react";
import clsx from "clsx";
import { UserProfile } from "@/lib/api";

export interface ChatSessionItem {
  id: string;
  title: string;
  isPinned?: boolean;
  timestamp?: string;
}

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  activeSessionId: string;
  activeChatTitle?: string;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onOpenAuth: () => void;
  user?: UserProfile | null;
  sessions?: ChatSessionItem[];
  onDeleteSession?: (id: string) => void;
  onLogout?: () => void;
  onViewItineraries?: () => void;
  savedItinerariesCount?: number;
  onOpenProfile?: () => void;
  onRenameSession?: (sessionId: string, newTitle: string) => void;
  onOpenEditModal?: (session: ChatSessionItem) => void;
  onOpenDeleteModal?: (session: ChatSessionItem) => void;
  inFlightSessionIds?: Set<string>;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onToggle,
  activeSessionId,
  activeChatTitle,
  onSelectSession,
  onNewChat,
  onOpenAuth,
  user,
  sessions = [],
  onDeleteSession,
  onLogout,
  onViewItineraries,
  savedItinerariesCount = 0,
  onOpenProfile,
  onRenameSession,
  onOpenEditModal,
  onOpenDeleteModal,
  inFlightSessionIds,
}) => {

  const isGuest = !user;
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");

  const handleStartRename = (session: ChatSessionItem) => {
    setEditingSessionId(session.id);
    setEditingTitle(session.title);
  };

  const handleSaveRename = (sessionId: string) => {
    const trimmed = editingTitle.trim();
    if (trimmed && onRenameSession) {
      onRenameSession(sessionId, trimmed);
    }
    setEditingSessionId(null);
  };

  const handleCancelRename = () => {
    setEditingSessionId(null);
  };

  const handleNewChatClick = () => {

    if (isGuest) {
      onOpenAuth();
    } else {
      onNewChat();
    }
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={onToggle}
          className="fixed inset-0 bg-black/40 z-40 md:hidden backdrop-blur-xs transition-opacity"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={clsx(
          "fixed md:static inset-y-0 left-0 z-50 flex flex-col bg-slate-50 border-r border-slate-200 transition-all duration-200 ease-in-out select-none",
          isOpen
            ? "w-68 sm:w-72 translate-x-0"
            : "-translate-x-full md:translate-x-0 md:w-0 md:border-none overflow-hidden"
        )}
      >
        {/* Sidebar Header: Brand & Collapse Toggle */}
        <div className="h-14 px-4 flex items-center justify-between border-b border-slate-200/80 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-white border border-slate-200 flex items-center justify-center p-0.5 shrink-0 shadow-xs">
              <Image
                src="/logo.png"
                alt="Humsafar"
                width={22}
                height={22}
                className="object-contain"
              />
            </div>
            <span className="font-semibold text-sm text-humsafar-navy tracking-tight">
              Humsafar
            </span>
          </div>

          <button
            type="button"
            onClick={onToggle}
            className="p-1.5 text-slate-500 hover:text-humsafar-navy hover:bg-slate-200/60 rounded-md transition-colors cursor-pointer"
            title="Close sidebar"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>

        {/* Action: + New Chat Button */}
        <div className="p-3 shrink-0">
          <button
            type="button"
            onClick={handleNewChatClick}
            className={clsx(
              "w-full flex items-center justify-between px-3 py-2 bg-white border rounded-lg text-xs font-semibold shadow-xs transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-humsafar-teal",
              isGuest
                ? "border-amber-200 hover:border-amber-300 text-slate-800"
                : "border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-800"
            )}
            title={isGuest ? "Sign in to unlock multiple chat sessions" : "Start a new chat"}
          >
            <div className="flex items-center gap-2">
              <Plus className="w-4 h-4 text-humsafar-teal" />
              <span>New plan</span>
            </div>

            {isGuest ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                <Lock className="w-3 h-3" />
                <span>Member</span>
              </span>
            ) : null}
          </button>
        </div>

        {/* Primary Navigation Links */}
        <div className="px-3 pb-2 space-y-0.5 text-xs text-slate-600 shrink-0">
          <a
            href="https://askoliadventure.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between px-2.5 py-1.5 rounded-md hover:bg-slate-200/60 hover:text-humsafar-navy transition-colors"
          >
            <div className="flex items-center gap-2">
              <Compass className="w-3.5 h-3.5 text-slate-500" />
              <span>Live Catalog</span>
            </div>
            <ExternalLink className="w-3 h-3 text-slate-400" />
          </a>

          {!isGuest && (
            <button
              type="button"
              onClick={onViewItineraries}
              className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-md hover:bg-slate-200/60 hover:text-humsafar-navy transition-colors text-left cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Bookmark className="w-3.5 h-3.5 text-slate-500" />
                <span>Saved Itineraries</span>
              </div>
              <span className="text-[10px] font-medium bg-slate-200 text-slate-700 px-1.5 py-0.2 rounded-full">
                {savedItinerariesCount}
              </span>
            </button>
          )}
        </div>

        {/* Scrollable Chat Sessions Section */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-4 text-xs">
          {/* Guest Mode: Only 1 Active Session Allowed */}
          {isGuest ? (
            <div className="space-y-3">
              <div className="space-y-1">
                <div className="px-2.5 text-[11px] font-medium text-slate-400">
                  Current Session (Guest Mode)
                </div>
                <div className="w-full flex items-center gap-2 px-2.5 py-2 rounded-md bg-slate-200/90 text-humsafar-navy font-medium truncate shadow-xs">
                  <span className="w-2 h-2 rounded-full bg-humsafar-teal shrink-0 animate-pulse" />
                  <span className="truncate">
                    {activeChatTitle || "Current Expedition Chat"}
                  </span>
                </div>
              </div>

              {/* Member Upgrade Invitation Card */}
              <div className="p-3.5 rounded-xl bg-humsafar-navy text-white space-y-2.5 shadow-sm border border-humsafar-navyHover">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-white">
                  <Sparkles className="w-3.5 h-3.5 text-humsafar-teal" />
                  <span>Multiple Expeditions</span>
                </div>
                <p className="text-[11px] text-white/75 leading-relaxed">
                  Sign in or register to organize multiple trips, save approved itineraries, and manage past chats from any device.
                </p>
                <button
                  type="button"
                  onClick={onOpenAuth}
                  className="w-full py-1.5 text-xs font-semibold text-humsafar-navy bg-white hover:bg-slate-100 rounded-lg transition-colors cursor-pointer text-center"
                >
                  Sign In / Register
                </button>
              </div>
            </div>
          ) : (
            /* Member Mode: Full Multiple Chats Enabled */
            <div className="space-y-1">
              <div className="px-2.5 text-[11px] font-medium text-slate-400 flex items-center justify-between">
                <span>My Chats & Expeditions</span>
                <span className="text-[10px] text-humsafar-teal font-medium">
                  {sessions.length} active
                </span>
              </div>

              {sessions.length === 0 ? (
                <div className="px-2.5 py-4 text-center text-slate-400 text-xs">
                  No previous chats. Start a new expedition plan!
                </div>
              ) : (
                sessions.map((session) => {
                  const isActive = activeSessionId === session.id;
                  const isRenaming = editingSessionId === session.id;
                  const isInFlight = inFlightSessionIds?.has(session.id);

                  if (isRenaming) {
                    return (
                      <div
                        key={session.id}
                        className="flex items-center gap-1 px-2 py-1 bg-white rounded-md border border-humsafar-teal shadow-xs my-0.5"
                      >
                        <input
                          type="text"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleSaveRename(session.id);
                            if (e.key === "Escape") handleCancelRename();
                          }}
                          autoFocus
                          className="flex-1 text-xs text-humsafar-navy px-1 py-0.5 outline-none font-medium bg-transparent"
                        />
                        <button
                          type="button"
                          onClick={() => handleSaveRename(session.id)}
                          className="p-1 text-emerald-600 hover:bg-emerald-50 rounded cursor-pointer"
                          title="Save title"
                        >
                          <Check className="w-3 h-3" />
                        </button>
                        <button
                          type="button"
                          onClick={handleCancelRename}
                          className="p-1 text-slate-400 hover:bg-slate-100 rounded cursor-pointer"
                          title="Cancel"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={session.id}
                      className={clsx(
                        "group w-full flex items-center justify-between px-2.5 py-1.5 rounded-md transition-colors truncate",
                        isActive
                          ? "bg-slate-200/90 text-humsafar-navy font-medium"
                          : "text-slate-600 hover:bg-slate-200/50 hover:text-slate-900"
                      )}
                    >
                      <button
                        type="button"
                        onClick={() => onSelectSession(session.id)}
                        className="flex-1 flex items-center gap-2 text-left truncate cursor-pointer mr-1"
                      >
                        <MessageSquare
                          className={clsx(
                            "w-3 h-3 shrink-0",
                            isActive ? "text-humsafar-teal" : "text-slate-400"
                          )}
                        />
                        <span className="truncate">{session.title}</span>
                        {isInFlight && (
                          <span
                            className="flex items-center gap-1 text-humsafar-teal shrink-0 ml-auto mr-1"
                            title="Researching in background..."
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-humsafar-teal animate-ping" />
                          </span>
                        )}
                      </button>

                      <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                        {(onOpenEditModal || onRenameSession) && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (onOpenEditModal) {
                                onOpenEditModal(session);
                              } else {
                                handleStartRename(session);
                              }
                            }}
                            className="p-1 text-slate-400 hover:text-humsafar-teal rounded transition-colors cursor-pointer"
                            title="Rename chat"
                          >
                            <Pencil className="w-3 h-3" />
                          </button>
                        )}
                        {(onOpenDeleteModal || onDeleteSession) && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (onOpenDeleteModal) {
                                onOpenDeleteModal(session);
                              } else if (onDeleteSession) {
                                if (window.confirm(`Delete "${session.title}"?`)) {
                                  onDeleteSession(session.id);
                                }
                              }
                            }}
                            className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors cursor-pointer"
                            title="Delete chat"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* User Profile Footer */}
        <div className="p-3 border-t border-slate-200/80 shrink-0 bg-slate-50 flex items-center justify-between gap-2">
          {user ? (
            <div className="flex items-center justify-between w-full">
              <button
                type="button"
                onClick={onOpenProfile}
                className="flex items-center gap-2.5 min-w-0 text-left hover:opacity-85 transition-opacity cursor-pointer flex-1"
                title="View profile details"
              >
                <div className="w-7 h-7 rounded-full bg-humsafar-teal text-white flex items-center justify-center text-xs font-semibold shrink-0 shadow-xs">
                  {user.username.slice(0, 2).toUpperCase()}
                </div>
                <div className="flex flex-col truncate">
                  <span className="text-xs font-semibold text-humsafar-navy truncate">
                    {user.username}
                  </span>
                  <span className="text-[10px] text-emerald-600 font-medium">
                    Member Account
                  </span>
                </div>
              </button>
              {onLogout && (
                <button
                  type="button"
                  onClick={onLogout}
                  title="Sign out"
                  className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-slate-200/60 rounded-md transition-colors cursor-pointer shrink-0"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              )}
            </div>

          ) : (
            <button
              type="button"
              onClick={onOpenAuth}
              className="w-full flex items-center justify-between p-1.5 rounded-lg hover:bg-slate-200/60 transition-colors cursor-pointer text-left"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-full bg-humsafar-navy text-white flex items-center justify-center text-xs font-semibold shrink-0">
                  IT
                </div>
                <div className="flex flex-col truncate">
                  <span className="text-xs font-semibold text-humsafar-navy truncate">
                    Guest Traveler
                  </span>
                  <span className="text-[10px] text-humsafar-teal font-medium">
                    Sign In / Register
                  </span>
                </div>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            </button>
          )}
        </div>
      </aside>
    </>
  );
};
