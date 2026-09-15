"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Sidebar, ChatSessionItem } from "./Sidebar";
import { TopBar } from "./TopBar";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { AuthScreen } from "@/components/auth/AuthScreen";
import { MessageProps, ItineraryDraftData } from "./MessageBubble";
import {
  SavedItinerariesModal,
  SavedItineraryItem,
} from "./SavedItinerariesModal";
import { UserProfileModal } from "./UserProfileModal";
import { EditChatModal } from "./EditChatModal";
import { DeleteChatModal } from "./DeleteChatModal";
import { api, ApiError, UserProfile, sanitizePricePkr } from "@/lib/api";
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
  useDeleteItineraryMutation,
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
  const [selectedSavedItinerary, setSelectedSavedItinerary] = useState<SavedItineraryItem | null>(null);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState<boolean>(false);
  const [editingSession, setEditingSession] = useState<ChatSessionItem | null>(null);
  const [deletingSession, setDeletingSession] = useState<ChatSessionItem | null>(null);

  // Itinerary saving state
  // Itinerary saving state
  const [savingItineraryTitle, setSavingItineraryTitle] = useState<string | null>(null);
  const [locallySavedTitles, setLocallySavedTitles] = useState<Set<string>>(new Set());
  const [guestItineraries, setGuestItineraries] = useState<SavedItineraryItem[]>([]);

  // Streaming & input prefill states
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [chatInputText, setChatInputText] = useState<string>("");
  const streamIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // TanStack Query — Server State Queries & Mutations
  const sessionsQuery = useSessionsQuery(Boolean(user));
  const itinerariesQuery = useItinerariesQuery(Boolean(user));

  const sendMessageMutation = useSendMessageMutation();
  const createSessionMutation = useCreateSessionMutation();
  const deleteSessionMutation = useDeleteSessionMutation();
  const renameSessionMutation = useRenameSessionMutation();
  const claimSessionMutation = useClaimSessionMutation();
  const saveItineraryMutation = useSaveItineraryMutation();
  const deleteItineraryMutation = useDeleteItineraryMutation();
  const approveItineraryMutation = useApproveItineraryMutation();

  const sessions: ChatSessionItem[] = (sessionsQuery.data || []).map((s: any) => ({
    id: s.id,
    title: s.title || "Custom Expedition Plan",
    timestamp: s.updated_at,
  }));

  const serverItineraries: SavedItineraryItem[] = itinerariesQuery.data || [];

  // Combine server itineraries with guest itineraries
  const allSavedItineraries: SavedItineraryItem[] = React.useMemo(() => {
    const list = [...serverItineraries];
    const seen = new Set(list.map((i) => i.title.toLowerCase().trim()));
    guestItineraries.forEach((gi) => {
      const k = gi.title.toLowerCase().trim();
      if (!seen.has(k)) {
        seen.add(k);
        list.push(gi);
      }
    });
    return list;
  }, [serverItineraries, guestItineraries]);

  const savedItineraryTitles = React.useMemo(() => {
    const set = new Set<string>();
    allSavedItineraries.forEach((item) => {
      if (item.title) set.add(item.title.toLowerCase().trim());
    });
    locallySavedTitles.forEach((title) => set.add(title.toLowerCase().trim()));
    return set;
  }, [allSavedItineraries, locallySavedTitles]);

  const handleRequestChanges = (messageId: string, title?: string) => {
    setChatInputText(
      `Could we customize this ${title ? `"${title}"` : "itinerary"} to adjust the following details: `
    );
  };

  const handleSaveItinerary = async (draft: ItineraryDraftData) => {
    if (!draft || !draft.title) return;

    const titleKey = draft.title.toLowerCase().trim();
    setSavingItineraryTitle(titleKey);

    const daysClean =
      typeof draft.days === "number"
        ? draft.days
        : parseInt(String(draft.days).replace(/[^0-9]/g, "")) || 7;

    const priceClean = sanitizePricePkr(draft.estimatedPrice);

    // Guest mode: Save securely to localStorage without interrupting chat session
    if (!user) {
      try {
        const guestItem: SavedItineraryItem = {
          id: `guest-${Date.now()}`,
          title: draft.title,
          region: draft.region || "Northern Pakistan",
          duration_days: daysClean,
          estimated_price_pkr: priceClean,
          confidence_label: draft.confidenceLabel || "custom draft",
          source_url: draft.sourceUrl || "https://askoliadventure.com",
          status: "approved",
          is_approved_by_user: true,
          created_at: new Date().toISOString(),
          itinerary_data: {
            highlights: draft.highlights || [],
            day_by_day: draft.dayByDay || [],
            inclusions: draft.inclusions || [],
            exclusions: draft.exclusions || [],
            equipment: draft.equipment || [],
            contact_details: draft.contactDetails || {},
            filename: draft.filename,
          },
        };
        const raw = localStorage.getItem("humsafar_guest_itineraries");
        const existing: SavedItineraryItem[] = raw ? JSON.parse(raw) : [];
        const filtered = existing.filter((item) => item.title.toLowerCase().trim() !== titleKey);
        filtered.unshift(guestItem);
        localStorage.setItem("humsafar_guest_itineraries", JSON.stringify(filtered));
        setGuestItineraries(filtered);
        setLocallySavedTitles((prev) => new Set(prev).add(titleKey));
      } catch (e) {
        console.error("Failed to save guest itinerary to localStorage:", e);
      } finally {
        setSavingItineraryTitle(null);
      }
      return;
    }

    try {
      await saveItineraryMutation.mutateAsync({
        session: activeSessionId || null,
        title: draft.title,
        region: draft.region || "Northern Pakistan",
        duration_days: daysClean,
        itinerary_data: {
          highlights: draft.highlights || [],
          day_by_day: draft.dayByDay || [],
          inclusions: draft.inclusions || [],
          exclusions: draft.exclusions || [],
          equipment: draft.equipment || [],
          contact_details: draft.contactDetails || {},
          filename: draft.filename,
        },
        estimated_price_pkr: priceClean,
        source_url: draft.sourceUrl || "https://askoliadventure.com",
        confidence_label: draft.confidenceLabel || "from our official listing",
      });

      setLocallySavedTitles((prev) => new Set(prev).add(titleKey));
    } catch (err: any) {
      alert(err.message || "Failed to save itinerary.");
    } finally {
      setSavingItineraryTitle(null);
    }
  };

  const handleDeleteItinerary = async (itineraryId: string) => {
    if (itineraryId.startsWith("guest-")) {
      const updated = guestItineraries.filter((i) => i.id !== itineraryId);
      setGuestItineraries(updated);
      try {
        localStorage.setItem("humsafar_guest_itineraries", JSON.stringify(updated));
      } catch (e) {}
      return;
    }
    try {
      await deleteItineraryMutation.mutateAsync(itineraryId);
    } catch (err: any) {
      alert(err.message || "Failed to delete itinerary.");
    }
  };

  // Smooth progressive chunk streaming helper to prevent abrupt pop-in of large text
  const streamAgentResponse = (
    targetSessionId: string,
    agentMsgTemplate: MessageProps,
    fullText: string
  ) => {
    const isViewing = activeSessionIdRef.current === targetSessionId;
    if (!isViewing || fullText.length <= 40) {
      const finalMsg = { ...agentMsgTemplate, content: fullText, isStreaming: false };
      setSessionMessages((prev) => {
        const existing = prev[targetSessionId] || [];
        return { ...prev, [targetSessionId]: [...existing, finalMsg] };
      });
      if (isViewing) {
        setMessages((prev) => [...prev, finalMsg]);
      }
      return;
    }

    setIsStreaming(true);
    const totalChars = fullText.length;
    // Reveal ~15-30 chars per tick (16ms) completing smoothly in ~0.6-0.8s
    const step = Math.max(12, Math.ceil(totalChars / 45));
    let revealedLength = Math.min(step, totalChars);

    const initialMsg: MessageProps = {
      ...agentMsgTemplate,
      content: fullText.slice(0, revealedLength),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, initialMsg]);

    if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    streamIntervalRef.current = setInterval(() => {
      revealedLength += step;
      if (revealedLength >= totalChars) {
        if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
        streamIntervalRef.current = null;
        setIsStreaming(false);

        const finalizedMsg: MessageProps = { ...agentMsgTemplate, content: fullText, isStreaming: false };
        setMessages((prev) =>
          prev.map((m) => (m.id === agentMsgTemplate.id ? finalizedMsg : m))
        );
        setSessionMessages((prev) => {
          const existing = prev[targetSessionId] || [];
          return {
            ...prev,
            [targetSessionId]: existing.map((m) =>
              m.id === agentMsgTemplate.id ? finalizedMsg : m
            ),
          };
        });
      } else {
        const partialText = fullText.slice(0, revealedLength);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === agentMsgTemplate.id ? { ...m, content: partialText, isStreaming: true } : m
          )
        );
      }
    }, 16);
  };

  // Hydrate guest itineraries and initialize Session on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem("humsafar_guest_itineraries");
      if (raw) {
        const parsed: SavedItineraryItem[] = JSON.parse(raw);
        setGuestItineraries(parsed);
      }
    } catch (e) {
      console.warn("Failed to parse guest itineraries from localStorage:", e);
    }

    useAppStore.getState().rehydrateAuth();
    initSession();
    return () => {
      if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
      if (abortControllerRef.current) abortControllerRef.current.abort();
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

  const handleEnsureSession = async (): Promise<string> => {
    if (activeSessionId && !activeSessionId.startsWith("guest-local-")) {
      return activeSessionId;
    }
    try {
      const session = await createSessionMutation.mutateAsync({
        title: "New Expedition Plan",
        forceNew: Boolean(user),
      });
      setActiveSessionId(session.id);
      setActiveChatTitle(session.title || "New Expedition Plan");
      return session.id;
    } catch (err) {
      console.error("Failed to ensure session:", err);
      return activeSessionId;
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
          attachments: m.metadata?.attachments || [],
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

        if (activeSessionIdRef.current === id) {
          setMessages(mapped);
        }
      }
    } catch (err: any) {
      if (err instanceof ApiError && (err.status === 403 || err.status === 404)) {
        console.warn("Selected session is inaccessible or forbidden. Clearing active session:", err);
        setActiveSessionId("");
        setActiveChatTitle("New Expedition Plan");
        setMessages([]);
      }
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

        const priceClean = sanitizePricePkr(draft.estimatedPrice);

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
          source_url: draft.sourceUrl || "https://askoliadventure.com",
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
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (streamIntervalRef.current) {
      clearInterval(streamIntervalRef.current);
      streamIntervalRef.current = null;
    }
    setIsStreaming(false);
    if (activeSessionId) {
      removeInFlightSession(activeSessionId);
    }
    sendMessageMutation.reset();
    setMessages((prev) =>
      prev.map((msg, i) =>
        i === prev.length - 1 ? { ...msg, isStreaming: false } : msg
      )
    );
  };

  const handleSendMessage = async (
    text: string,
    attachments?: Array<{ name: string; size?: string }>
  ) => {
    const trimmed = text.trim();
    const hasAttachments = Boolean(attachments && attachments.length > 0);
    if (!trimmed && !hasAttachments) return;

    sendMessageMutation.reset();

    // 1. Immediate Optimistic User Message (rendered instantly so user sees it right away)
    const userMsg: MessageProps = {
      id: `u-${Date.now()}`,
      sender: "user",
      content: trimmed,
      attachments: hasAttachments ? attachments : undefined,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);

    // Snapshot history before adding this message, for in-context multi-turn memory
    const historyPayload = messages.map((m) => ({
      role: m.sender === "user" ? "user" : "assistant",
      content: m.content,
    }));

    // 2. Determine target session (create if first message in new plan)
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

    setSessionMessages((prev) => {
      const existing = prev[targetSessionId] || [];
      return { ...prev, [targetSessionId]: [...existing, userMsg] };
    });

    // Mark session as in-flight in background
    addInFlightSession(targetSessionId);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const outgoingMessage = trimmed || "Please review my attached document and help with my expedition plan.";
      const response = await sendMessageMutation.mutateAsync({
        sessionId: targetSessionId,
        message: outgoingMessage,
        history: historyPayload,
        signal: controller.signal,
        attachments,
      });
      abortControllerRef.current = null;

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
        undefined;
      const sourceUrl =
        itineraryData?.source_url ||
        assistantMsgData.metadata?.source_url ||
        undefined;

      const fullReplyText = assistantMsgData.content;
      const agentMsgId = assistantMsgData.id || `a-${Date.now()}`;

      const agentMsg: MessageProps = {
        id: agentMsgId,
        sender: "agent",
        content: fullReplyText,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        isStreaming: false,
        confidenceLabel: confidenceLabel,
        confidenceType: confidenceLabel
          ? confidenceLabel.toLowerCase().includes("official")
            ? "official"
            : "unverified"
          : undefined,
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
              confidenceType: (itineraryData.confidence_label || confidenceLabel || "")
                .toLowerCase()
                .includes("official")
                ? "official"
                : "unverified",
              sourceUrl: itineraryData.source_url || sourceUrl,
              highlights: [
                itineraryData.summary || "Official verified expedition schedule from askoliadventure.com.",
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

      // Stream agent response progressively for a smooth, elegant appearance
      streamAgentResponse(targetSessionId, agentMsg, fullReplyText);
    } catch (err: any) {
      abortControllerRef.current = null;
      if (err?.name === "AbortError" || err?.message?.includes("aborted")) {
        console.log("Generation stopped by user.");
        removeInFlightSession(targetSessionId);
        return;
      }
      if (err instanceof ApiError && (err.status === 403 || err.status === 404)) {
        console.warn("Session access denied or invalid. Auto-recovering with fresh session...");
        sendMessageMutation.reset();
        try {
          const freshSession = await createSessionMutation.mutateAsync({
            title: "New Expedition Plan",
            forceNew: true,
          });
          setActiveSessionId(freshSession.id);
          setActiveChatTitle(freshSession.title || "New Expedition Plan");
          targetSessionId = freshSession.id;

          const retryRes = await sendMessageMutation.mutateAsync({
            sessionId: targetSessionId,
            message: text,
          });

          const assistantMsgData = retryRes.assistant_message;
          const itineraryData = retryRes.itinerary;
          const confidenceLabel =
            retryRes.confidence_label ||
            assistantMsgData.metadata?.confidence_label ||
            undefined;
          const sourceUrl =
            itineraryData?.source_url ||
            assistantMsgData.metadata?.source_url ||
            undefined;

          const agentMsg: MessageProps = {
            id: assistantMsgData.id || `a-${Date.now()}`,
            sender: "agent",
            content: assistantMsgData.content,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            isStreaming: false,
            confidenceLabel: confidenceLabel,
            confidenceType: confidenceLabel
              ? confidenceLabel.toLowerCase().includes("official")
                ? "official"
                : "unverified"
              : undefined,
            sourceUrl: sourceUrl,
            sessionId: targetSessionId,
            itineraryId: retryRes.itinerary_id || itineraryData?.id,
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
                  confidenceType: (itineraryData.confidence_label || confidenceLabel || "")
                    .toLowerCase()
                    .includes("official")
                    ? "official"
                    : "unverified",
                  sourceUrl: itineraryData.source_url || sourceUrl,
                  highlights: [
                    itineraryData.summary || "Official verified expedition schedule from askoliadventure.com.",
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

          setSessionMessages((prev) => ({
            ...prev,
            [targetSessionId]: [userMsg, agentMsg],
          }));
          if (activeSessionIdRef.current === targetSessionId) {
            setMessages([userMsg, agentMsg]);
          }
        } catch (recoverErr) {
          console.error("Auto-recovery error:", recoverErr);
        }
      }
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
      } catch (claimErr) {
        console.warn("Could not claim guest session upon login:", claimErr);
      }
    }

    // Sync any guest itineraries stored locally to user account
    try {
      const raw = localStorage.getItem("humsafar_guest_itineraries");
      if (raw) {
        const guestItems: SavedItineraryItem[] = JSON.parse(raw);
        for (const item of guestItems) {
          try {
            await saveItineraryMutation.mutateAsync({
              session: activeSessionId || null,
              title: item.title,
              region: item.region || "Northern Pakistan",
              duration_days: typeof item.duration_days === "number" ? item.duration_days : 7,
              itinerary_data: {},
              estimated_price_pkr: sanitizePricePkr(item.estimated_price_pkr),
              source_url: item.source_url || "https://askoliadventure.com",
              confidence_label: item.confidence_label || "custom draft",
            });
          } catch (syncErr) {
            console.warn("Could not sync guest itinerary to server:", syncErr);
          }
        }
        localStorage.removeItem("humsafar_guest_itineraries");
        setGuestItineraries([]);
      }
    } catch (e) {
      console.warn("Error processing guest itineraries sync:", e);
    }

    await queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    await queryClient.invalidateQueries({ queryKey: ["saved-itineraries"] });
    await queryClient.invalidateQueries({ queryKey: ["itineraries"] });

    try {
      const userSessions = await api.listSessions();
      if (Array.isArray(userSessions) && userSessions.length > 0) {
        const found = userSessions.find((s) => s.id === activeSessionId);
        if (found) {
          await handleSelectSession(found.id);
        } else {
          await handleSelectSession(userSessions[0].id);
        }
      }
    } catch {
      // ignore
    }
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
        savedItinerariesCount={allSavedItineraries.length}
        onOpenProfile={() => setIsProfileModalOpen(true)}
        onRenameSession={handleRenameSession}
        onOpenEditModal={(session) => setEditingSession(session)}
        onOpenDeleteModal={(session) => setDeletingSession(session)}
        inFlightSessionIds={new Set(inFlightSessionIds)}
        savedItineraries={allSavedItineraries}
        onSelectSavedItinerary={(item) => {
          setSelectedSavedItinerary(item);
          setIsItinerariesModalOpen(true);
        }}
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
          savedCount={allSavedItineraries.length}
          onOpenProfile={() => setIsProfileModalOpen(true)}
          onRenameActiveChat={(newTitle) => {
            if (activeSessionId) {
              handleRenameSession(activeSessionId, newTitle);
            } else {
              setActiveChatTitle(newTitle);
            }
          }}
          onOpenEditModal={() => {
            if (activeSessionId) {
              const current = sessions.find((s) => s.id === activeSessionId) || {
                id: activeSessionId,
                title: activeChatTitle,
              };
              setEditingSession(current);
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
              onSaveItinerary={handleSaveItinerary}
              savedItineraryTitles={savedItineraryTitles}
              savingItineraryTitle={savingItineraryTitle}
            />

            <ChatInput
              onSend={handleSendMessage}
              onStop={handleStopStreaming}
              isStreaming={isStreaming || isMessageLoading}
              inputText={chatInputText}
              setInputText={setChatInputText}
              activeSessionId={activeSessionId}
              onEnsureSession={handleEnsureSession}
            />
          </>
        )}
      </main>

      {/* Member / Guest Saved Itineraries Drawer / Modal */}
      <SavedItinerariesModal
        isOpen={isItinerariesModalOpen}
        onClose={() => {
          setIsItinerariesModalOpen(false);
          setSelectedSavedItinerary(null);
        }}
        itineraries={allSavedItineraries}
        isLoading={itinerariesQuery.isLoading}
        onDeleteItinerary={handleDeleteItinerary}
        selectedItinerary={selectedSavedItinerary}
        onSelectItinerary={setSelectedSavedItinerary}
      />

      {/* Authenticated Member Profile Modal */}
      <UserProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
        user={user}
        savedCount={allSavedItineraries.length}
        onLogout={handleLogout}
        onViewSavedItineraries={() => setIsItinerariesModalOpen(true)}
      />

      {/* Edit Chat Title Modal */}
      {editingSession && (
        <EditChatModal
          isOpen={Boolean(editingSession)}
          onClose={() => setEditingSession(null)}
          currentTitle={editingSession.title}
          onSave={(newTitle) => {
            handleRenameSession(editingSession.id, newTitle);
            setEditingSession(null);
          }}
        />
      )}

      {/* Delete Chat Confirmation Modal */}
      {deletingSession && (
        <DeleteChatModal
          isOpen={Boolean(deletingSession)}
          onClose={() => setDeletingSession(null)}
          sessionTitle={deletingSession.title}
          onConfirm={() => {
            handleDeleteSession(deletingSession.id);
            setDeletingSession(null);
          }}
        />
      )}
    </div>
  );
};
