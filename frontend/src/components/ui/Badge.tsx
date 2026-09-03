import React from "react";
import clsx from "clsx";

export interface BadgeProps {
  children: React.ReactNode;
  variant?: "accent" | "verified" | "draft" | "neutral" | "live";
  icon?: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "neutral",
  icon,
  className,
}) => {
  const baseStyles =
    "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium tracking-wide uppercase";

  const variantStyles = {
    accent: "bg-[#FDF4E3] text-[#9E6D18] border border-[#F3DBAC]",
    verified: "bg-[#E6F4EE] text-[#0B6B50] border border-[#C1E2D4]",
    draft: "bg-[#FFF8EB] text-[#B07417] border border-[#FCE1B6]",
    neutral: "bg-white text-humsafar-mutedText border border-humsafar-subtleBorder",
    live: "bg-[#0E4A37] text-[#D8EADB] border border-[#1A614A]",
  };

  return (
    <span className={clsx(baseStyles, variantStyles[variant], className)}>
      {variant === "live" && (
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
      )}
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </span>
  );
};
