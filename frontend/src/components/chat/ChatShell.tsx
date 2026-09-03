"use client";

import React, { useState, useRef, useEffect } from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { AuthScreen } from "@/components/auth/AuthScreen";
import { MessageProps } from "./MessageBubble";

const SAMPLE_SESSIONS: Record<string, { title: string; messages: MessageProps[] }> = {
  "rec-1": {
    title: "Hunza Autumn Foliage & Heritage Trail",
    messages: [
      {
        id: "m-1",
        sender: "agent",
        timestamp: "10:42 AM",
        content:
          "Salam and welcome to Indus Trekking and Tours Pakistan. I am Humsafar, your live expedition planning companion. All routes, seasonal advisories, and base costs are pulled directly from our live website catalog (itp.7scribes.com).\n\nWhich region or trekking circuit are you interested in exploring?",
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
          "Late October is the peak of the Hunza golden foliage season, when apricot and poplar orchards turn amber beneath Rakaposhi (7,788m) and Ladyfinger Peak.\n\nBased on verified logistics from Indus Trekking & Tours Pakistan, I have synthesized the personalized itinerary below. As part of our traveler commitment, this is a draft until you explicitly approve it.",
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
          filename: "7-Day Hunza Autumn Trail • MD",
          highlights: [
            "Day 1: Arrival in Gilgit, scenic drive along KKH to Karimabad",
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
    ],
  },
  "pin-1": {
    title: "K2 & Concordia Classic Trek",
    messages: [
      {
        id: "k2-1",
        sender: "agent",
        timestamp: "9:15 AM",
        content:
          "Welcome to the K2 & Concordia expedition desk. The Baltoro Glacier trek requires approximately 14 to 21 days with mandatory government trekking permits and professional mountain guides.",
        confidenceType: "official",
        sourceUrl: "itp.7scribes.com",
      },
    ],
  },
};

export const ChatShell: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [activeSessionId, setActiveSessionId] = useState<string>("rec-1");
  const [activeChatTitle, setActiveChatTitle] = useState<string>(
    "Hunza Autumn Foliage & Heritage Trail"
  );
  const [messages, setMessages] = useState<MessageProps[]>(
    SAMPLE_SESSIONS["rec-1"].messages
  );
  const [activeView, setActiveView] = useState<"chat" | "auth">("chat");
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const streamIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    };
  }, []);

  const handleToggleSidebar = () => {
    setIsSidebarOpen((prev) => !prev);
  };

  const handleSelectSession = (id: string) => {
    if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    setIsStreaming(false);
    setError(null);
    setActiveSessionId(id);
    if (SAMPLE_SESSIONS[id]) {
      setActiveChatTitle(SAMPLE_SESSIONS[id].title);
      setMessages(SAMPLE_SESSIONS[id].messages);
    } else {
      setActiveChatTitle("Custom Expedition Plan");
      setMessages([]);
    }
    setActiveView("chat");
  };

  const handleNewChat = () => {
    if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    setIsStreaming(false);
    setError(null);
    setActiveSessionId("new");
    setActiveChatTitle("New Trip Plan");
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
    setMessages((prev) =>
      prev.map((msg, i) =>
        i === prev.length - 1 ? { ...msg, isStreaming: false } : msg
      )
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
      "I am cross-referencing your inquiry live against tour schedules and road conditions on itp.7scribes.com.\n\nPeak expedition season across Gilgit-Baltistan runs between late May and October. I can structure a detailed day-by-day itinerary draft with transport logistics, hotel staging, and guide arrangements.";

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
    }, 35);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-white">
      {/* Claude-Style Collapsible Sidebar */}
      <Sidebar
        isOpen={isSidebarOpen}
        onToggle={handleToggleSidebar}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onOpenAuth={() => setActiveView((prev) => (prev === "auth" ? "chat" : "auth"))}
      />

      {/* Main Canvas Area */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden bg-white">
        {/* Sticky Top Bar */}
        <TopBar
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={handleToggleSidebar}
          activeChatTitle={activeChatTitle}
          onOpenAuth={() => setActiveView((prev) => (prev === "auth" ? "chat" : "auth"))}
          activeView={activeView}
        />

        {/* Dynamic Body: Chat vs Auth */}
        {activeView === "chat" ? (
          <main className="flex-1 flex flex-col justify-between overflow-hidden relative">
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
          <main className="flex-1 flex items-center justify-center p-4 overflow-y-auto">
            <AuthScreen
              onContinueAsGuest={() => setActiveView("chat")}
              onLoginSuccess={() => setActiveView("chat")}
            />
          </main>
        )}
      </div>
    </div>
  );
};
