import React from "react";
import clsx from "clsx";
import { ShieldCheck, AlertCircle } from "lucide-react";

export interface ConfidenceChipProps {
  type?: "official" | "unverified";
  label?: string;
  timestamp?: string;
  sourceUrl?: string;
  className?: string;
}

export const ConfidenceChip: React.FC<ConfidenceChipProps> = ({
  type,
  label,
  timestamp,
  sourceUrl = "itp.7scribes.com",
  className,
}) => {
  // If label is passed, determine if official from text
  const isOfficial = label
    ? label.includes("official")
    : type === "official";

  const displayLabel =
    label ||
    (isOfficial
      ? "from our official listing"
      : "researched just now, unverified, please confirm with our team");

  return (
    <div
      className={clsx(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors",
        isOfficial
          ? "bg-humsafar-navy text-white border-humsafar-navy shadow-subtle"
          : "bg-amber-50 text-amber-900 border-amber-300",
        className
      )}
      title={`Confidence: ${displayLabel}${sourceUrl ? ` • Source: ${sourceUrl}` : ""}${timestamp ? ` • ${timestamp}` : ""}`}
    >
      {isOfficial ? (
        <ShieldCheck className="w-3.5 h-3.5 text-humsafar-teal shrink-0" />
      ) : (
        <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
      )}

      <span className="font-semibold">{displayLabel}</span>

      {sourceUrl && (
        <span
          className={clsx(
            "text-[10.5px] border-l pl-1.5 ml-0.5",
            isOfficial ? "border-white/20 text-white/75" : "border-amber-300 text-amber-800"
          )}
        >
          {sourceUrl.replace(/^https?:\/\//, "").replace(/\/$/, "")}
        </span>
      )}
    </div>
  );
};
