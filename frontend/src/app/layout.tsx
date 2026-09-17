import type { Metadata } from "next";
import "@/styles/globals.css";
import { QueryProvider } from "@/providers/QueryProvider";

export const metadata: Metadata = {
  title: "Humsafar — AI Travel Planning | Askoli Adventure",
  description: "Plan better. Travel farther. Live ground-truth AI travel planning for Pakistan's northern mountain regions.",
  icons: {
    icon: "/logo.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full bg-white text-humsafar-bodyText antialiased selection:bg-humsafar-teal/20 selection:text-humsafar-navy">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
