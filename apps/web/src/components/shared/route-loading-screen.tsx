import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import {
  AnalyticsRouteSkeleton,
  DetailRouteSkeleton,
  FormRouteSkeleton,
  ListRouteSkeleton,
  WorklistRouteSkeleton,
} from "@/components/shared/page-skeletons";
import { resolveDashboardRouteKind } from "@/lib/dashboard-routes";
import { cn } from "@/lib/utils";

type RouteLoadingVariant = "generic" | "dashboard" | "auth";
type RouteLoadingScope = "fullscreen" | "content";

type RouteLoadingScreenProps = {
  overlay?: boolean;
  variant?: RouteLoadingVariant;
  label?: string;
  className?: string;
  scope?: RouteLoadingScope;
  pathname?: string | null;
};

function LoadingBadge({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-full border border-border/60 bg-card/88 px-4 py-2 text-sm text-muted-foreground shadow-2xl shadow-black/20 backdrop-blur-md">
      <Spinner className="size-4" />
      <span>{label}</span>
    </div>
  );
}

function DashboardRouteSkeleton({ pathname }: { pathname?: string | null }) {
  const kind = resolveDashboardRouteKind(pathname);

  if (kind === "analytics") {
    return <AnalyticsRouteSkeleton />;
  }

  if (kind === "worklist") {
    return <WorklistRouteSkeleton />;
  }

  if (kind === "form") {
    return <FormRouteSkeleton />;
  }

  if (kind === "detail") {
    return <DetailRouteSkeleton />;
  }

  return <ListRouteSkeleton />;
}

function AuthRouteSkeleton() {
  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_0.9fr]">
      <div className="hidden border-r border-border/60 p-10 lg:flex lg:flex-col lg:justify-between">
        <div className="space-y-4">
          <Skeleton className="h-9 w-44 rounded-full" />
          <div className="space-y-4">
            <Skeleton className="h-14 w-4/5 rounded-3xl" />
            <Skeleton className="h-14 w-3/4 rounded-3xl" />
            <Skeleton className="h-5 w-full max-w-xl" />
            <Skeleton className="h-5 w-5/6 max-w-lg" />
          </div>
        </div>
        <div className="grid max-w-2xl gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={index}
              className="rounded-[1.75rem] border border-border/60 bg-card/60 p-5 shadow-xl shadow-black/10"
            >
              <Skeleton className="h-8 w-12" />
              <Skeleton className="mt-3 h-4 w-24" />
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md rounded-[2rem] border border-border/60 bg-card/72 p-6 shadow-2xl shadow-black/15">
          <div className="space-y-4">
            <Skeleton className="size-12 rounded-2xl" />
            <Skeleton className="h-8 w-44" />
            <Skeleton className="h-4 w-72 max-w-full" />
          </div>
          <div className="mt-8 space-y-5">
            <div className="space-y-2">
              <Skeleton className="h-4 w-14" />
              <Skeleton className="h-11 w-full rounded-xl" />
            </div>
            <div className="space-y-2">
              <Skeleton className="h-4 w-14" />
              <Skeleton className="h-11 w-full rounded-xl" />
              <Skeleton className="h-4 w-40" />
            </div>
            <Skeleton className="h-11 w-full rounded-2xl" />
          </div>
        </div>
      </div>
    </div>
  );
}

function GenericRouteSkeleton() {
  return (
    <div className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-6 p-4 md:p-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <Skeleton className="h-12 w-full max-w-xl rounded-2xl" />
        <div className="flex items-center gap-3">
          <Skeleton className="h-11 w-28 rounded-2xl" />
          <Skeleton className="h-11 w-36 rounded-2xl" />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-32 w-full rounded-[1.75rem]" />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Skeleton className="h-[22rem] w-full rounded-[2rem]" />
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-16 w-full rounded-[1.5rem]" />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function RouteLoadingScreen({
  overlay = false,
  variant = "generic",
  label = "Carregando modulo...",
  className,
  scope = "fullscreen",
  pathname,
}: RouteLoadingScreenProps) {
  const isContentScope = scope === "content";

  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className={cn(
        overlay
          ? isContentScope
            ? "absolute inset-0 z-40 overflow-auto bg-background/88 backdrop-blur-md"
            : "fixed inset-0 z-[120] overflow-auto bg-background/88 backdrop-blur-md"
          : isContentScope
            ? "min-h-full"
            : "min-h-screen bg-background",
        className,
      )}
    >
      <div className="absolute top-4 left-1/2 z-10 -translate-x-1/2 md:top-6">
        <LoadingBadge label={label} />
      </div>

      <div
        className={cn(
          "mx-auto w-full max-w-7xl px-4 py-16 md:px-6 md:py-20",
          isContentScope && "max-w-none px-0 py-0 pt-12 md:pt-16",
        )}
      >
        {variant === "dashboard" ? (
          <DashboardRouteSkeleton pathname={pathname} />
        ) : variant === "auth" ? (
          <AuthRouteSkeleton />
        ) : (
          <GenericRouteSkeleton />
        )}
      </div>
    </div>
  );
}
