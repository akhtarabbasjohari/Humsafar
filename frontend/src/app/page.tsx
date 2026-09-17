"use client";

import dynamic from "next/dynamic";

const ChatShell = dynamic(
  () => import("@/components/chat/ChatShell").then((mod) => mod.ChatShell),
  { ssr: false }
);

export default function HomePage() {
  return <ChatShell />;
}
