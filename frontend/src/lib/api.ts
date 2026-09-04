/**
 * Humsafar API Client
 * Manages JWT tokens, guest session tokens, and communication with DRF backend.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const ACCESS_TOKEN_KEY = "humsafar_access_token";
const REFRESH_TOKEN_KEY = "humsafar_refresh_token";
const USER_KEY = "humsafar_user";
const GUEST_TOKEN_KEY = "humsafar_guest_token";

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  phone_number?: string;
}

export interface AuthResponse {
  access?: string;
  refresh?: string;
  tokens?: {
    access: string;
    refresh: string;
  };
  user: UserProfile;
}

export interface ItineraryPreview {
  title: string;
  duration: string;
  price: string;
  confidence_label?: string;
  source_url?: string;
  scraped_at?: string;
  summary?: string;
  inclusions?: string[];
  exclusions?: string[];
  equipment?: string[];
  contact_details?: {
    company?: string;
    website?: string;
    email?: string;
    advisory?: string;
  };
}

export interface SendMessageResponse {
  user_message: {
    id: string;
    sender: "user";
    content: string;
    created_at: string;
  };
  assistant_message: {
    id: string;
    sender: "assistant";
    content: string;
    created_at: string;
    metadata?: {
      confidence_label?: string;
      source_url?: string;
      timestamp?: string;
      itinerary?: ItineraryPreview;
    };
  };
  itinerary?: ItineraryPreview;
  confidence_label?: string;
  session_title?: string;
  session_id?: string;
}


export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export const authStorage = {
  getAccessToken: (): string | null => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },
  getRefreshToken: (): string | null => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },
  getUser: (): UserProfile | null => {
    if (typeof window === "undefined") return null;
    const raw = localStorage.getItem(USER_KEY);
    try {
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },
  getGuestToken: (): string | null => {
    if (typeof window === "undefined") return null;
    return sessionStorage.getItem(GUEST_TOKEN_KEY) || localStorage.getItem(GUEST_TOKEN_KEY);
  },
  setTokens: (access: string, refresh: string, user?: UserProfile) => {
    if (typeof window === "undefined") return;
    localStorage.setItem(ACCESS_TOKEN_KEY, access);
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
  },
  setGuestToken: (guestToken: string) => {
    if (typeof window === "undefined") return;
    sessionStorage.setItem(GUEST_TOKEN_KEY, guestToken);
  },
  clear: () => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(GUEST_TOKEN_KEY);
  },
  isAuthenticated: (): boolean => {
    if (typeof window === "undefined") return false;
    return Boolean(localStorage.getItem(ACCESS_TOKEN_KEY));
  },
};

async function apiRequest<T>(endpoint: string, options: RequestInit = {}, retryOn401: boolean = true): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };

  const accessToken = authStorage.getAccessToken();
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  } else {
    const guestToken = authStorage.getGuestToken();
    if (guestToken) {
      headers["X-Guest-Token"] = guestToken;
    }
  }

  let response = await fetch(url, {
    ...options,
    headers,
  });

  // Automatic token refresh on 401 Unauthorized
  if (response.status === 401 && retryOn401 && !endpoint.includes("/auth/")) {
    const refreshToken = authStorage.getRefreshToken();
    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${API_BASE_URL}/api/auth/token/refresh/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh: refreshToken }),
        });
        if (refreshRes.ok) {
          const refreshData = await refreshRes.json();
          const newAccess = refreshData.access;
          if (newAccess) {
            authStorage.setTokens(newAccess, refreshToken, authStorage.getUser() || undefined);
            headers["Authorization"] = `Bearer ${newAccess}`;
            response = await fetch(url, {
              ...options,
              headers,
            });
          }
        } else {
          authStorage.clear();
        }
      } catch {
        authStorage.clear();
      }
    }
  }

  if (!response.ok) {
    let errorData: any = {};
    try {
      errorData = await response.json();
    } catch {
      errorData = { detail: response.statusText };
    }

    let message = errorData.detail || errorData.message;
    if (!message && errorData.non_field_errors) {
      message = Array.isArray(errorData.non_field_errors)
        ? errorData.non_field_errors[0]
        : errorData.non_field_errors;
    }

    // Extract field-level errors (e.g. {"username": ["..."], "password": ["..."]})
    if (!message && typeof errorData === "object" && errorData !== null) {
      const fieldErrors: string[] = [];
      for (const [key, val] of Object.entries(errorData)) {
        const errorText = Array.isArray(val) ? val.join(" ") : String(val);
        fieldErrors.push(`${key}: ${errorText}`);
      }
      if (fieldErrors.length > 0) {
        message = fieldErrors.join(" • ");
      }
    }

    if (!message) {
      message = `Request failed with status ${response.status}`;
    }

    throw new ApiError(message, response.status, errorData);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  // Authentication
  async login(usernameOrEmail: string, password: string): Promise<AuthResponse> {
    const data = await apiRequest<AuthResponse>("/api/auth/login/", {
      method: "POST",
      body: JSON.stringify({ username: usernameOrEmail, password }),
    });

    const access = data.access || data.tokens?.access;
    const refresh = data.refresh || data.tokens?.refresh;
    if (access && refresh) {
      authStorage.setTokens(access, refresh, data.user);
    }
    return data;
  },

  async register(username: string, email: string, password: string, phoneNumber?: string): Promise<AuthResponse> {
    const data = await apiRequest<AuthResponse>("/api/auth/register/", {
      method: "POST",
      body: JSON.stringify({
        username: username.trim(),
        email: email.trim(),
        password,
        password2: password,
        password_confirm: password,
        phone_number: phoneNumber || "",
      }),
    });

    const access = data.tokens?.access || data.access;
    const refresh = data.tokens?.refresh || data.refresh;
    if (access && refresh) {
      authStorage.setTokens(access, refresh, data.user);
    }
    return data;
  },

  async initGuestSession(): Promise<{ guest_token: string; session_id: string }> {
    const data = await apiRequest<{ guest_token: string; session_id: string }>("/api/auth/guest/", {
      method: "POST",
      body: JSON.stringify({}),
    });
    if (data.guest_token) {
      authStorage.setGuestToken(data.guest_token);
    }
    return data;
  },

  logout(): void {
    authStorage.clear();
  },

  // Chat Sessions
  async createSession(title: string = "New Trip Plan", forceNew: boolean = false): Promise<{ id: string; title: string }> {
    return apiRequest<{ id: string; title: string }>("/api/chat/sessions/", {
      method: "POST",
      body: JSON.stringify({ title, force_new: forceNew }),
    });
  },

  async listSessions(): Promise<Array<{ id: string; title: string; is_guest: boolean; updated_at?: string }>> {
    return apiRequest("/api/chat/sessions/", {
      method: "GET",
    });
  },

  async deleteSession(sessionId: string): Promise<void> {
    return apiRequest<void>(`/api/chat/sessions/${sessionId}/`, {
      method: "DELETE",
    });
  },

  async updateSessionTitle(sessionId: string, title: string): Promise<any> {
    return apiRequest(`/api/chat/sessions/${sessionId}/`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
  },

  async claimGuestSession(sessionId: string, guestToken?: string): Promise<any> {
    return apiRequest("/api/chat/sessions/claim/", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        guest_token: guestToken || authStorage.getGuestToken(),
      }),
    });
  },

  async getMessages(sessionId: string): Promise<Array<any>> {
    return apiRequest(`/api/chat/sessions/${sessionId}/messages/`, {
      method: "GET",
    });
  },

  async sendMessage(sessionId: string, message: string): Promise<SendMessageResponse> {
    return apiRequest<SendMessageResponse>(`/api/chat/sessions/${sessionId}/send/`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
  },

  // Itineraries
  async listItineraries(): Promise<Array<any>> {
    return apiRequest("/api/itineraries/", {
      method: "GET",
    });
  },

  async saveItinerary(itineraryData: any): Promise<any> {
    return apiRequest("/api/itineraries/", {
      method: "POST",
      body: JSON.stringify(itineraryData),
    });
  },

  async approveItinerary(itineraryId: string, notes: string = ""): Promise<any> {
    return apiRequest(`/api/itineraries/${itineraryId}/approve/`, {
      method: "POST",
      body: JSON.stringify({
        approved: true,
        feedback_or_notes: notes,
      }),
    });
  },
};
