"use client";

import React, { useState } from "react";
import { Header } from "./Header";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { AuthScreen } from "@/components/auth/AuthScreen";

export const ChatShell: React.FC = () => {
  const [activeView, setActiveView] = useState<"chat" | "auth">("chat");

  const handleToggleAuth = () => {
    setActiveView((prev) => (prev === "chat" ? "auth" : "chat"));
  };

  const handleContinueAsGuest = () => {
    setActiveView("chat");
  };

  const handleNewChat = () => {
    setActiveView("chat");
  };

  return (
    <div className="flex flex-col min-h-screen bg-humsafar-background">
      {/* Top Fixed Header */}
      <Header
        activeView={activeView}
        onOpenAuth={handleToggleAuth}
        onNewChat={handleNewChat}
      />

      {/* Main Body */}
      {activeView === "chat" ? (
        <main className="flex-1 flex flex-col justify-between overflow-hidden">
          <MessageList />
          <ChatInput />
        </main>
      ) : (
        <main className="flex-1 flex items-center justify-center p-4">
          <AuthScreen
            onContinueAsGuest={handleContinueAsGuest}
            onLoginSuccess={() => setActiveView("chat")}
          />
        </main>
      )}
    </div>
  );
};
