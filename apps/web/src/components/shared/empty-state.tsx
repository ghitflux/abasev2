import { InboxIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

type EmptyStateProps = {
  title: string;
  description: string;
};

export default function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <Card className="glass-panel rounded-[1.75rem] border-border/60">
      <CardContent className="flex flex-col items-center justify-center gap-4 py-12 text-center">
        <div className="flex size-14 items-center justify-center rounded-3xl bg-primary/12 text-primary">
          <InboxIcon className="size-6" />
        </div>
        <div>
          <p className="text-lg font-semibold text-foreground">{title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
      </CardContent>
    </Card>
  );
}
