"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Sidebar, ChatSessionItem } from "./Sidebar";
import { TopBar } from "./TopBar";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { AuthScreen } from "@/components/auth/AuthScreen";
import { MessageProps } from "./MessageBubble";
import { api, authStorage, UserProfile, SendMessageResponse } from "@/lib/api";

export const ChatShell: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const [activeChatTitle, setActiveChatTitle] = useState<string>("New Trip Plan");
  const [messages, setMessages] = useState<MessageProps[]>([]);
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [activeView, setActiveView] = useState<"chat" | "auth">("chat");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const streamIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize Auth & Session on mount
  useEffect(() => {
    const currentUser = authStorage.getUser();
    if (currentUser) {
      setUser(currentUser);
    }
    initSession();
    return () => {
      if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    };
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const serverSessions = await api.listSessions();
      if (Array.isArray(serverSessions) && serverSessions.length > 0) {
        setSessions(
          serverSessions.map((s) => ({
            id: s.id,
            title: s.title || "Custom Expedition",
            timestamp: s.updated_at,
          }))
        );
      }
    } catch {
      // Guest mode or initial state
    }
  }, []);

  const initSession = async () => {
    try {
      const session = await api.createSession("New Trip Plan");
      setActiveSessionId(session.id);
      setActiveChatTitle(session.title || "New Trip Plan");
      await refreshSessions();
    } catch (err) {
      console.warn("Failed to create initial backend session. Operating in local mode:", err);
      setActiveSessionId(`guest-local-${Date.now()}`);
    }
  };

  const handleToggleSidebar = () => {
    setIsSidebarOpen((prev) => !prev);
  };

  const handleSelectSession = async (id: string) => {
    if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    setIsStreaming(false);
    setIsLoading(false);
    setError(null);
    setActiveSessionId(id);

    try {
      const msgs = await api.getMessages(id);
      if (Array.isArray(msgs)) {
        setMessages(
          msgs.map((m: any) => ({
            id: m.id,
            sender: m.sender === "user" ? "user" : "agent",
            content: m.content,
            timestamp: new Date(m.created_at || Date.now()).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            confidenceLabel: m.metadata?.confidence_label,
            sourceUrl: m.metadata?.source_url,
          }))
        );
      }
    } catch {
      setMessages([]);
    }
    setActiveView("chat");
  };

  const handleNewChat = async () => {
    if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    setIsStreaming(false);
    setIsLoading(false);
    setError(null);
    setMessages([]);
    await initSession();
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

  const handleSendMessage = async (text: string) => {
    if (!text.trim()) return;

    setError(null);

    // 1. Optimistic User Message
    const userMsg: MessageProps = {
      id: `u-${Date.now()}`,
      sender: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    let sessionId = activeSessionId;
    if (!sessionId || sessionId.startsWith("guest-local-")) {
      try {
        const session = await api.createSession(text.slice(0, 40));
        sessionId = session.id;
        setActiveSessionId(sessionId);
        setActiveChatTitle(session.title);
      } catch {
        // Continue with current session ID
      }
    }

    try {
      const response: SendMessageResponse = await api.sendMessage(sessionId, text);
      setIsLoading(false);

      const assistantMsgData = response.assistant_message;
      const itineraryData = response.itinerary;
      const confidenceLabel =
        response.confidence_label ||
        assistantMsgData.metadata?.confidence_label ||
        "from our official listing";
      const sourceUrl =
        itineraryData?.source_url ||
        assistantMsgData.metadata?.source_url ||
        "https://itp.7scribes.com";

      const fullReplyText = assistantMsgData.content;
      const agentMsgId = assistantMsgData.id || `a-${Date.now()}`;

      // 2. Setup Assistant Placeholder for Typewriter
      const agentMsgPlaceholder: MessageProps = {
        id: agentMsgId,
        sender: "agent",
        content: "",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        isStreaming: true,
        confidenceLabel: confidenceLabel,
        confidenceType: confidenceLabel.includes("official") ? "official" : "unverified",
        sourceUrl: sourceUrl,
        itineraryDraft: itineraryData
          ? {
              title: itineraryData.title,
              region: itineraryData.title.toLowerCase().includes("hunza")
                ? "Hunza Valley, Gilgit-Baltistan"
                : "Karakoram & Northern Pakistan",
              days: itineraryData.duration,
              estimatedPrice: itineraryData.price,
              confidenceLabel: itineraryData.confidence_label || confidenceLabel,
              confidenceType: (itineraryData.confidence_label || confidenceLabel).includes("official")
                ? "official"
                : "unverified",
              sourceUrl: itineraryData.source_url || sourceUrl,
              filename: `${itineraryData.title.slice(0, 24)} • MD`,
              highlights: [
                itineraryData.summary || "Official verified expedition schedule from itp.7scribes.com.",
              ],
              isApproved: false,
            }
          : undefined,
      };

      setMessages((prev) => [...prev, agentMsgPlaceholder]);
      setIsStreaming(true);

      // Smooth typewriter delivery
      let charIndex = 0;
      streamIntervalRef.current = setInterval(() => {
        charIndex += 6;
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
      }, 20);

      // Refresh sidebar sessions to pick up updated title
      await refreshSessions();
    } catch (err: any) {
      setIsLoading(false);
      setIsStreaming(false);
      setError(
        err.message ||
          "Could not verify live itinerary details with the backend server. Please check your connection and try again."
      );
    }
  };

  const handleLoginSuccess = async () => {
    const loggedUser = authStorage.getUser();
    setUser(loggedUser);
    setActiveView("chat");
    await refreshSessions();
    await handleNewChat();
  };

  const handleLogout = () => {
    api.logout();
    setUser(null);
    setSessions([]);
    handleNewChat();
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-white font-sans text-slate-900">
      {/* Sidebar Navigation */}
      <Sidebar
        isOpen={isSidebarOpen}
        onToggle={handleToggleSidebar}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onOpenAuth={() => setActiveView("auth")}
        user={user}
        sessions={sessions}
        onLogout={handleLogout}
      />

      {/* Main Column */}
      <main className="flex-1 flex flex-col h-full min-w-0 bg-white relative">
        {/* Minimal Top Bar */}
        <TopBar
          activeChatTitle={activeChatTitle}
          onToggleSidebar={handleToggleSidebar}
          isSidebarOpen={isSidebarOpen}
          onOpenAuth={() => setActiveView("auth")}
          activeView={activeView}
        />

        {/* View Switcher: Chat Feed vs Authentication */}
        {activeView === "auth" ? (
          <AuthScreen
            onContinueAsGuest={() => setActiveView("chat")}
            onLoginSuccess={handleLoginSuccess}
          />
        ) : (
          <>
            <MessageList
              messages={messages}
              isStreaming={isStreaming}
              isLoading={isLoading}
              error={error}
              onRetry={() => setError(null)}
              onApproveItinerary={handleApproveItinerary}
              onSelectPrompt={handleSendMessage}
            />

            <ChatInput
              onSend={handleSendMessage}
              onStop={handleStopStreaming}
              isStreaming={isStreaming}
            />
          </>
        )}
      </main>
    </div>
  );
};
