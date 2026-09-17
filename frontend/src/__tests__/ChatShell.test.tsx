import React from "react";
import "@testing-library/jest-dom";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChatShell } from "@/components/chat/ChatShell";
import { api } from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";

// Mock React-Markdown and plugins for jsdom
jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="markdown">{children}</div>,
}));
jest.mock("remark-gfm", () => () => {});
jest.mock("remark-breaks", () => () => {});

// Mock API layer
jest.mock("@/lib/api", () => ({
  api: {
    initGuestSession: jest.fn().mockResolvedValue({
      session_id: "test-guest-session-123",
      guest_token: "mock-token-xyz",
    }),
    sendMessage: jest.fn().mockResolvedValue({
      user_message: {
        id: "msg-user-1",
        sender: "user",
        content: "Plan a trip to Hunza",
        created_at: new Date().toISOString(),
      },
      assistant_message: {
        id: "msg-asst-1",
        sender: "assistant",
        content: "I would be happy to plan your trip to Hunza Valley!",
        created_at: new Date().toISOString(),
      },
      path: "official_match",
      confidence_label: "from our official listing",
      itinerary: null,
    }),
    listSessions: jest.fn().mockResolvedValue([
      { id: "test-guest-session-123", title: "Hunza Expedition", updated_at: new Date().toISOString() },
    ]),
    getMessages: jest.fn().mockResolvedValue([]),
    listSavedItineraries: jest.fn().mockResolvedValue([]),
    createSession: jest.fn().mockResolvedValue({ id: "new-session-456", title: "New Expedition Plan" }),
    deleteSession: jest.fn().mockResolvedValue({}),
    renameSession: jest.fn().mockResolvedValue({ id: "renamed", title: "Renamed Title" }),
    approveItinerary: jest.fn().mockResolvedValue({ status: "approved" }),
  },
  authStorage: {
    getAccessToken: jest.fn().mockReturnValue(null),
    getRefreshToken: jest.fn().mockReturnValue(null),
    getUser: jest.fn().mockReturnValue(null),
    getGuestToken: jest.fn().mockReturnValue("mock-token-xyz"),
    setTokens: jest.fn(),
    setGuestToken: jest.fn(),
    clear: jest.fn(),
    isAuthenticated: jest.fn().mockReturnValue(false),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe("ChatShell Component Test Suite", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAppStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      guestToken: "mock-token-xyz",
      isGuest: true,
      activeSessionId: "test-guest-session-123",
      activeChatTitle: "New Expedition Plan",
      activeView: "chat",
      isSidebarOpen: false,
    });
  });

  test("renders TopBar branding, assistant title and input composer", async () => {
    renderWithClient(<ChatShell />);

    // Branding / Header check
    expect(screen.getAllByText(/Humsafar/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("New Expedition Plan").length).toBeGreaterThan(0);

    // Input textarea check
    const textarea = screen.getByPlaceholderText("Write a message...");
    expect(textarea).toBeInTheDocument();
  });

  test("renders welcome message when session begins", async () => {
    renderWithClient(<ChatShell />);

    // Wait for the initial message to appear
    await waitFor(() => {
      expect(screen.getByText(/Askoli Adventure/i)).toBeInTheDocument();
    });
  });

  test("toggles sidebar visibility on button click", async () => {
    renderWithClient(<ChatShell />);

    // Find the toggle button in TopBar
    const toggleButtons = screen.getAllByRole("button");
    const sidebarToggle = toggleButtons.find(
      (b) => b.getAttribute("title")?.includes("sidebar") || b.getAttribute("aria-label")?.includes("sidebar")
    ) || toggleButtons[0];

    fireEvent.click(sidebarToggle);
    // Zustand state should be toggled
    expect(useAppStore.getState().isSidebarOpen).toBe(true);
  });

  test("submits message and sends query through API", async () => {
    renderWithClient(<ChatShell />);

    const textarea = screen.getByPlaceholderText("Write a message...");
    fireEvent.change(textarea, { target: { value: "Plan a trip to Hunza" } });
    expect(textarea).toHaveValue("Plan a trip to Hunza");

    // Submit the form
    const form = textarea.closest("form");
    if (form) {
      fireEvent.submit(form);
    }

    await waitFor(() => {
      expect(api.sendMessage).toHaveBeenCalledWith(
        expect.any(String),
        "Plan a trip to Hunza",
        expect.any(Array),
        expect.anything()
      );
    });
  });
});
