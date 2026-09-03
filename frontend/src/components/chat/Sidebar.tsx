"use client";

import React, { useState } from "react";
import Image from "next/image";
import {
  Plus,
  Compass,
  FolderClosed,
  Bookmark,
  Code2,
  Sliders,
  PanelLeftClose,
  PanelLeft,
  ChevronDown,
  Download,
  ExternalLink,
  MessageSquare,
  Sparkles,
  Mountain,
  MapPin,
  User,
} from "lucide-react";
import clsx from "clsx";

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
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onOpenAuth: () => void;
}

const PINNED_SESSIONS: ChatSessionItem[] = [
  { id: "pin-1", title: "K2 & Concordia Classic Trek", isPinned: true },
  { id: "pin-2", title: "Hunza Autumn 7-Day Foliage", isPinned: true },
  { id: "pin-3", title: "Fairy Meadows & Nanga Parbat", isPinned: true },
];

const RECENT_SESSIONS: ChatSessionItem[] = [
  { id: "rec-1", title: "Hunza Autumn Foliage & Heritage Trail" },
  { id: "rec-2", title: "Skardu & Deosai Plains Family Tour" },
  { id: "rec-3", title: "Shimshal Valley & Passu Glacier Expedition" },
  { id: "rec-4", title: "Swat & Kalam Alpine Exploration" },
];

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onToggle,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onOpenAuth,
}) => {
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
            <div className="w-7 h-7 rounded-lg bg-humsafar-navy flex items-center justify-center p-0.5 shrink-0 shadow-xs">
              <Image
                src="/logo.png"
                alt="Humsafar"
                width={24}
                height={24}
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

        {/* Action: + New Chat Button (Claude Style) */}
        <div className="p-3 shrink-0">
          <button
            type="button"
            onClick={onNewChat}
            className="w-full flex items-center gap-2.5 px-3 py-2 bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-800 rounded-lg text-xs font-semibold shadow-xs transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-humsafar-teal"
          >
            <Plus className="w-4 h-4 text-humsafar-teal" />
            <span>New plan</span>
          </button>
        </div>

        {/* Primary Navigation Sections (Claude Style) */}
        <div className="px-3 pb-2 space-y-0.5 text-xs text-slate-600 shrink-0">
          <a
            href="https://itp.7scribes.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between px-2.5 py-1.5 rounded-md hover:bg-slate-200/60 hover:text-humsafar-navy transition-colors"
          >
            <div className="flex items-center gap-2">
              <Compass className="w-3.5 h-3.5 text-slate-500" />
              <span>Live Website</span>
            </div>
            <ExternalLink className="w-3 h-3 text-slate-400" />
          </a>

          <button
            type="button"
            onClick={() => {}}
            className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-md hover:bg-slate-200/60 hover:text-humsafar-navy transition-colors text-left"
          >
            <div className="flex items-center gap-2">
              <FolderClosed className="w-3.5 h-3.5 text-slate-500" />
              <span>Expeditions</span>
            </div>
            <span className="text-[10px] text-slate-400">12</span>
          </button>

          <button
            type="button"
            onClick={() => {}}
            className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-md hover:bg-slate-200/60 hover:text-humsafar-navy transition-colors text-left"
          >
            <div className="flex items-center gap-2">
              <Bookmark className="w-3.5 h-3.5 text-slate-500" />
              <span>Saved Itineraries</span>
            </div>
            <span className="text-[10px] text-slate-400">3</span>
          </button>
        </div>

        {/* Scrollable Chat Sessions List (Claude Style) */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-4 text-xs">
          {/* Pinned Section */}
          <div className="space-y-1">
            <div className="px-2.5 text-[11px] font-medium text-slate-400">
              Pinned
            </div>
            {PINNED_SESSIONS.map((session) => {
              const isActive = activeSessionId === session.id;
              return (
                <button
                  key={session.id}
                  type="button"
                  onClick={() => onSelectSession(session.id)}
                  className={clsx(
                    "w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-left transition-colors truncate cursor-pointer",
                    isActive
                      ? "bg-slate-200/90 text-humsafar-navy font-medium"
                      : "text-slate-700 hover:bg-slate-200/50 hover:text-slate-900"
                  )}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-humsafar-teal shrink-0" />
                  <span className="truncate">{session.title}</span>
                </button>
              );
            })}
          </div>

          {/* Recent Chats Section */}
          <div className="space-y-1">
            <div className="px-2.5 text-[11px] font-medium text-slate-400">
              Chats and plans
            </div>
            {RECENT_SESSIONS.map((session) => {
              const isActive = activeSessionId === session.id;
              return (
                <button
                  key={session.id}
                  type="button"
                  onClick={() => onSelectSession(session.id)}
                  className={clsx(
                    "w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-left transition-colors truncate cursor-pointer",
                    isActive
                      ? "bg-slate-200/90 text-humsafar-navy font-medium"
                      : "text-slate-600 hover:bg-slate-200/50 hover:text-slate-900"
                  )}
                >
                  <MessageSquare className="w-3 h-3 text-slate-400 shrink-0" />
                  <span className="truncate">{session.title}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* User Profile Footer (Claude Style) */}
        <div className="p-3 border-t border-slate-200/80 shrink-0 bg-slate-50">
          <button
            type="button"
            onClick={onOpenAuth}
            className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-slate-200/60 transition-colors cursor-pointer text-left"
          >
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-humsafar-navy text-white flex items-center justify-center text-xs font-semibold shrink-0">
                IT
              </div>
              <div className="flex flex-col truncate">
                <span className="text-xs font-semibold text-humsafar-navy truncate">
                  Indus Traveler
                </span>
                <span className="text-[10px] text-slate-500">
                  Guest Session • Active
                </span>
              </div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          </button>
        </div>
      </aside>
    </>
  );
};
