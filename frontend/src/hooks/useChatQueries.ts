import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, SendMessageResponse, ItineraryPreview } from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";

export function useSessionsQuery(enabled: boolean = true) {
  return useQuery({
    queryKey: ["chat-sessions"],
    queryFn: async () => {
      const data = await api.listSessions();
      return Array.isArray(data) ? data : [];
    },
    enabled,
  });
}

export function useMessagesQuery(sessionId: string) {
  return useQuery({
    queryKey: ["chat-messages", sessionId],
    queryFn: async () => {
      if (!sessionId || sessionId.startsWith("guest-local-")) {
        return [];
      }
      const data = await api.getMessages(sessionId);
      return Array.isArray(data) ? data : [];
    },
    enabled: Boolean(sessionId && !sessionId.startsWith("guest-local-")),
  });
}

export function useSendMessageMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    SendMessageResponse,
    Error,
    {
      sessionId: string;
      message: string;
      history?: Array<{ role: string; content: string }>;
      signal?: AbortSignal;
    }
  >({
    mutationFn: async ({ sessionId, message, history, signal }) => {
      return api.sendMessage(sessionId, message, history, signal);
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["chat-messages", variables.sessionId] });
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
  });
}

export function useCreateSessionMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    { id: string; title: string },
    Error,
    { title?: string; forceNew?: boolean }
  >({
    mutationFn: async ({ title = "New Trip Plan", forceNew = false }) => {
      return api.createSession(title, forceNew);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
  });
}

export function useDeleteSessionMutation() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: async (sessionId: string) => {
      return api.deleteSession(sessionId);
    },
    onSuccess: (_, sessionId) => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      queryClient.removeQueries({ queryKey: ["chat-messages", sessionId] });
    },
  });
}

export function useRenameSessionMutation() {
  const queryClient = useQueryClient();

  return useMutation<any, Error, { sessionId: string; newTitle: string }>({
    mutationFn: async ({ sessionId, newTitle }) => {
      return api.updateSessionTitle(sessionId, newTitle);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
  });
}

export function useClaimSessionMutation() {
  const queryClient = useQueryClient();

  return useMutation<any, Error, { sessionId: string; guestToken?: string }>({
    mutationFn: async ({ sessionId, guestToken }) => {
      return api.claimGuestSession(sessionId, guestToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
  });
}

export function useItinerariesQuery(enabled: boolean = true) {
  return useQuery({
    queryKey: ["saved-itineraries"],
    queryFn: async () => {
      const data = await api.listItineraries();
      return Array.isArray(data) ? data : [];
    },
    enabled,
  });
}

export function useSaveItineraryMutation() {
  const queryClient = useQueryClient();

  return useMutation<any, Error, any>({
    mutationFn: async (itineraryData: any) => {
      return api.saveItinerary(itineraryData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-itineraries"] });
    },
  });
}

export function useApproveItineraryMutation() {
  const queryClient = useQueryClient();

  return useMutation<any, Error, { itineraryId: string; notes?: string }>({
    mutationFn: async ({ itineraryId, notes = "" }) => {
      return api.approveItinerary(itineraryId, notes);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-itineraries"] });
    },
  });
}

export function useRedraftItineraryMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    SendMessageResponse,
    Error,
    {
      sessionId: string;
      feedback: string;
      itineraryId?: string;
      currentItinerary?: any;
    }
  >({
    mutationFn: async ({ sessionId, feedback, itineraryId, currentItinerary }) => {
      return api.redraftItinerary(sessionId, {
        feedback,
        itineraryId,
        currentItinerary,
      });
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["chat-messages", variables.sessionId] });
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["saved-itineraries"] });
      if (variables.itineraryId) {
        useAppStore.getState().setApprovalStatus(variables.itineraryId, false);
      }
      if (data?.session_id) {
        useAppStore.getState().setApprovalStatus(data.session_id, false);
      }
      if (data?.itinerary_id) {
        useAppStore.getState().setApprovalStatus(data.itinerary_id, false);
      }
    },
  });
}
