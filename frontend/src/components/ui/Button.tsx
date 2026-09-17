import React from "react";
import clsx from "clsx";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "approval" | "stop" | "outline" | "ghost" | "header";
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
    "inline-flex items-center justify-center font-medium transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer";

  const sizeStyles = {
    sm: "px-3 py-1.5 text-xs rounded-md gap-1.5",
    md: "px-4 py-2 text-sm rounded-lg gap-2",
    lg: "px-5 py-2.5 text-base rounded-lg gap-2.5",
  };

  const variantStyles = {
    // Primary interactive (Send button, primary actions): Teal #0D9488
    primary:
      "bg-humsafar-teal hover:bg-humsafar-tealHover text-white focus-visible:ring-humsafar-teal shadow-subtle",
    // HITL Approval button: Deep Navy #0F2C3E
    approval:
      "bg-humsafar-navy hover:bg-humsafar-navyHover text-white font-semibold focus-visible:ring-humsafar-navy shadow-subtle",
    // Stop generating button: Crisp Navy border
    stop:
      "bg-white hover:bg-humsafar-navyLight text-humsafar-navy border border-humsafar-navy focus-visible:ring-humsafar-navy text-xs font-semibold",
    // Outline neutral
    outline:
      "bg-white text-humsafar-navy border border-humsafar-neutralBorder hover:bg-humsafar-neutralBg focus-visible:ring-humsafar-teal",
    // Ghost
    ghost:
      "text-humsafar-bodyText hover:bg-humsafar-tealTint hover:text-humsafar-teal focus-visible:ring-humsafar-teal",
    // Header dark variant
    header:
      "bg-white/10 hover:bg-white/15 text-white border border-white/15 focus-visible:ring-humsafar-teal text-xs font-medium rounded-md",
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
