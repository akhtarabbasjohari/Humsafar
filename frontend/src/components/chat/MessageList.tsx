"use client";

import React from "react";
import { Mountain, MapPin, Sparkles, ShieldCheck } from "lucide-react";
import { MessageBubble, MessageProps } from "./MessageBubble";
import { Badge } from "@/components/ui/Badge";

const PLACEHOLDER_MESSAGES: MessageProps[] = [
  {
    id: "1",
    sender: "agent",
    timestamp: "10:42 AM",
    content:
      "Salam and welcome to Indus Trekking and Tours Pakistan! I'm Humsafar, your AI travel companion. Every route, trek grade, and seasonal advisory I present is verified live from our official website (itp.7scribes.com).\n\nWhere in Pakistan's majestic north are you dreaming of exploring?",
    verifiedSource: "Ground truth verified live from itp.7scribes.com • 2026-09-03",
  },
  {
    id: "2",
    sender: "user",
    timestamp: "10:44 AM",
    content:
      "I want to plan a 7-day autumn trip to Hunza Valley in late October for 2 people. Can you recommend a route with cultural highlights, golden apricot foliage, and moderate walking?",
  },
  {
    id: "3",
    sender: "agent",
    timestamp: "10:45 AM",
    content:
      "Late October is the pinnacle of the Hunza autumn blossom! The apricot and poplar trees turn radiant gold and amber against the snow-dusted peaks of Rakaposhi and Ladyfinger.\n\nBased on live expedition schedules and verified valley logistics from Indus Trekking & Tours, I have synthesized a 7-day personalized itinerary draft for you below. As part of our traveler commitment, this is a draft until you explicitly approve it.",
    verifiedSource: "Verified live from itp.7scribes.com on 2026-09-03 10:45 PKT",
    itineraryDraft: {
      title: "7-Day Hunza Autumn Blossom & Heritage Trail",
      region: "Hunza & Nagar Valleys, Gilgit-Baltistan",
      days: 7,
      grade: "Easy to Moderate",
      estimatedPrice: "PKR 195,000 / couple",
      highlights: [
        "Day 1: Arrival in Gilgit, scenic drive along KKH to Karimabad",
        "Day 2: 800-year-old Baltit Fort & Altit Fort heritage exploration",
        "Day 3: Sunrise over Rakaposhi (7,788m) from Duikar Eagle's Nest",
        "Day 4: Day excursion to Passu Cones, Borith Lake & Hussaini Bridge",
        "Day 5: Attabad Lake boating & Hopper Glacier excursion in Nagar Valley",
        "Day 6: Local bazaar exploration & traditional organic Hunza lunch",
        "Day 7: Scenic departure back to Gilgit airport",
      ],
      isApproved: false,
    },
  },
];

interface MessageListProps {
  onSelectPrompt?: (prompt: string) => void;
}

export const MessageList: React.FC<MessageListProps> = ({ onSelectPrompt }) => {
  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 space-y-4 max-w-4xl mx-auto w-full">
      {/* Expedition Brand Welcome Banner */}
      <div className="bg-gradient-to-br from-[#12372A]/5 via-white to-humsafar-surfaceParchment rounded-2xl p-4 sm:p-6 border border-humsafar-subtleBorder shadow-sm mb-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="space-y-1.5 max-w-xl">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="accent">Official AI Travel Concierge</Badge>
              <span className="text-xs text-humsafar-mutedText">
                Indus Trekking & Tours Pakistan
              </span>
            </div>
            <h2 className="text-lg sm:text-xl font-bold text-humsafar-header tracking-tight">
              Plan better. Travel farther.
            </h2>
            <p className="text-xs sm:text-sm text-humsafar-slate leading-relaxed">
              Explore the Karakoram, Himalayas, and Hindukush. Tell me your preferred regions, dates, fitness level, or trekking dreams.
            </p>
          </div>

          <div className="hidden sm:flex items-center gap-2 text-xs text-humsafar-mutedText self-center bg-white px-3 py-2 rounded-xl border border-humsafar-subtleBorder shadow-subtle">
            <ShieldCheck className="w-4 h-4 text-humsafar-mainButton" />
            <span>Human-in-the-Loop Safe</span>
          </div>
        </div>
      </div>

      {/* Render Conversation Bubbles */}
      <div className="space-y-2">
        {PLACEHOLDER_MESSAGES.map((msg) => (
          <MessageBubble key={msg.id} {...msg} />
        ))}
      </div>
    </div>
  );
};
