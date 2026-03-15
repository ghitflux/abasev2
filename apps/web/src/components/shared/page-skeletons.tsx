import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function buildWidths(count: number) {
  const widths = ["w-3/4", "w-2/3", "w-1/2", "w-5/6", "w-3/5", "w-2/5"];

  return Array.from({ length: count }, (_, index) => widths[index % widths.length]);
}

export function MetricCardSkeleton() {
  return (
    <div className="glass-panel rounded-[1.75rem] border border-border/60 p-6 shadow-xl shadow-black/20">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1 space-y-3">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-10 w-24" />
          <Skeleton className="h-4 w-40" />
        </div>
        <Skeleton className="size-11 rounded-2xl" />
      </div>
      <div className="mt-5 flex items-center gap-2">
        <Skeleton className="size-4 rounded-full" />
        <Skeleton className="h-4 w-24" />
      </div>
    </div>
  );
}

export function SummaryCardSkeleton() {
  return (
    <div className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6 shadow-xl shadow-black/20">
      <div className="space-y-3">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-20" />
        <Skeleton className="h-4 w-32" />
      </div>
    </div>
  );
}

export function HeroSectionSkeleton({
  compact = false,
  actions = 2,
}: {
  compact?: boolean;
  actions?: number;
}) {
  return (
    <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6 shadow-xl shadow-black/15">
      <div
        className={cn(
          "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between",
          compact && "gap-3",
        )}
      >
        <div className="max-w-3xl space-y-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-72 max-w-full" />
          <Skeleton className="h-4 w-full max-w-2xl" />
          {!compact ? <Skeleton className="h-4 w-5/6 max-w-3xl" /> : null}
        </div>
        <div className="flex flex-wrap gap-3">
          {Array.from({ length: actions }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-28 rounded-2xl" />
          ))}
        </div>
      </div>
    </section>
  );
}

export function FilterToolbarSkeleton({
  fields = 3,
  buttons = 2,
  className,
}: {
  fields?: number;
  buttons?: number;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 xl:grid-cols-[minmax(0,1.2fr)_repeat(2,minmax(0,0.6fr))_auto_auto]",
        className,
      )}
    >
      {Array.from({ length: fields }).map((_, index) => (
        <Skeleton
          key={index}
          className={cn(
            "h-11 w-full rounded-2xl",
            index === 0 ? "xl:col-span-2" : "",
          )}
        />
      ))}
      {Array.from({ length: buttons }).map((_, index) => (
        <Skeleton key={`button-${index}`} className="h-11 w-28 rounded-2xl" />
      ))}
    </section>
  );
}

export function DataTableCardSkeleton({
  columns = 6,
  rows = 6,
  className,
}: {
  columns?: number;
  rows?: number;
  className?: string;
}) {
  const widths = buildWidths(columns);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-[1.75rem] border border-border/60 bg-card/70 shadow-xl shadow-black/20",
        className,
      )}
    >
      <div className="grid gap-4 border-b border-border/60 px-5 py-4 md:grid-cols-6">
        {Array.from({ length: columns }).map((_, index) => (
          <Skeleton key={`head-${index}`} className={cn("h-3 rounded-full", widths[index])} />
        ))}
      </div>
      <div className="divide-y divide-border/60">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div key={rowIndex} className="grid gap-4 px-5 py-4 md:grid-cols-6">
            {Array.from({ length: columns }).map((__, columnIndex) => (
              <Skeleton
                key={`${rowIndex}-${columnIndex}`}
                className={cn(
                  "h-4 rounded-full",
                  widths[(rowIndex + columnIndex) % widths.length],
                )}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 px-5 py-4">
        <Skeleton className="h-4 w-32" />
        <div className="flex items-center gap-2">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="size-9 rounded-xl" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function InlinePanelSkeleton({
  rows = 3,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-4", className)}>
      <div className="grid gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div
            key={index}
            className="rounded-2xl border border-border/60 bg-background/50 p-4"
          >
            <Skeleton className="h-3 w-20" />
            <Skeleton className="mt-3 h-5 w-24" />
            <Skeleton className="mt-2 h-4 w-32" />
          </div>
        ))}
      </div>
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="rounded-2xl border border-border/60 bg-card/60 p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-2">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-4 w-44" />
            </div>
            <Skeleton className="h-6 w-24 rounded-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function DialogFormSkeleton() {
  return (
    <div className="space-y-4 rounded-[1.75rem] border border-border/60 bg-card/60 p-6">
      <div className="space-y-2">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-4 w-full max-w-2xl" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-11 w-full rounded-xl" />
          </div>
        ))}
      </div>
      <Skeleton className="h-32 w-full rounded-[1.5rem]" />
      <div className="flex justify-end gap-3">
        <Skeleton className="h-10 w-24 rounded-2xl" />
        <Skeleton className="h-10 w-36 rounded-2xl" />
      </div>
    </div>
  );
}

