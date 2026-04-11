import type { LucideIcon } from "lucide-react";
import { ArrowDownRightIcon, ArrowUpRightIcon, MinusIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Muted } from "@/components/ui/typography";

type StatsCardProps = {
  title: string;
  value: string;
  delta: string;
  tooltip?: string;
  icon?: LucideIcon;
  tone?: "positive" | "warning" | "neutral";
  onClick?: () => void;
  active?: boolean;
};

const toneStyles = {
  positive: "text-emerald-300 bg-emerald-500/12",
  warning: "text-amber-300 bg-amber-500/12",
  neutral: "text-sky-300 bg-sky-500/12",
};

export default function StatsCard({
  title,
  value,
  delta,
  tooltip,
  icon: Icon,
  tone = "neutral",
  onClick,
  active = false,
}: StatsCardProps) {
  const DeltaIcon =
    tone === "positive"
      ? ArrowUpRightIcon
      : tone === "warning"
        ? ArrowDownRightIcon
        : MinusIcon;

  return (
    <Card
      className={cn(
        "glass-panel rounded-[1.75rem] border-border/60 shadow-xl shadow-black/20",
        active ? "border-primary/70 ring-1 ring-primary/30" : "",
        onClick ? "cursor-pointer transition hover:border-primary/50" : "",
      )}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          {tooltip ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <CardTitle className="cursor-help text-sm font-medium text-muted-foreground">
                  {title}
                </CardTitle>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-72">
                {tooltip}
              </TooltipContent>
            </Tooltip>
          ) : (
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {title}
            </CardTitle>
          )}
          <p className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
            {value}
          </p>
        </div>
        {Icon ? (
          <div
            className={cn(
              "flex size-11 items-center justify-center rounded-2xl",
              toneStyles[tone],
            )}
          >
            <Icon className="size-5" />
          </div>
        ) : null}
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 text-sm">
          <DeltaIcon
            className={cn(
              "size-4",
              tone === "warning" ? "text-amber-300" : "text-emerald-300",
            )}
          />
          <Muted className="text-sm">{delta}</Muted>
        </div>
      </CardContent>
    </Card>
  );
}
