import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, AuthResponse } from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";

export interface LoginParams {
  usernameOrEmail: string;
  password: string;
}

export interface RegisterParams {
  username: string;
  email: string;
  password: string;
  phoneNumber?: string;
}

export function useLoginMutation() {
  const queryClient = useQueryClient();
  const setAuth = useAppStore((state) => state.setAuth);

  return useMutation<AuthResponse, Error, LoginParams>({
    mutationFn: async ({ usernameOrEmail, password }: LoginParams) => {
      return api.login(usernameOrEmail, password);
    },
    onSuccess: (data) => {
      const access = data.access || data.tokens?.access;
      const refresh = data.refresh || data.tokens?.refresh;
      if (access && refresh && data.user) {
        setAuth({ access, refresh }, data.user);
      }
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["saved-itineraries"] });
    },
  });
}

export function useRegisterMutation() {
  const queryClient = useQueryClient();
  const setAuth = useAppStore((state) => state.setAuth);

  return useMutation<AuthResponse, Error, RegisterParams>({
    mutationFn: async ({ username, email, password, phoneNumber }: RegisterParams) => {
      return api.register(username, email, password, phoneNumber);
    },
    onSuccess: (data) => {
      const access = data.tokens?.access || data.access;
      const refresh = data.tokens?.refresh || data.refresh;
      if (access && refresh && data.user) {
        setAuth({ access, refresh }, data.user);
      }
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["saved-itineraries"] });
    },
  });
}

export function useGuestInitMutation() {
  const setGuestToken = useAppStore((state) => state.setGuestToken);

  return useMutation<{ guest_token: string; session_id: string }, Error, void>({
    mutationFn: async () => {
      return api.initGuestSession();
    },
    onSuccess: (data) => {
      if (data.guest_token) {
        setGuestToken(data.guest_token);
      }
    },
  });
}
