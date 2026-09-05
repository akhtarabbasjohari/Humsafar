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
import { UserProfileModal } from "./UserProfileModal";
import { api, authStorage, UserProfile, SendMessageResponse } from "@/lib/api";

export const ChatShell: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const activeSessionIdRef = useRef<string>("");
  activeSessionIdRef.current = activeSessionId;

  const [activeChatTitle, setActiveChatTitle] = useState<string>("New Expedition Plan");
  const [messages, setMessages] = useState<MessageProps[]>([]);
  const [sessionMessages, setSessionMessages] = useState<Record<string, MessageProps[]>>({});
  const sessionMessagesRef = useRef<Record<string, MessageProps[]>>({});
  sessionMessagesRef.current = sessionMessages;

  const [inFlightSessionIds, setInFlightSessionIds] = useState<Set<string>>(new Set());
  const inFlightRef = useRef<Set<string>>(new Set());
  inFlightRef.current = inFlightSessionIds;

  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [savedItineraries, setSavedItineraries] = useState<SavedItineraryItem[]>([]);
  const [isItinerariesModalOpen, setIsItinerariesModalOpen] = useState<boolean>(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState<boolean>(false);
  const [user, setUser] = useState<UserProfile | null>(null);

  const [activeView, setActiveView] = useState<"chat" | "auth">("chat");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [chatInputText, setChatInputText] = useState<string>("");

  const streamIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const handleRequestChanges = (messageId: string, title?: string) => {
    setChatInputText(
      `Could we customize this ${title ? `"${title}"` : "itinerary"} to adjust the following details: `
    );
  };


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
      if (existingUser) {
        await refreshSessions(true);
        await refreshItineraries();
        const serverSessions = await api.listSessions();
        if (Array.isArray(serverSessions) && serverSessions.length > 0) {
          await handleSelectSession(serverSessions[0].id);
          return;
        }
        // No existing session: start in clean new plan state
        setActiveSessionId("");
        setActiveChatTitle("New Expedition Plan");
        setMessages([]);
        return;
      }

      // Guest mode
      const session = await api.createSession("New Trip Plan");
      setActiveSessionId(session.id);
      setActiveChatTitle(session.title || "New Trip Plan");
    } catch (err) {
      console.warn("Failed to initialize session. Operating in local mode:", err);
      setActiveSessionId("");
    }
  };

  const handleToggleSidebar = () => {
    setIsSidebarOpen((prev) => !prev);
  };

  const handleSelectSession = async (id: string) => {
    if (streamIntervalRef.current) {
      clearInterval(streamIntervalRef.current);
      streamIntervalRef.current = null;
    }
    setIsStreaming(false);
    setError(null);
    setActiveSessionId(id);

    // If this session has a background task in flight, reflect loading
    setIsLoading(inFlightRef.current.has(id));

    const matched = sessions.find((s) => s.id === id);
    if (matched) {
      setActiveChatTitle(matched.title);
    }

    // Immediately show cached messages for this session
    if (sessionMessagesRef.current[id]) {
      setMessages(sessionMessagesRef.current[id]);
    } else {
      setMessages([]);
    }

    try {
      const msgs = await api.getMessages(id);
      if (Array.isArray(msgs)) {
        const mapped: MessageProps[] = msgs.map((m: any) => ({
          id: m.id,
          sender: m.sender === "user" ? "user" : "agent",
          content: m.content,
          timestamp: new Date(m.created_at || Date.now()).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          confidenceLabel: m.metadata?.confidence_label,
          sourceUrl: m.metadata?.source_url,
          itineraryDraft: (() => {
            const itin = m.metadata?.itinerary || m.metadata?.itinerary_data;
            if (!itin) return undefined;
            return {
              title: itin.title || "Expedition Itinerary",
              region: itin.region || "Northern Pakistan",
              days: itin.duration || "7 Days",
              estimatedPrice: itin.price || "Pricing upon inquiry",
              highlights: itin.highlights || [],
              dayByDay: itin.day_by_day,
              inclusions: itin.inclusions,
              exclusions: itin.exclusions,
              equipment: itin.equipment,
              contactDetails: itin.contact_details,
              isApproved: itin.is_approved || false,
              confidenceLabel: m.metadata?.confidence_label,
              confidenceType: (m.metadata?.confidence_label || "").includes("official") ? "official" : "unverified",
              sourceUrl: m.metadata?.source_url,
            };
          })(),

        }));

        setSessionMessages((prev) => ({ ...prev, [id]: mapped }));
        if (activeSessionIdRef.current === id) {
          setMessages(mapped);
          if (!inFlightRef.current.has(id)) {
            setIsLoading(false);
          }
        }
      }
    } catch {
      // keep cached
    }
    setActiveView("chat");
  };

  const handleNewChat = () => {
    // If guest: unauthenticated visitors are gated from multiple chats
    if (!user) {
      setActiveView("auth");
      return;
    }

    if (streamIntervalRef.current) {
      clearInterval(streamIntervalRef.current);
      streamIntervalRef.current = null;
    }
    setIsStreaming(false);
    setIsLoading(false);
    setError(null);
    setMessages([]);

    // Deferred session creation: do not hit the backend until user sends first message
    setActiveSessionId("");
    setActiveChatTitle("New Expedition Plan");
    setActiveView("chat");
  };

  const handleRenameSession = async (sessionId: string, newTitle: string) => {
    if (!sessionId) {
      setActiveChatTitle(newTitle);
      return;
    }
    try {
      await api.updateSessionTitle(sessionId, newTitle);
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, title: newTitle } : s))
      );
      if (activeSessionId === sessionId) {
        setActiveChatTitle(newTitle);
      }
    } catch (err: any) {
      alert(err.message || "Failed to update chat title.");
    }
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await api.deleteSession(id);
      const remaining = sessions.filter((s) => s.id !== id);
      setSessions(remaining);
      setSessionMessages((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setInFlightSessionIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });

      // If the deleted session was currently active, switch to next available or create new
      if (activeSessionId === id) {
        if (remaining.length > 0) {
          await handleSelectSession(remaining[0].id);
        } else {
          handleNewChat();
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

    if (activeSessionId) {
      setSessionMessages((prev) => {
        const list = prev[activeSessionId] || [];
        return {
          ...prev,
          [activeSessionId]: list.map((msg) =>
            msg.id === messageId && msg.itineraryDraft
              ? { ...msg, itineraryDraft: { ...msg.itineraryDraft, isApproved: true } }
              : msg
          ),
        };
      });
    }

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

    // 1. Determine target session (create if first message in new plan)
    let targetSessionId = activeSessionId;
    if (!targetSessionId || targetSessionId.startsWith("guest-local-")) {
      try {
        const session = await api.createSession("New Expedition Plan", Boolean(user));
        targetSessionId = session.id;
        setActiveSessionId(targetSessionId);
        setActiveChatTitle(session.title || "New Expedition Plan");
        if (user) {
          await refreshSessions(true);
        }
      } catch (err: any) {
        setError(err.message || "Failed to initialize chat session.");
        return;
      }
    }

    // 2. Optimistic User Message
    const userMsg: MessageProps = {
      id: `u-${Date.now()}`,
      sender: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setSessionMessages((prev) => {
      const existing = prev[targetSessionId] || [];
      return { ...prev, [targetSessionId]: [...existing, userMsg] };
    });

    if (activeSessionIdRef.current === targetSessionId) {
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
    }

    // Mark session as in-flight in background
    setInFlightSessionIds((prev) => new Set(prev).add(targetSessionId));

    try {
      const response: SendMessageResponse = await api.sendMessage(targetSessionId, text);

      if (response.session_title) {
        setSessions((prev) =>
          prev.map((s) => (s.id === targetSessionId ? { ...s, title: response.session_title! } : s))
        );
        if (activeSessionIdRef.current === targetSessionId) {
          setActiveChatTitle(response.session_title);
        }
      }

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

      const agentMsg: MessageProps = {
        id: agentMsgId,
        sender: "agent",
        content: fullReplyText,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        isStreaming: false,
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
              highlights: [
                itineraryData.summary || "Official verified expedition schedule from itp.7scribes.com.",
              ],
              dayByDay: itineraryData.day_by_day,
              inclusions: itineraryData.inclusions,
              exclusions: itineraryData.exclusions,
              equipment: itineraryData.equipment,
              contactDetails: itineraryData.contact_details,
              isApproved: false,
            }
          : undefined,

      };

      // Store in session's message list
      setSessionMessages((prev) => {
        const existing = prev[targetSessionId] || [];
        return { ...prev, [targetSessionId]: [...existing, agentMsg] };
      });

      // If the user is currently viewing targetSessionId, update display
      if (activeSessionIdRef.current === targetSessionId) {
        setIsLoading(false);
        setMessages((prev) => [...prev, agentMsg]);
      }

      if (user) {
        await refreshSessions(true);
      }
    } catch (err: any) {
      if (activeSessionIdRef.current === targetSessionId) {
        setIsLoading(false);
        setIsStreaming(false);
        setError(
          err.message ||
            "Could not verify live itinerary details with the backend server. Please check your connection and try again."
        );
      }
    } finally {
      // Clear in-flight state for targetSessionId
      setInFlightSessionIds((prev) => {
        const next = new Set(prev);
        next.delete(targetSessionId);
        return next;
      });
      if (activeSessionIdRef.current === targetSessionId) {
        setIsLoading(false);
      }
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
    setSessionMessages({});
    setInFlightSessionIds(new Set());
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
        onOpenProfile={() => setIsProfileModalOpen(true)}
        onRenameSession={handleRenameSession}
        inFlightSessionIds={inFlightSessionIds}
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
          onOpenProfile={() => setIsProfileModalOpen(true)}
          onRenameActiveChat={(newTitle) => {
            if (activeSessionId) {
              handleRenameSession(activeSessionId, newTitle);
            } else {
              setActiveChatTitle(newTitle);
            }
          }}
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
              onRequestChanges={handleRequestChanges}
              onSelectPrompt={handleSendMessage}
            />

            <ChatInput
              onSend={handleSendMessage}
              onStop={handleStopStreaming}
              isStreaming={isStreaming}
              inputText={chatInputText}
              setInputText={setChatInputText}
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

      {/* Authenticated Member Profile Modal */}
      <UserProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
        user={user}
        savedCount={savedItineraries.length}
        onLogout={handleLogout}
        onViewSavedItineraries={() => setIsItinerariesModalOpen(true)}
      />

    </div>
  );
};
