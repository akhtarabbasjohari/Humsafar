"use client";

import React, { useState } from "react";
import Image from "next/image";
import { Compass, UserCheck, Shield, Sparkles, ArrowRight, Lock, Mail, User as UserIcon } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";

interface AuthScreenProps {
  onContinueAsGuest: () => void;
  onLoginSuccess?: () => void;
}

export const AuthScreen: React.FC<AuthScreenProps> = ({
  onContinueAsGuest,
  onLoginSuccess,
}) => {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Static placeholder interaction for Phase 2
    if (onLoginSuccess) {
      onLoginSuccess();
    }
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4 sm:p-6 bg-humsafar-background">
      <div className="w-full max-w-md bg-white border border-humsafar-subtleBorder rounded-2xl shadow-floating overflow-hidden">
        {/* Top Accent Header */}
        <div className="bg-humsafar-header px-6 py-8 text-center text-white relative">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-[#0A2219] border border-humsafar-accent/40 p-1.5 flex items-center justify-center mb-3 shadow-inner">
            <Image
              src="/logo.png"
              alt="Humsafar Logo"
              width={48}
              height={48}
              className="object-contain"
            />
          </div>
          <h2 className="text-xl font-bold tracking-tight text-[#FFFDF7]">
            HUMSAFAR
          </h2>
          <p className="text-xs text-humsafar-accent font-medium italic mt-0.5">
            Plan better. Travel farther.
          </p>
          <div className="mt-3 flex justify-center">
            <Badge variant="live" className="text-[10px]">
              Indus Trekking & Tours Pakistan
            </Badge>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Guest Mode Card (Default Frictionless Entry) */}
          <div className="bg-humsafar-agentBubble/70 border border-humsafar-agentBubbleBorder rounded-xl p-4 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-humsafar-header flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-humsafar-accent" />
                Default Guest Access
              </span>
              <Badge variant="verified" className="text-[10px]">
                No Account Needed
              </Badge>
            </div>
            <p className="text-xs text-humsafar-slate leading-relaxed">
              Start planning your expedition immediately. Draft itineraries and explore routes with zero signup friction.
            </p>
            <Button
              variant="primary"
              size="md"
              onClick={onContinueAsGuest}
              className="w-full justify-center !rounded-xl"
              icon={<ArrowRight className="w-4 h-4" />}
            >
              Continue as Guest Traveler
            </Button>
          </div>

          <div className="relative flex items-center justify-center">
            <div className="border-t border-humsafar-subtleBorder w-full" />
            <span className="bg-white px-3 text-xs uppercase tracking-wider font-semibold text-humsafar-mutedText absolute">
              Or Sign In for Persisted History
            </span>
          </div>

          {/* Member Login / Register Tabs */}
          <div className="space-y-4">
            <div className="grid grid-cols-2 bg-humsafar-surfaceParchment p-1 rounded-xl border border-humsafar-subtleBorder">
              <button
                type="button"
                onClick={() => setMode("login")}
                className={`py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  mode === "login"
                    ? "bg-white text-humsafar-header shadow-subtle"
                    : "text-humsafar-mutedText hover:text-humsafar-slate"
                }`}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => setMode("register")}
                className={`py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  mode === "register"
                    ? "bg-white text-humsafar-header shadow-subtle"
                    : "text-humsafar-mutedText hover:text-humsafar-slate"
                }`}
              >
                Create Account
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3.5">
              <Input
                label="Username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g., karakoram_trekker"
                required
              />

              {mode === "register" && (
                <Input
                  label="Email Address"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  required
                />
              )}

              <Input
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                required
              />

              <Button
                type="submit"
                variant="outline"
                size="md"
                className="w-full justify-center !rounded-xl !border-humsafar-header !text-humsafar-header hover:!bg-humsafar-header hover:!text-white font-semibold mt-2"
              >
                {mode === "login" ? "Sign In to Account" : "Register New Account"}
              </Button>
            </form>
          </div>
        </div>

        {/* Footnote */}
        <div className="px-6 py-3 bg-humsafar-surfaceParchment border-t border-humsafar-subtleBorder text-center">
          <p className="text-[11px] text-humsafar-mutedText">
            All itinerary and region data is sourced live from{" "}
            <span className="font-semibold text-humsafar-slate">itp.7scribes.com</span>
          </p>
        </div>
      </div>
    </div>
  );
};
