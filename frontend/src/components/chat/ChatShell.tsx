"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Sidebar, ChatSessionItem } from "./Sidebar";
import { TopBar } from "./TopBar";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { AuthScreen } from "@/components/auth/AuthScreen";
import { MessageProps } from "./MessageBubble";
import {
  SavedItinerariesModal,
  SavedItineraryItem,
} from "./SavedItinerariesModal";
import { api, authStorage, UserProfile, SendMessageResponse } from "@/lib/api";

export const ChatShell: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const [activeChatTitle, setActiveChatTitle] = useState<string>("New Trip Plan");
  const [messages, setMessages] = useState<MessageProps[]>([]);
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [savedItineraries, setSavedItineraries] = useState<SavedItineraryItem[]>([]);
  const [isItinerariesModalOpen, setIsItinerariesModalOpen] = useState<boolean>(false);
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
    initSession(currentUser);
    return () => {
      if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    };
  }, []);

  const refreshSessions = useCallback(async (isMember: boolean) => {
    if (!isMember) {
      setSessions([]);
      return;
    }
    try {
      const serverSessions = await api.listSessions();
      if (Array.isArray(serverSessions)) {
        setSessions(
          serverSessions.map((s) => ({
            id: s.id,
            title: s.title || "Custom Expedition Plan",
            timestamp: s.updated_at,
          }))
        );
      }
    } catch {
      // Session fetch error handled silently
    }
  }, []);

  const refreshItineraries = useCallback(async () => {
    try {
      const list = await api.listItineraries();
      if (Array.isArray(list)) {
        setSavedItineraries(list);
      }
    } catch {
      // Non-critical
    }
  }, []);

  const initSession = async (existingUser: UserProfile | null) => {
    try {
      const session = await api.createSession("New Trip Plan");
      setActiveSessionId(session.id);
      setActiveChatTitle(session.title || "New Trip Plan");
      if (existingUser) {
        await refreshSessions(true);
        await refreshItineraries();
      }
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
      const matched = sessions.find((s) => s.id === id);
      if (matched) {
        setActiveChatTitle(matched.title);
      }
    } catch {
      setMessages([]);
    }
    setActiveView("chat");
  };

  const handleNewChat = async () => {
    // If guest: unauthenticated visitors are gated from multiple chats
    if (!user) {
      setActiveView("auth");
      return;
    }

    if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    setIsStreaming(false);
    setIsLoading(false);
    setError(null);
    setMessages([]);

    try {
      // Force new session for authenticated user
      const newSession = await api.createSession("New Expedition Plan", true);
      setActiveSessionId(newSession.id);
      setActiveChatTitle(newSession.title);
      await refreshSessions(true);
    } catch (err: any) {
      setError(err.message || "Failed to create new chat session.");
    }
    setActiveView("chat");
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await api.deleteSession(id);
      const remaining = sessions.filter((s) => s.id !== id);
      setSessions(remaining);

      // If the deleted session was currently active, switch to next available or create new
      if (activeSessionId === id) {
        if (remaining.length > 0) {
          await handleSelectSession(remaining[0].id);
        } else {
          await handleNewChat();
        }
      }
    } catch (err: any) {
      alert(err.message || "Failed to delete chat session.");
    }
  };

  const handleApproveItinerary = async (messageId: string) => {
    // 1. Optimistic UI update
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

    // 2. Persist to backend
    const targetMsg = messages.find((m) => m.id === messageId);
    if (targetMsg?.itineraryDraft && activeSessionId) {
      const draft = targetMsg.itineraryDraft;
      try {
        const daysClean =
          typeof draft.days === "number"
            ? draft.days
            : parseInt(String(draft.days).replace(/[^0-9]/g, "")) || 7;

        const priceClean =
          draft.estimatedPrice.replace(/[^0-9.]/g, "") || "150000.00";

        const saved = await api.saveItinerary({
          session: activeSessionId,
          title: draft.title,
          region: draft.region,
          duration_days: daysClean,
          itinerary_data: {
            highlights: draft.highlights,
            filename: draft.filename,
          },
          estimated_price_pkr: priceClean,
          source_url: draft.sourceUrl || "https://itp.7scribes.com",
          confidence_label: draft.confidenceLabel || "from our official listing",
        });

        // Approve it via HITL endpoint
        await api.approveItinerary(saved.id, "Approved by traveler in chat.");
        await refreshItineraries();
      } catch (err) {
        console.warn("Backend itinerary saving warning:", err);
      }
    }
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
      if (user) {
        await refreshSessions(true);
      }
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

    // Migrate existing guest conversation to this newly authenticated user account
    if (activeSessionId && !activeSessionId.startsWith("guest-local-")) {
      try {
        await api.claimGuestSession(activeSessionId);
      } catch {
        // Session claim handled
      }
    }

    await refreshSessions(true);
    await refreshItineraries();
  };

  const handleLogout = () => {
    api.logout();
    setUser(null);
    setSessions([]);
    setSavedItineraries([]);
    setMessages([]);
    initSession(null);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-white font-sans text-slate-900">
      {/* Sidebar Navigation */}
      <Sidebar
        isOpen={isSidebarOpen}
        onToggle={handleToggleSidebar}
        activeSessionId={activeSessionId}
        activeChatTitle={activeChatTitle}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onOpenAuth={() => setActiveView("auth")}
        user={user}
        sessions={sessions}
        onDeleteSession={handleDeleteSession}
        onLogout={handleLogout}
        onViewItineraries={() => setIsItinerariesModalOpen(true)}
        savedItinerariesCount={savedItineraries.length}
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
          user={user}
          onViewItineraries={() => setIsItinerariesModalOpen(true)}
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

      {/* Member Saved Itineraries Drawer / Modal */}
      <SavedItinerariesModal
        isOpen={isItinerariesModalOpen}
        onClose={() => setIsItinerariesModalOpen(false)}
        itineraries={savedItineraries}
      />
    </div>
  );
};
