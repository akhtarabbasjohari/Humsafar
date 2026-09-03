"use client";

import React from "react";
import Image from "next/image";
import { RefreshCw, User, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface HeaderProps {
  onOpenAuth: () => void;
  onNewChat: () => void;
  activeView: "chat" | "auth";
  isStreaming?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onOpenAuth,
  onNewChat,
  activeView,
  isStreaming = false,
}) => {
  return (
    <header className="sticky top-0 z-30 w-full bg-humsafar-navy text-white border-b border-humsafar-navyHover/80">
      <div className="max-w-chat mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Left: Brand Identity */}
        <div className="flex items-center gap-3">
          <div className="relative w-9 h-9 rounded-lg overflow-hidden bg-black/20 p-1 border border-white/10 flex items-center justify-center shrink-0">
            <Image
              src="/logo.png"
              alt="Humsafar Logo"
              width={36}
              height={36}
              className="object-contain"
              priority
            />
          </div>

          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="font-semibold tracking-wide text-base text-white">
                Humsafar
              </span>
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-humsafar-teal/20 text-humsafar-tealBorder border border-humsafar-teal/30">
                <span className="w-1.5 h-1.5 rounded-full bg-humsafar-teal animate-pulse" />
                Live Scrape
              </span>
            </div>
            <p className="text-xs text-white/70 font-normal">
              Indus Trekking & Tours Pakistan
            </p>
          </div>
        </div>

        {/* Right: Controls */}
        <div className="flex items-center gap-2">
          <Button
            variant="header"
            size="sm"
            onClick={onNewChat}
            disabled={isStreaming}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
            title="Reset conversation"
            className="hidden sm:inline-flex"
          >
            New Trip
          </Button>

          <Button
            variant="header"
            size="sm"
            onClick={onOpenAuth}
            icon={<User className="w-3.5 h-3.5 text-humsafar-teal" />}
            className={activeView === "auth" ? "!bg-humsafar-teal !text-white" : ""}
          >
            {activeView === "auth" ? "Back to Chat" : "Guest / Account"}
          </Button>
        </div>
      </div>
    </header>
  );
};
