"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Plus,
  ArrowUp,
  Square,
  Mic,
  Paperclip,
  FileText,
  AlertCircle,
  X,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import { api } from "@/lib/api";

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop: () => void;
  isStreaming?: boolean;
  inputText?: string;
  setInputText?: (val: string) => void;
  activeSessionId?: string;
  onEnsureSession?: () => Promise<string>;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onStop,
  isStreaming = false,
  inputText,
  setInputText,
  activeSessionId,
  onEnsureSession,
}) => {
  const [localInput, setLocalInput] = useState("");
  const input = inputText !== undefined ? inputText : localInput;
  const setInputValue = setInputText || setLocalInput;
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Voice recording state
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Document upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploadingDoc, setIsUploadingDoc] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [attachedDocs, setAttachedDocs] = useState<
    Array<{ name: string; size: string }>
  >([]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // Reset height to auto first to accurately calculate scrollHeight on deletions/shrink
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [input]);

  // Clean up recording stream on unmount
  useEffect(() => {
    return () => {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isStreaming) {
      onStop();
      return;
    }
    const messageToSend =
      input.trim() ||
      (attachedDocs.length > 0
        ? `Please review my uploaded document "${attachedDocs[0].name}" and help plan my trip.`
        : "");

    if (messageToSend) {
      onSend(messageToSend);
      setInputValue("");
      setAttachedDocs([]);
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // --- Voice Input (MediaRecorder + Groq Whisper) ---
  const startRecording = async () => {
    setVoiceError(null);
    if (typeof window === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setVoiceError("Audio recording is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      let mimeType = "";
      if (typeof MediaRecorder !== "undefined") {
        if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
          mimeType = "audio/webm;codecs=opus";
        } else if (MediaRecorder.isTypeSupported("audio/webm")) {
          mimeType = "audio/webm";
        } else if (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")) {
          mimeType = "audio/ogg;codecs=opus";
        } else if (MediaRecorder.isTypeSupported("audio/ogg")) {
          mimeType = "audio/ogg";
        }
      }

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        // Stop audio tracks so browser mic recording icon disappears
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;

        if (recordingTimerRef.current) {
          clearInterval(recordingTimerRef.current);
          recordingTimerRef.current = null;
        }
        setIsRecording(false);
        setRecordingSeconds(0);

        const chunks = audioChunksRef.current;
        if (!chunks || chunks.length === 0) {
          setVoiceError("No speech detected. Please speak clearly and try again.");
          return;
        }

        const audioBlob = new Blob(chunks, { type: mimeType || "audio/webm" });
        if (audioBlob.size < 300) {
          setVoiceError("No speech detected. Please speak clearly and try again.");
          return;
        }

        try {
          setIsTranscribing(true);
          const ext = mimeType.includes("ogg") ? "audio.ogg" : "audio.webm";
          const res = await api.transcribeAudio(audioBlob, ext);
          const transcript = (res.transcript || "").trim();

          if (!transcript) {
            setVoiceError("No speech detected. Please speak clearly and try again.");
          } else {
            // Rule: The transcript fills the composer text field as editable text, it must never be sent automatically.
            setInputValue(input.trim() ? `${input.trim()} ${transcript}` : transcript);
            setVoiceError(null);
          }
        } catch (err: any) {
          const detail = err?.message || err?.detail || "";
          if (
            detail.toLowerCase().includes("no speech") ||
            detail.toLowerCase().includes("empty")
          ) {
            setVoiceError("No speech detected. Please speak clearly and try again.");
          } else {
            setVoiceError("Audio transcription failed. Please check your connection and try again.");
          }
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);
      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds((s) => s + 1);
      }, 1000);
    } catch (err: any) {
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setVoiceError("Microphone permission was denied. Please allow microphone access in your browser settings to use voice input.");
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        setVoiceError("No microphone found. Please connect an audio input device and try again.");
      } else {
        setVoiceError("Could not access microphone. Please check your browser audio permissions.");
      }
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
    setIsRecording(false);
  };

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  // --- Document Upload (PDF, TXT, PNG, JPEG, WEBP - max 10MB) ---
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (!file) return;

    setUploadError(null);

    // Validate 10 MB cap
    const MAX_SIZE = 10 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      setUploadError(`"${file.name}" exceeds the 10 MB limit. Please choose a smaller document.`);
      return;
    }

    try {
      setIsUploadingDoc(true);
      let targetSession = activeSessionId;
      if ((!targetSession || targetSession.startsWith("guest-local-")) && onEnsureSession) {
        targetSession = await onEnsureSession();
      }
      if (!targetSession || targetSession.startsWith("guest-local-")) {
        setUploadError("Unable to establish chat session for document upload.");
        return;
      }

      await api.uploadDocument(file, targetSession);
      const sizeStr =
        file.size < 1024 * 1024
          ? `${Math.round(file.size / 1024)} KB`
          : `${(file.size / (1024 * 1024)).toFixed(1)} MB`;

      setAttachedDocs((prev) => [...prev, { name: file.name, size: sizeStr }]);
      if (!input.trim()) {
        setInputValue(`Please review my uploaded document "${file.name}" and help plan my trip.`);
      }
    } catch (err: any) {
      const msg =
        err?.message ||
        err?.detail ||
        "Document upload failed. Ensure the file is a valid PDF, TXT, or image (PNG, JPEG, WEBP).";
      setUploadError(msg);
    } finally {
      setIsUploadingDoc(false);
    }
  };

  return (
    <div className="sticky bottom-0 w-full bg-gradient-to-t from-white via-white/95 to-transparent pt-3 pb-4 sm:pb-6 px-4 sm:px-6 z-20">
      <div className="max-w-chat mx-auto space-y-2">
        {/* Hidden File Input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.png,.jpg,.jpeg,.webp,application/pdf,text/plain,image/png,image/jpeg,image/webp"
          onChange={handleFileSelect}
          className="hidden"
        />

        {/* Visible Error Banner for Voice and Upload Failures */}
        {(voiceError || uploadError) && (
          <div className="flex items-center justify-between gap-2 px-3.5 py-2.5 rounded-xl bg-rose-50 border border-rose-200/80 text-rose-800 text-xs shadow-xs animate-in fade-in">
            <div className="flex items-center gap-2 min-w-0">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span className="truncate">{voiceError || uploadError}</span>
            </div>
            <button
              type="button"
              onClick={() => {
                setVoiceError(null);
                setUploadError(null);
              }}
              className="p-1 text-rose-500 hover:text-rose-700 hover:bg-rose-100 rounded-md transition-colors cursor-pointer shrink-0"
              title="Dismiss error"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Attached Documents List */}
        {attachedDocs.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap px-1">
            {attachedDocs.map((doc, idx) => (
              <div
                key={idx}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-teal-50 border border-teal-200 text-teal-900 text-xs shadow-2xs"
              >
                <FileText className="w-3.5 h-3.5 text-humsafar-teal shrink-0" />
                <span className="font-medium max-w-[170px] truncate">{doc.name}</span>
                <span className="text-[10.5px] text-teal-700 font-mono">({doc.size})</span>
                <span className="text-[10px] text-teal-700 font-semibold bg-teal-100/70 px-1.5 py-0.5 rounded">
                  Distilled for Context
                </span>
                <button
                  type="button"
                  onClick={() => setAttachedDocs((prev) => prev.filter((_, i) => i !== idx))}
                  className="p-0.5 text-teal-600 hover:text-rose-600 hover:bg-teal-100 rounded transition-colors cursor-pointer ml-0.5"
                  title="Remove document"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Floating Claude-Style Composer */}
        <form
          onSubmit={handleSubmit}
          className="relative bg-white border border-slate-300/90 rounded-2xl shadow-composer focus-within:border-humsafar-teal focus-within:ring-2 focus-within:ring-humsafar-teal/20 transition-all p-2 sm:p-2.5"
        >
          <div className="flex items-end gap-2">
            {/* Document Upload Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploadingDoc || isStreaming || isRecording}
              title="Attach travel document or image (PDF, TXT, PNG, JPEG, WEBP - max 10MB)"
              className="p-1.5 text-slate-500 hover:text-humsafar-navy hover:bg-slate-100 rounded-lg transition-colors cursor-pointer shrink-0 mb-1 disabled:opacity-40"
            >
              {isUploadingDoc ? (
                <Loader2 className="w-4 h-4 animate-spin text-humsafar-teal" />
              ) : (
                <Paperclip className="w-4 h-4" />
              )}
            </button>

            {/* Expanding Textarea or Recording State */}
            {isRecording ? (
              <div className="flex-1 flex items-center gap-3 py-2 px-2">
                <span className="w-3 h-3 rounded-full bg-rose-500 animate-ping shrink-0" />
                <span className="text-sm font-medium text-rose-700">
                  Listening... Speak your travel plan
                </span>
                <span className="text-xs font-mono text-slate-500 ml-auto">
                  0:{recordingSeconds < 10 ? `0${recordingSeconds}` : recordingSeconds}
                </span>
              </div>
            ) : isTranscribing ? (
              <div className="flex-1 flex items-center gap-2.5 py-2 px-2">
                <Loader2 className="w-4 h-4 animate-spin text-humsafar-teal shrink-0" />
                <span className="text-sm font-medium text-slate-600">
                  Transcribing your voice with Groq Whisper...
                </span>
              </div>
            ) : (
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                disabled={isStreaming}
                placeholder={
                  isStreaming
                    ? "Humsafar is synthesizing verified itinerary data..."
                    : "Write a message..."
                }
                className="flex-1 resize-none bg-transparent border-none text-[15px] text-humsafar-bodyText placeholder-slate-400 focus:outline-none focus:ring-0 leading-relaxed py-1.5 px-1 max-h-40 overflow-y-auto disabled:opacity-60"
              />
            )}

            {/* Right Action Icons: Mic + Send/Stop */}
            <div className="flex items-center gap-1.5 shrink-0 mb-0.5">
              {/* Mic / Voice Recording Button */}
              <button
                type="button"
                onClick={toggleRecording}
                disabled={isStreaming || isTranscribing}
                className={`p-2 rounded-xl transition-all cursor-pointer ${
                  isRecording
                    ? "bg-rose-500 text-white shadow-xs animate-pulse hover:bg-rose-600"
                    : "text-slate-500 hover:text-humsafar-navy hover:bg-slate-100"
                } disabled:opacity-40`}
                title={isRecording ? "Stop recording voice" : "Start voice input"}
              >
                {isRecording ? (
                  <Square className="w-3.5 h-3.5 fill-current" />
                ) : (
                  <Mic className="w-4 h-4" />
                )}
              </button>

              {/* Stop Streaming or Submit Button */}
              {isStreaming ? (
                <button
                  type="button"
                  onClick={onStop}
                  className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-humsafar-navy border border-slate-300 transition-colors cursor-pointer"
                  title="Stop generating"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={(!input.trim() && attachedDocs.length === 0) || isRecording || isTranscribing}
                  className="p-2 rounded-xl bg-humsafar-teal hover:bg-humsafar-tealHover disabled:opacity-30 disabled:pointer-events-none text-white transition-all shadow-xs cursor-pointer"
                  title={attachedDocs.length > 0 && !input.trim() ? "Send with attached document" : "Send message"}
                >
                  <ArrowUp className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        </form>

        {/* Footer: Disclaimer + Tech Stack Model Indicator (Claude Style) */}
        <div className="flex items-center justify-between text-[11px] text-slate-500 px-1 pt-0.5">
          <p className="truncate">
            Humsafar is AI grounded in live data from{" "}
            <span className="font-medium text-slate-700">askoliadventure.com</span>.
          </p>

          <div className="flex items-center gap-1.5 text-slate-600 font-medium shrink-0 ml-3">
            <span className="w-1.5 h-1.5 rounded-full bg-humsafar-teal" />
            <span>Groq LLaMA 3.3 70B & Whisper</span>
          </div>
        </div>
      </div>
    </div>
  );
};
