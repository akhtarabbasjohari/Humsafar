import React from "react";
import clsx from "clsx";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input: React.FC<InputProps> = ({ label, error, className, ...props }) => {
  return (
    <div className="w-full space-y-1.5">
      {label && (
        <label className="block text-xs font-medium text-humsafar-navy">
          {label}
        </label>
      )}
      <input
        className={clsx(
          "w-full px-3.5 py-2.5 bg-white border rounded-lg text-sm text-humsafar-bodyText placeholder-humsafar-mutedText/60 focus:outline-none focus:ring-2 focus:ring-humsafar-teal/20 focus:border-humsafar-teal transition-colors duration-150 shadow-subtle",
          error ? "border-rose-400 focus:border-rose-500" : "border-humsafar-neutralBorder",
          className
        )}
        {...props}
      />
      {error && <p className="text-xs text-rose-600 mt-1">{error}</p>}
    </div>
  );
};
