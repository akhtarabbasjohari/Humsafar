import React from "react";
import clsx from "clsx";
import { ShieldCheck, AlertCircle, ExternalLink } from "lucide-react";

export interface ConfidenceChipProps {
  type: "official" | "unverified";
  timestamp?: string;
  sourceUrl?: string;
  className?: string;
}

export const ConfidenceChip: React.FC<ConfidenceChipProps> = ({
  type,
  timestamp,
  sourceUrl = "itp.7scribes.com",
  className,
}) => {
  const isOfficial = type === "official";

  return (
    <div
      className={clsx(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors",
        isOfficial
          ? "bg-humsafar-navy text-white border-humsafar-navy shadow-subtle"
          : "bg-white text-humsafar-navy border-humsafar-navy/30 hover:border-humsafar-navy",
        className
      )}
      title={
        isOfficial
          ? `Verified live from official company listing on ${sourceUrl}${timestamp ? ` (${timestamp})` : ""}`
          : "Researched just now via external search. Unverified with tour operator, please confirm."
      }
    >
      {isOfficial ? (
        <ShieldCheck className="w-3.5 h-3.5 text-humsafar-teal shrink-0" />
      ) : (
        <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
      )}

      <span>
        {isOfficial ? "Official Listing" : "Researched • Unverified"}
      </span>

      <span className={clsx("text-[10px]", isOfficial ? "text-white/60" : "text-humsafar-mutedText")}>
        {sourceUrl}
      </span>
    </div>
  );
};
