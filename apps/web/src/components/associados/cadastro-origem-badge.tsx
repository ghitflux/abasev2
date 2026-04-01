"use client";

import * as React from "react";
import { Globe2Icon, SmartphoneIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type CadastroOrigemBadgeProps = {
  origem?: string | null;
  label?: string | null;
  className?: string;
};

export default function CadastroOrigemBadge({
  origem,
  label,
  className,
}: CadastroOrigemBadgeProps) {
  const isMobile = origem === "mobile";
  const Icon = isMobile ? SmartphoneIcon : Globe2Icon;
  const fallbackLabel = isMobile ? "Mobile" : "Web";

  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1 rounded-full border px-2.5 py-1 text-xs font-medium",
        isMobile
          ? "border-sky-500/40 bg-sky-500/10 text-sky-200"
          : "border-slate-500/40 bg-slate-500/10 text-slate-200",
        className,
      )}
    >
      <Icon className="size-3" />
      {label || fallbackLabel}
    </Badge>
  );
}
