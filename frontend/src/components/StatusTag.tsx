import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type StatusTagVariant = "success" | "error" | "info" | "warning" | "neutral";

const VARIANT_CLASSES: Record<StatusTagVariant, string> = {
  success: "bg-success-wash text-success-text",
  error: "bg-error-wash text-error-text",
  info: "bg-info-wash text-info-text",
  warning: "bg-warning-wash text-warning-text",
  neutral: "bg-overlay text-text-secondary",
};

type StatusTagProps = {
  variant: StatusTagVariant;
  children: ReactNode;
  className?: string;
};

/** Tag/chip pattern per design-guidelines.md §8 — reused by Phase 3's
 * citation chips and Phase 5's model-routing indicators. */
export function StatusTag({ variant, children, className }: StatusTagProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-xs font-semibold",
        VARIANT_CLASSES[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
