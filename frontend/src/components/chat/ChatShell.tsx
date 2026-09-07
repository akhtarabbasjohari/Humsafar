"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
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
import { api, ApiError, UserProfile } from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";
import {
  useSessionsQuery,
  useItinerariesQuery,
  useSendMessageMutation,
  useCreateSessionMutation,
  useDeleteSessionMutation,
  useRenameSessionMutation,
  useClaimSessionMutation,
  useSaveItineraryMutation,
  useApproveItineraryMutation,
} from "@/hooks/useChatQueries";

export const ChatShell: React.FC = () => {
  const queryClient = useQueryClient();

  // Zustand Store — Local UI & Client Auth State
  const {
    user,
    activeSessionId,
    activeChatTitle,
    activeView,
    isSidebarOpen,
    inFlightSessionIds,
    setActiveSessionId,
    setActiveChatTitle,
    setActiveView,
    setSidebarOpen,
    setApprovalStatus,
    addInFlightSession,
    removeInFlightSession,
    logout,
  } = useAppStore();

  const activeSessionIdRef = useRef<string>("");
  activeSessionIdRef.current = activeSessionId;

  // Local message state per session
  const [messages, setMessages] = useState<MessageProps[]>([]);
  const [sessionMessages, setSessionMessages] = useState<Record<string, MessageProps[]>>({});
  const sessionMessagesRef = useRef<Record<string, MessageProps[]>>({});
  sessionMessagesRef.current = sessionMessages;

  // Modal dialog states
  const [isItinerariesModalOpen, setIsItinerariesModalOpen] = useState<boolean>(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState<boolean>(false);

  // Streaming & input prefill states
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [chatInputText, setChatInputText] = useState<string>("");
  const streamIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // TanStack Query — Server State Queries & Mutations
  const sessionsQuery = useSessionsQuery(Boolean(user));
  const itinerariesQuery = useItinerariesQuery(Boolean(user));

  const sendMessageMutation = useSendMessageMutation();
  const createSessionMutation = useCreateSessionMutation();
  const deleteSessionMutation = useDeleteSessionMutation();
  const renameSessionMutation = useRenameSessionMutation();
  const claimSessionMutation = useClaimSessionMutation();
  const saveItineraryMutation = useSaveItineraryMutation();
  const approveItineraryMutation = useApproveItineraryMutation();

  const sessions: ChatSessionItem[] = (sessionsQuery.data || []).map((s: any) => ({
    id: s.id,
    title: s.title || "Custom Expedition Plan",
    timestamp: s.updated_at,
  }));

  const savedItineraries: SavedItineraryItem[] = itinerariesQuery.data || [];

  const handleRequestChanges = (messageId: string, title?: string) => {
    setChatInputText(
      `Could we customize this ${title ? `"${title}"` : "itinerary"} to adjust the following details: `
    );
  };

  // Initialize Session on mount
  useEffect(() => {
    useAppStore.getState().rehydrateAuth();
    initSession();
    return () => {
      if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    };
  }, []);

  const initSession = async () => {
    const currentUser = useAppStore.getState().user;
    try {
      if (currentUser) {
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
    setSidebarOpen((prev) => !prev);
  };

  const handleSelectSession = async (id: string) => {
    if (streamIntervalRef.current) {
      clearInterval(streamIntervalRef.current);
      streamIntervalRef.current = null;
    }
    setIsStreaming(false);
    sendMessageMutation.reset();
    setActiveSessionId(id);

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
          sessionId: id,
          itineraryId: m.metadata?.itinerary_id || m.metadata?.itinerary?.id,
          confidenceLabel: m.metadata?.confidence_label,
          sourceUrl: m.metadata?.source_url,
          itineraryDraft: (() => {
            const itin = m.metadata?.itinerary || m.metadata?.itinerary_data;
            if (!itin) return undefined;
            return {
              title: itin.title || "Expedition Itinerary",
              region: itin.region || "Northern Pakistan",
              days: itin.duration || "7 Days",
              estimatedPrice: itin.price || "Market Rate Calculated",
              highlights: itin.highlights || [],
              dayByDay: itin.day_by_day,
              inclusions: itin.inclusions,
              exclusions: itin.exclusions,
              equipment: itin.equipment,
              contactDetails: itin.contact_details,
              isApproved: itin.is_approved || false,
              confidenceLabel: m.metadata?.confidence_label,
              confidenceType: (m.metadata?.confidence_label || "").includes("official")
                ? "official"
                : "unverified",
              sourceUrl: m.metadata?.source_url,
            };
          })(),
        }));

        setSessionMessages((prev) => ({ ...prev, [id]: mapped }));
        if (activeSessionIdRef.current === id) {
          setMessages(mapped);
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
    sendMessageMutation.reset();
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
      await renameSessionMutation.mutateAsync({ sessionId, newTitle });
      if (activeSessionId === sessionId) {
        setActiveChatTitle(newTitle);
      }
    } catch (err: any) {
      alert(err.message || "Failed to update chat title.");
    }
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await deleteSessionMutation.mutateAsync(id);
      removeInFlightSession(id);
      setSessionMessages((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });

      // If the deleted session was currently active, switch to next available or create new
      if (activeSessionId === id) {
        const remaining = sessions.filter((s) => s.id !== id);
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
    // 1. Optimistic UI update in Zustand and local state
    setApprovalStatus(messageId, true);
    if (activeSessionId) {
      setApprovalStatus(activeSessionId, true);
    }
    const targetMsg = messages.find((m) => m.id === messageId);
    if (targetMsg?.itineraryDraft?.title) {
      setApprovalStatus(targetMsg.itineraryDraft.title, true);
    }
    if (targetMsg?.itineraryId) {
      setApprovalStatus(targetMsg.itineraryId, true);
    }

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

    // 2. Persist to backend via TanStack Query mutations
    if (targetMsg?.itineraryDraft && activeSessionId) {
      const draft = targetMsg.itineraryDraft;
      try {
        const daysClean =
          typeof draft.days === "number"
            ? draft.days
            : parseInt(String(draft.days).replace(/[^0-9]/g, "")) || 7;

        const priceClean =
          draft.estimatedPrice.replace(/[^0-9.]/g, "") || "150000.00";

        const saved = await saveItineraryMutation.mutateAsync({
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

        // Approve it via HITL endpoint mutation
        await approveItineraryMutation.mutateAsync({
          itineraryId: saved.id,
          notes: "Approved by traveler in chat.",
        });
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

    sendMessageMutation.reset();

    // 1. Determine target session (create if first message in new plan)
    let targetSessionId = activeSessionId;
    if (!targetSessionId || targetSessionId.startsWith("guest-local-")) {
      try {
        const session = await createSessionMutation.mutateAsync({
          title: "New Expedition Plan",
          forceNew: Boolean(user),
        });
        targetSessionId = session.id;
        setActiveSessionId(targetSessionId);
        setActiveChatTitle(session.title || "New Expedition Plan");
      } catch (err: any) {
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
    }

    // Mark session as in-flight in background
    addInFlightSession(targetSessionId);

    try {
      const response = await sendMessageMutation.mutateAsync({
        sessionId: targetSessionId,
        message: text,
      });

      if (response.session_title) {
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
        sessionId: targetSessionId,
        itineraryId: response.itinerary_id || itineraryData?.id,
        itineraryDraft: itineraryData
          ? {
              title: itineraryData.title,
              region:
                itineraryData.region ||
                (itineraryData.title.toLowerCase().includes("hunza")
                  ? "Hunza Valley, Gilgit-Baltistan"
                  : "Northern Pakistan"),
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
        setMessages((prev) => [...prev, agentMsg]);
      }
    } catch {
      // Error state provided by sendMessageMutation.error
    } finally {
      removeInFlightSession(targetSessionId);
    }
  };

  const handleLoginSuccess = async () => {
    setActiveView("chat");

    // Migrate existing guest conversation to this newly authenticated user account
    if (activeSessionId && !activeSessionId.startsWith("guest-local-")) {
      try {
        await claimSessionMutation.mutateAsync({ sessionId: activeSessionId });
      } catch {
        // Session claim handled
      }
    }

    queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    queryClient.invalidateQueries({ queryKey: ["saved-itineraries"] });
  };

  const handleLogout = () => {
    logout();
    queryClient.clear();
    setMessages([]);
    setSessionMessages({});
    initSession();
  };

  // Derive loading and error states from TanStack Query and in-flight tracking
  const isMessageLoading =
    inFlightSessionIds.includes(activeSessionId) ||
    (sendMessageMutation.isPending &&
      sendMessageMutation.variables?.sessionId === activeSessionId);

  const rawError =
    createSessionMutation.error ||
    (sendMessageMutation.variables?.sessionId === activeSessionId
      ? sendMessageMutation.error
      : null);

  const chatError = rawError
    ? rawError instanceof ApiError
      ? rawError.message
      : rawError.message ||
        "Could not verify live itinerary details with the backend server. Please check your connection and try again."
    : null;

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
        inFlightSessionIds={new Set(inFlightSessionIds)}
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
              isLoading={isMessageLoading}
              error={chatError}
              onRetry={() => sendMessageMutation.reset()}
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
