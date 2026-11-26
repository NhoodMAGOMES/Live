import * as React from "react";
import { Slot } from "@radix-ui/react-slot";

import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  asChild?: boolean;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "icon";
};

export function Button({ className, variant = "primary", size = "md", asChild, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md border text-sm font-medium transition duration-150 hover:-translate-y-0.5 hover:shadow-md active:translate-y-0 focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:pointer-events-none disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-none",
        variant === "primary" && "border-primary bg-primary px-3 text-white hover:bg-primary/90",
        variant === "secondary" && "border-primary-light bg-primary-extra-light px-3 text-primary hover:border-primary hover:bg-primary-light/25",
        variant === "ghost" && "border-transparent bg-transparent px-2 text-foreground hover:bg-primary-extra-light hover:text-primary",
        variant === "danger" && "border-danger bg-danger px-3 text-white hover:bg-danger/90",
        size === "sm" && "h-8 px-2 text-xs",
        size === "md" && "h-9",
        size === "icon" && "h-9 w-9 p-0",
        className
      )}
      {...props}
    />
  );
}
