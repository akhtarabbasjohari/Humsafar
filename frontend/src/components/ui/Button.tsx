import React from "react";
import clsx from "clsx";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "approval" | "secondary" | "outline" | "ghost" | "header";
  size?: "sm" | "md" | "lg";
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = "primary",
  size = "md",
  icon,
  className,
  ...props
}) => {
  const baseStyles =
    "inline-flex items-center justify-center font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-2 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none rounded-lg cursor-pointer";

  const sizeStyles = {
    sm: "px-3 py-1.5 text-xs gap-1.5",
    md: "px-4 py-2 text-sm gap-2",
    lg: "px-5 py-2.5 text-base gap-2.5",
  };

  const variantStyles = {
    // Primary Main Action: #0B6B50
    primary:
      "bg-humsafar-mainButton hover:bg-humsafar-mainButtonHover text-white shadow-subtle focus:ring-humsafar-mainButton",
    // HITL Approval Action: #D89B32
    approval:
      "bg-humsafar-approval hover:bg-humsafar-approvalHover text-white font-semibold shadow-subtle focus:ring-humsafar-approval",
    // Secondary Soft Action
    secondary:
      "bg-humsafar-agentBubble text-humsafar-header border border-humsafar-agentBubbleBorder hover:bg-[#DCEDE5] focus:ring-humsafar-mainButton",
    // Subtle Outline
    outline:
      "bg-white text-humsafar-slate border border-humsafar-subtleBorder hover:bg-humsafar-surfaceParchment focus:ring-humsafar-mainButton",
    // Ghost Minimal
    ghost:
      "text-humsafar-slate hover:bg-humsafar-surfaceParchment hover:text-humsafar-header focus:ring-humsafar-mainButton",
    // Header Dark Variant
    header:
      "bg-humsafar-alpineMuted hover:bg-[#28604B] text-[#FFFDF7] border border-humsafar-alpineBorder focus:ring-humsafar-accent text-xs font-medium",
  };

  return (
    <button
      className={clsx(baseStyles, sizeStyles[size], variantStyles[variant], className)}
      {...props}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </button>
  );
};