export function ListRouteSkeleton({ metricCards = 4 }: { metricCards?: number }) {
  return (
    <div className="space-y-6">
      {metricCards > 0 ? (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: metricCards }).map((_, index) => (
            <MetricCardSkeleton key={index} />
          ))}
        </section>
      ) : null}
      <FilterToolbarSkeleton />
      <DataTableCardSkeleton />
    </div>
  );
}

export function WorklistRouteSkeleton() {
  return (
    <div className="space-y-6">
      <HeroSectionSkeleton compact actions={1} />
      <FilterToolbarSkeleton fields={4} />
      <DataTableCardSkeleton rows={5} />
      <div className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6 shadow-xl shadow-black/15">
        <div className="space-y-3">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-4 w-72 max-w-full" />
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full rounded-[1.5rem]" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function FormRouteSkeleton() {
  return (
    <div className="space-y-6">
      <HeroSectionSkeleton />
      <div className="grid gap-6 xl:grid-cols-[18rem_minmax(0,1fr)]">
        <div className="rounded-[1.75rem] border border-border/60 bg-card/70 p-5 shadow-xl shadow-black/15">
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="flex items-center gap-3">
                <Skeleton className="size-8 rounded-full" />
                <div className="min-w-0 flex-1 space-y-2">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-3 w-20" />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="space-y-6">
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={index}
              className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6 shadow-xl shadow-black/15"
            >
              <div className="space-y-3">
                <Skeleton className="h-5 w-36" />
                <Skeleton className="h-4 w-64 max-w-full" />
              </div>
              <div className="mt-6 grid gap-4 md:grid-cols-2">
                {Array.from({ length: 6 }).map((__, fieldIndex) => (
                  <div key={fieldIndex} className="space-y-2">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-11 w-full rounded-xl" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function DetailRouteSkeleton() {
  return (
    <div className="space-y-6">
      <HeroSectionSkeleton actions={2} />
      {Array.from({ length: 4 }).map((_, index) => (
        <div
          key={index}
          className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6 py-5 shadow-xl shadow-black/15"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-2">
              <Skeleton className="h-5 w-44" />
              <Skeleton className="h-4 w-72 max-w-full" />
            </div>
            <Skeleton className="size-5 rounded-full" />
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((__, itemIndex) => (
              <div key={itemIndex} className="space-y-2">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-5 w-32" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function AnalyticsSectionSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <MetricCardSkeleton key={index} />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-3">
        <div className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6 shadow-xl shadow-black/15 xl:col-span-2">
          <div className="space-y-3">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-4 w-80 max-w-full" />
          </div>
          <Skeleton className="mt-6 h-[18rem] w-full rounded-[1.5rem]" />
        </div>
        <div className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6 shadow-xl shadow-black/15">
          <div className="space-y-3">
            <Skeleton className="h-5 w-36" />
            <Skeleton className="h-4 w-56 max-w-full" />
          </div>
          <div className="mt-6 space-y-4">
            {Array.from({ length: 5 }).map((_, index) => (
              <Skeleton key={index} className="h-12 w-full rounded-2xl" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function AnalyticsRouteSkeleton() {
  return (
    <div className="space-y-6">
      <HeroSectionSkeleton />
      <AnalyticsSectionSkeleton />
      <DataTableCardSkeleton rows={5} />
    </div>
  );
}
