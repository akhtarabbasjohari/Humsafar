import React from "react";
import clsx from "clsx";
import { ShieldCheck, AlertCircle, ExternalLink } from "lucide-react";

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

  const fullHref = sourceUrl?.startsWith("http")
    ? sourceUrl
    : `https://${sourceUrl}`;

  return (
    <div
      className={clsx(
        "inline-flex items-center gap-2 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors",
        isOfficial
          ? "bg-humsafar-navy text-white border-humsafar-navy shadow-subtle"
          : "bg-amber-50 text-amber-900 border-amber-300",
        className
      )}
      title={`Confidence: ${displayLabel}${sourceUrl ? ` • Source: ${sourceUrl}` : ""}${timestamp ? ` • ${timestamp}` : ""}`}
    >
      <div className="flex items-center gap-1.5 shrink-0">
        {isOfficial ? (
          <ShieldCheck className="w-3.5 h-3.5 text-humsafar-teal shrink-0" />
        ) : (
          <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
        )}
        <span className="font-semibold">{displayLabel}</span>
      </div>

      {sourceUrl && (
        <a
          href={fullHref}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className={clsx(
            "text-[10.5px] border-l pl-2 ml-0.5 inline-flex items-center gap-1 font-mono font-medium underline-offset-2 hover:underline transition-colors",
            isOfficial
              ? "border-white/20 text-white/80 hover:text-white"
              : "border-amber-300 text-amber-800 hover:text-amber-950"
          )}
          title={`Open verified source: ${sourceUrl}`}
        >
          <span>{sourceUrl.replace(/^https?:\/\//, "").replace(/\/$/, "")}</span>
          <ExternalLink className="w-2.5 h-2.5 opacity-80 shrink-0" />
        </a>
      )}
    </div>
  );
};
