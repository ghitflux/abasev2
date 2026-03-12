import type { LucideIcon } from "lucide-react";
import { ArrowDownRightIcon, ArrowUpRightIcon, MinusIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Muted } from "@/components/ui/typography";

type StatsCardProps = {
  title: string;
  value: string;
  delta: string;
  icon?: LucideIcon;
  tone?: "positive" | "warning" | "neutral";
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
  icon: Icon,
  tone = "neutral",
}: StatsCardProps) {
  const DeltaIcon =
    tone === "positive" ? ArrowUpRightIcon : tone === "warning" ? ArrowDownRightIcon : MinusIcon;

  return (
    <Card className="glass-panel rounded-[1.75rem] border-border/60 shadow-xl shadow-black/20">
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-foreground">{value}</p>
        </div>
        {Icon ? (
          <div className={cn("flex size-11 items-center justify-center rounded-2xl", toneStyles[tone])}>
            <Icon className="size-5" />
          </div>
        ) : null}
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 text-sm">
          <DeltaIcon className={cn("size-4", tone === "warning" ? "text-amber-300" : "text-emerald-300")} />
          <Muted className="text-sm">{delta}</Muted>
        </div>
      </CardContent>
    </Card>
  );
}
