"use client";

import React, { useState, useRef, useEffect } from "react";
import { Header } from "./Header";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { AuthScreen } from "@/components/auth/AuthScreen";
import { MessageProps } from "./MessageBubble";

const INITIAL_MESSAGES: MessageProps[] = [
  {
    id: "m-1",
    sender: "agent",
    timestamp: "10:42 AM",
    content:
      "Salam and welcome to Indus Trekking and Tours Pakistan. I am Humsafar, your live expedition planning companion. All routes, seasonal advisories, and base costs are pulled directly from our live website catalog.\n\nWhich region or trekking circuit are you interested in exploring?",
    confidenceType: "official",
    sourceUrl: "itp.7scribes.com",
  },
  {
    id: "m-2",
    sender: "user",
    timestamp: "10:44 AM",
    content:
      "I want to plan a 7-day autumn tour in Hunza Valley in late October for 2 people. We want moderate walks, historical forts, and golden foliage view points.",
  },
  {
    id: "m-3",
    sender: "agent",
    timestamp: "10:45 AM",
    content:
      "Late October is the peak of the Hunza golden foliage season, when apricot and poplar orchards turn amber beneath Rakaposhi (7,788m) and Ladyfinger Peak.\n\nBased on verified logistics from Indus Trekking & Tours Pakistan, I have drafted the following 7-day personalized itinerary. As part of our traveler commitment, this is a draft until you explicitly approve it.",
    confidenceType: "official",
    sourceUrl: "itp.7scribes.com",
    itineraryDraft: {
      title: "7-Day Hunza Autumn Foliage & Heritage Trail",
      region: "Hunza & Nagar Valleys, Gilgit-Baltistan",
      days: 7,
      grade: "Easy to Moderate",
      estimatedPrice: "PKR 195,000 / couple",
      confidenceType: "official",
      sourceUrl: "itp.7scribes.com",
      highlights: [
        "Day 1: Arrival in Gilgit, scenic drive via Karakoram Highway to Karimabad",
        "Day 2: 800-year-old Baltit Fort and Altit Fort historic tour",
        "Day 3: Sunrise panorama over Rakaposhi from Duikar Eagle's Nest",
        "Day 4: Day excursion to Passu Cones, Borith Lake and suspension bridge",
        "Day 5: Attabad Lake boat crossing and Hopper Glacier in Nagar Valley",
        "Day 6: Local organic cuisine lunch and artisan bazaar walk",
        "Day 7: Morning departure to Gilgit airport for return flight",
      ],
      isApproved: false,
    },
  },
];

export const ChatShell: React.FC = () => {
  const [activeView, setActiveView] = useState<"chat" | "auth">("chat");
  const [messages, setMessages] = useState<MessageProps[]>(INITIAL_MESSAGES);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const streamIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Clean up streaming interval on unmount
  useEffect(() => {
    return () => {
      if (streamIntervalRef.current) {
        clearInterval(streamIntervalRef.current);
      }
    };
  }, []);

  const handleToggleAuth = () => {
    setActiveView((prev) => (prev === "chat" ? "auth" : "chat"));
  };

  const handleNewChat = () => {
    if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    setIsStreaming(false);
    setError(null);
    setMessages([]);
    setActiveView("chat");
  };

  const handleApproveItinerary = (messageId: string) => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id === messageId && msg.itineraryDraft) {
          return {
            ...msg,
            itineraryDraft: {
              ...msg.itineraryDraft,
              isApproved: true,
            },
          };
        }
        return msg;
      })
    );
  };

  const handleStopStreaming = () => {
    if (streamIntervalRef.current) {
      clearInterval(streamIntervalRef.current);
      streamIntervalRef.current = null;
    }
    setIsStreaming(false);
    // Mark last streaming message as no longer streaming
    setMessages((prev) =>
      prev.map((msg, i) => (i === prev.length - 1 ? { ...msg, isStreaming: false } : msg))
    );
  };

  const handleSendMessage = (text: string) => {
    const userMsg: MessageProps = {
      id: `u-${Date.now()}`,
      sender: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    const agentMsgId = `a-${Date.now()}`;
    const fullReplyText =
      "I am cross-referencing your request with live itinerary availability on itp.7scribes.com. Seasonal weather windows for northern Pakistan generally open between May and October, with road access via the Karakoram Highway monitored in real time.\n\nWould you like me to prepare a custom day-by-day expedition proposal for these dates?";

    const agentMsgPlaceholder: MessageProps = {
      id: agentMsgId,
      sender: "agent",
      content: "",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      isStreaming: true,
      confidenceType: "official",
      sourceUrl: "itp.7scribes.com",
    };

    setMessages((prev) => [...prev, userMsg, agentMsgPlaceholder]);
    setIsStreaming(true);
    setError(null);

    // Simulate real typewriter streaming
    let charIndex = 0;
    streamIntervalRef.current = setInterval(() => {
      charIndex += 4;
      if (charIndex >= fullReplyText.length) {
        if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
        streamIntervalRef.current = null;
        setIsStreaming(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === agentMsgId ? { ...m, content: fullReplyText, isStreaming: false } : m
          )
        );
      } else {
        const currentSlice = fullReplyText.slice(0, charIndex);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === agentMsgId ? { ...m, content: currentSlice, isStreaming: true } : m
          )
        );
      }
    }, 40);
  };

  return (
    <div className="flex flex-col min-h-screen bg-white">
      {/* Top Header in Deep Navy #0F2C3E */}
      <Header
        activeView={activeView}
        onOpenAuth={handleToggleAuth}
        onNewChat={handleNewChat}
        isStreaming={isStreaming}
      />

      {/* Main Conversational Body */}
      {activeView === "chat" ? (
        <main className="flex-1 flex flex-col justify-between overflow-hidden">
          <MessageList
            messages={messages}
            isStreaming={isStreaming}
            error={error}
            onRetry={() => setError(null)}
            onApproveItinerary={handleApproveItinerary}
            onSelectPrompt={(prompt) => handleSendMessage(prompt)}
          />

          <ChatInput
            onSend={handleSendMessage}
            onStop={handleStopStreaming}
            isStreaming={isStreaming}
          />
        </main>
      ) : (
        <main className="flex-1 flex items-center justify-center p-4">
          <AuthScreen
            onContinueAsGuest={() => setActiveView("chat")}
            onLoginSuccess={() => setActiveView("chat")}
          />
        </main>
      )}
    </div>
  );
};
