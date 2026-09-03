"use client";

import React from "react";
import Image from "next/image";
import { Mountain, Compass, ShieldAlert, Sparkles } from "lucide-react";
import { MessageBubble, MessageProps } from "./MessageBubble";
import { Button } from "@/components/ui/Button";

interface MessageListProps {
  messages: MessageProps[];
  isStreaming?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onApproveItinerary?: (messageId: string) => void;
  onSelectPrompt?: (prompt: string) => void;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isStreaming = false,
  error = null,
  onRetry,
  onApproveItinerary,
  onSelectPrompt,
}) => {
  // Empty State: Intentional mountain/river invitation
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-4 sm:px-6 py-12 max-w-chat mx-auto w-full text-center">
        <div className="w-16 h-16 rounded-2xl bg-humsafar-navy flex items-center justify-center p-2 mb-6 border border-humsafar-navyHover shadow-subtle">
          <Image
            src="/logo.png"
            alt="Humsafar Motif"
            width={48}
            height={48}
            className="object-contain"
          />
        </div>

        <h2 className="text-2xl sm:text-3xl font-bold text-humsafar-navy tracking-tight mb-3">
          Plan better. Travel farther.
        </h2>

        <p className="text-sm sm:text-base text-humsafar-mutedText max-w-md mx-auto leading-relaxed mb-8">
          Welcome to Indus Trekking and Tours Pakistan. Your expedition starts with verified, live route data across the Karakoram, Himalayas, and Hindukush.
        </p>

        {/* Actionable Expedition Starters */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg text-left">
          <button
            type="button"
            onClick={() => onSelectPrompt?.("Autumn foliage tour in Hunza Valley")}
            className="p-4 rounded-xl border border-slate-200 bg-white hover:border-humsafar-teal hover:shadow-subtle transition-all text-left cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-humsafar-teal"
          >
            <div className="flex items-center gap-2 mb-1">
              <Compass className="w-4 h-4 text-humsafar-teal" />
              <span className="font-semibold text-sm text-humsafar-navy">
                Hunza Autumn Blossom
              </span>
            </div>
            <p className="text-xs text-humsafar-mutedText leading-relaxed">
              Explore golden apricot valleys and ancient Silk Route forts.
            </p>
          </button>

          <button
            type="button"
            onClick={() => onSelectPrompt?.("K2 Base Camp expedition requirements")}
            className="p-4 rounded-xl border border-slate-200 bg-white hover:border-humsafar-teal hover:shadow-subtle transition-all text-left cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-humsafar-teal"
          >
            <div className="flex items-center gap-2 mb-1">
              <Mountain className="w-4 h-4 text-humsafar-teal" />
              <span className="font-semibold text-sm text-humsafar-navy">
                K2 & Concordia Expedition
              </span>
            </div>
            <p className="text-xs text-humsafar-mutedText leading-relaxed">
              Logistics, Baltoro glacier stages, and physical fitness guidelines.
            </p>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 max-w-chat mx-auto w-full">
      {/* Messages Feed with Claude-style generous vertical rhythm */}
      <div className="space-y-4 sm:space-y-6">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            {...msg}
            onApproveItinerary={() => onApproveItinerary?.(msg.id)}
          />
        ))}

        {/* Inline Error State */}
        {error && (
          <div className="my-6 p-4 rounded-xl border border-rose-200 bg-rose-50 text-slate-800 flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-semibold text-sm text-rose-900">
                  Live verification failed
                </h4>
                <p className="text-xs text-rose-700 mt-0.5">{error}</p>
              </div>
            </div>
            {onRetry && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRetry}
                className="!text-rose-900 !border-rose-300 hover:!bg-rose-100 shrink-0"
              >
                Retry
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
