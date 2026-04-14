"use client";

import * as React from "react";
import { CheckIcon, CopyIcon } from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";

type CopySnippetProps = {
  label: string;
  value: string;
  copyValue?: string;
  className?: string;
  mono?: boolean;
  inline?: boolean;
};

export default function CopySnippet({
  label,
  value,
  copyValue,
  className,
  mono = false,
  inline = false,
}: CopySnippetProps) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(copyValue ?? value);
      setCopied(true);
      toast.success(`${label} copiado.`);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error(`Nao foi possivel copiar ${label.toLowerCase()}.`);
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={cn(
        inline
          ? "inline-flex max-w-full items-center gap-2 rounded-md px-0 py-0 text-left text-sm font-medium text-foreground transition-colors hover:text-foreground/80"
          : "inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs text-foreground/90 transition-colors hover:bg-background",
        className,
      )}
    >
      {inline ? null : (
        <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          {label}
        </span>
      )}
      <span
        className={cn(
          inline ? "truncate" : "max-w-48 truncate",
          mono && "font-mono",
        )}
      >
        {value}
      </span>
      {copied ? (
        <CheckIcon className="size-3.5 text-emerald-300" />
      ) : (
        <CopyIcon className="size-3.5 text-muted-foreground" />
      )}
    </button>
  );
}
