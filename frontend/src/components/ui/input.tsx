"use client";

import { cn } from "@/lib/utils";
import { forwardRef } from "react";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, ...props }, ref) => {
    return (
      <div className="space-y-1.5">
        {label && (
          <label
            htmlFor={id}
            className="block text-sm font-medium text-surface-700 dark:text-surface-300"
          >
            {label}
          </label>
        )}
        <input
          id={id}
          className={cn(
            "flex h-10 w-full rounded-lg border bg-white px-3 py-2 text-sm shadow-sm transition-colors",
            "placeholder:text-surface-400",
            "focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20",
            "disabled:cursor-not-allowed disabled:opacity-50",
            "dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100",
            error
              ? "border-red-500 focus:border-red-500 focus:ring-red-500/20"
              : "border-surface-300",
            className
          )}
          ref={ref}
          {...props}
        />
        {error && (
          <p className="text-xs text-red-500">{error}</p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };
