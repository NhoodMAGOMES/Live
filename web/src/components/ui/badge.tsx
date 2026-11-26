import type React from "react";

import { cn } from "@/lib/utils";

export function Badge({
  children,
  tone = "neutral"
}: {
  children: React.ReactNode;
  tone?: "neutral" | "green" | "amber" | "red" | "blue";
}) {
  return (
    <span
      className={cn(
        "inline-flex min-h-6 items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        tone === "neutral" && "border-border bg-muted text-foreground",
        tone === "green" && "border-primary-light bg-primary-extra-light text-primary",
        tone === "amber" && "border-brand-gold/60 bg-brand-gold/15 text-brand-marine",
        tone === "red" && "border-danger/30 bg-danger-light text-danger",
        tone === "blue" && "border-brand-blue/25 bg-brand-blue/10 text-brand-blue"
      )}
    >
      {children}
    </span>
  );
}
