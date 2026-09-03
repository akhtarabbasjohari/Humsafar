import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Humsafar — AI Travel Planning | Indus Trekking & Tours Pakistan",
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
      <body className="h-full bg-humsafar-background text-humsafar-charcoal antialiased selection:bg-humsafar-accent/20 selection:text-humsafar-header">
        {children}
      </body>
    </html>
  );
}
