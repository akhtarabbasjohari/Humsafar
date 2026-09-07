"use client";

import React, { useState } from "react";
import Image from "next/image";
import { AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useLoginMutation, useRegisterMutation, useGuestInitMutation } from "@/hooks/useAuthMutations";
import { ApiError } from "@/lib/api";

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

  const loginMutation = useLoginMutation();
  const registerMutation = useRegisterMutation();
  const guestMutation = useGuestInitMutation();

  const activeMutation = mode === "login" ? loginMutation : registerMutation;
  const isLoading = guestMutation.isPending || activeMutation.isPending;

  const currentError = activeMutation.error || guestMutation.error;
  const error = currentError
    ? currentError instanceof ApiError
      ? currentError.message
      : currentError.message || "An unexpected error occurred. Please check your credentials and try again."
    : null;

  const handleGuestClick = () => {
    loginMutation.reset();
    registerMutation.reset();
    guestMutation.mutate(undefined, {
      onSuccess: () => {
        onContinueAsGuest();
      },
      onError: (err: any) => {
        // If network fails, allow offline guest mode as fallback
        console.warn("Guest session init warning:", err);
        onContinueAsGuest();
      },
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === "login") {
      loginMutation.mutate(
        { usernameOrEmail: username, password },
        {
          onSuccess: () => {
            onLoginSuccess?.();
          },
        }
      );
    } else {
      registerMutation.mutate(
        { username, email, password },
        {
          onSuccess: () => {
            onLoginSuccess?.();
          },
        }
      );
    }
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4 sm:p-6 bg-white">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-subtle overflow-hidden">
        {/* Navy Header */}
        <div className="bg-humsafar-navy px-6 py-7 text-center text-white">
          <div className="mx-auto w-12 h-12 rounded-xl bg-black/25 border border-white/10 p-1 flex items-center justify-center mb-3">
            <Image
              src="/logo.png"
              alt="Humsafar Logo"
              width={40}
              height={40}
              className="object-contain"
            />
          </div>
          <h2 className="text-xl font-bold tracking-tight text-white">
            Humsafar
          </h2>
          <p className="text-xs text-white/70 font-normal mt-0.5">
            Plan better. Travel farther.
          </p>
        </div>

        <div className="p-6 space-y-6">
          {/* Guest Mode Option (Default) */}
          <div className="bg-humsafar-tealTint border border-humsafar-tealBorder rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-humsafar-navy">
                Guest Expedition Mode
              </span>
              <span className="text-[11px] font-medium text-humsafar-teal">
                No sign up needed
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Explore routes and draft custom itineraries immediately. Saved in your current browser session.
            </p>
            <Button
              variant="primary"
              size="md"
              onClick={handleGuestClick}
              disabled={isLoading}
              className="w-full justify-center mt-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                  Starting Session...
                </>
              ) : (
                "Continue as Guest"
              )}
            </Button>
          </div>

          <div className="relative flex items-center justify-center">
            <div className="border-t border-slate-200 w-full" />
            <span className="bg-white px-3 text-xs text-humsafar-mutedText absolute">
              or sign in with your account
            </span>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 p-3 rounded-xl text-xs">
              <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Member Login / Register */}
          <div className="space-y-4">
            <div className="grid grid-cols-2 bg-slate-100 p-1 rounded-lg">
              <button
                type="button"
                onClick={() => {
                  setMode("login");
                  loginMutation.reset();
                  registerMutation.reset();
                }}
                className={`py-1.5 text-xs font-semibold rounded-md transition-colors ${
                  mode === "login"
                    ? "bg-white text-humsafar-navy shadow-subtle"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode("register");
                  loginMutation.reset();
                  registerMutation.reset();
                }}
                className={`py-1.5 text-xs font-semibold rounded-md transition-colors ${
                  mode === "register"
                    ? "bg-white text-humsafar-navy shadow-subtle"
                    : "text-slate-500 hover:text-slate-800"
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
                placeholder="e.g. karakoram_trekker"
                required
              />

              {mode === "register" && (
                <Input
                  label="Email address"
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
                variant="approval"
                size="md"
                disabled={isLoading}
                className="w-full justify-center mt-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                    {mode === "login" ? "Authenticating..." : "Creating Account..."}
                  </>
                ) : (
                  mode === "login" ? "Sign In" : "Register Account"
                )}
              </Button>
            </form>
          </div>
        </div>

        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 text-center">
          <p className="text-xs text-humsafar-mutedText">
            Askoli Adventure • askoliadventure.com
          </p>
        </div>
      </div>
    </div>
  );
};
