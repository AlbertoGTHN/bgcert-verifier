"use client";

import { cn } from "@/lib/utils";
import type { ValidationStatus } from "@/lib/types";
import { STATUS_CONFIG } from "@/lib/types";
import { Loader2 } from "lucide-react";

interface StatusBadgeProps {
  status: ValidationStatus;
  size?: "sm" | "md" | "lg";
  showIcon?: boolean;
}

export function StatusBadge({ status, size = "md", showIcon = true }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  const sizeClasses = {
    sm: "text-xs px-2 py-0.5 gap-1",
    md: "text-xs px-2.5 py-1 gap-1.5",
    lg: "text-sm px-3 py-1.5 gap-2",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center font-medium rounded-full border",
        config.bgColor,
        config.borderColor,
        config.textColor,
        config.darkBg,
        config.darkText,
        sizeClasses[size]
      )}
    >
      {showIcon && (
        status === "processing" ? (
          <Loader2 size={size === "lg" ? 14 : 10} className="animate-spin" />
        ) : (
          <span className="text-current">{config.icon}</span>
        )
      )}
      {config.label}
    </span>
  );
}
