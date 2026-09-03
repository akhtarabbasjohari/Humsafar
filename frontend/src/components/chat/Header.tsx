"use client";

import React from "react";
import Image from "next/image";
import { Compass, Sparkles, User, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

interface HeaderProps {
  onOpenAuth: () => void;
  onNewChat: () => void;
  activeView: "chat" | "auth";
}

export const Header: React.FC<HeaderProps> = ({
  onOpenAuth,
  onNewChat,
  activeView,
}) => {
  return (
    <header className="sticky top-0 z-30 w-full bg-humsafar-header text-white border-b border-humsafar-alpineBorder shadow-card">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 sm:h-18 flex items-center justify-between">
        {/* Left: Brand Identity with Logo and Tagline */}
        <div className="flex items-center gap-3 sm:gap-4">
          <div className="relative w-10 h-10 sm:w-11 sm:h-11 rounded-xl overflow-hidden bg-[#0A2219] p-1 border border-humsafar-alpineBorder flex items-center justify-center shrink-0 shadow-inner">
            <Image
              src="/logo.png"
              alt="Humsafar Logo"
              width={44}
              height={44}
              className="object-contain"
              priority
            />
          </div>

          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="font-semibold tracking-wider text-base sm:text-lg text-[#FFFDF7]">
                HUMSAFAR
              </span>
              <Badge variant="live" className="hidden sm:inline-flex text-[10px]">
                Live Ground Truth
              </Badge>
            </div>
            <div className="flex items-center gap-2 text-xs text-[#D8EADB]/80 font-light">
              <span className="text-humsafar-accent font-medium italic">
                Plan better. Travel farther.
              </span>
              <span className="hidden md:inline text-white/30">•</span>
              <span className="hidden md:inline text-white/70">
                Indus Trekking & Tours Pakistan
              </span>
            </div>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2 sm:gap-3">
          <Button
            variant="header"
            size="sm"
            onClick={onNewChat}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
            title="Start new planning session"
            className="hidden sm:inline-flex"
          >
            New Plan
          </Button>

          <Button
            variant="header"
            size="sm"
            onClick={onOpenAuth}
            icon={<User className="w-3.5 h-3.5 text-humsafar-accent" />}
            className={activeView === "auth" ? "!bg-humsafar-accent !text-white font-semibold" : ""}
          >
            {activeView === "auth" ? "Back to Chat" : "Guest Mode / Account"}
          </Button>
        </div>
      </div>
    </header>
  );
};
