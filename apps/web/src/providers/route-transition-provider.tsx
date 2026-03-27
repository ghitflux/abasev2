"use client";

import * as React from "react";
import { usePathname, useSearchParams } from "next/navigation";

import RouteLoadingScreen from "@/components/shared/route-loading-screen";
import { isDashboardRoute, normalizePathname } from "@/lib/dashboard-routes";

type RouteTransitionContextValue = {
  isRouteTransitioning: boolean;
  isRouteLoadingVisible: boolean;
  pendingHref: string | null;
  startRouteTransition: (href?: string | null) => void;
};

const SHOW_OVERLAY_DELAY_MS = 260;
const MAX_TRANSITION_DURATION_MS = 8000;

const RouteTransitionContext =
  React.createContext<RouteTransitionContextValue | null>(null);

function normalizeInternalHref(href: string) {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const url = new URL(href, window.location.href);
    if (url.origin !== window.location.origin) {
      return null;
    }
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return null;
  }
}

function getCurrentRouteKey() {
  if (typeof window === "undefined") {
    return "";
  }

  return `${window.location.pathname}${window.location.search}${window.location.hash}`;
}

export function RouteTransitionProvider({
  children,
}: React.PropsWithChildren) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isRouteTransitioning, setIsRouteTransitioning] = React.useState(false);
  const [showOverlay, setShowOverlay] = React.useState(false);
  const [pendingHref, setPendingHref] = React.useState<string | null>(null);
  const showOverlayTimerRef = React.useRef<number | null>(null);
  const maxDurationTimerRef = React.useRef<number | null>(null);
  const lastRouteKeyRef = React.useRef<string | null>(null);

  const routeKey = React.useMemo(() => {
    const search = searchParams.toString();
    return search ? `${pathname}?${search}` : pathname;
  }, [pathname, searchParams]);

  const clearTimers = React.useCallback(() => {
    if (showOverlayTimerRef.current !== null) {
      window.clearTimeout(showOverlayTimerRef.current);
      showOverlayTimerRef.current = null;
    }

    if (maxDurationTimerRef.current !== null) {
      window.clearTimeout(maxDurationTimerRef.current);
      maxDurationTimerRef.current = null;
    }
  }, []);

  const finishRouteTransition = React.useCallback(() => {
    clearTimers();
    setIsRouteTransitioning(false);
    setShowOverlay(false);
    setPendingHref(null);
  }, [clearTimers]);

  const startRouteTransition = React.useCallback(
    (href?: string | null) => {
      if (typeof window === "undefined") {
        return;
      }

      if (href) {
        const normalizedHref = normalizeInternalHref(href);
        if (!normalizedHref || normalizedHref === getCurrentRouteKey()) {
          return;
        }
        setPendingHref(normalizedHref);
      } else {
        setPendingHref(null);
      }

      clearTimers();
      setIsRouteTransitioning(true);
      showOverlayTimerRef.current = window.setTimeout(() => {
        setShowOverlay(true);
      }, SHOW_OVERLAY_DELAY_MS);
      maxDurationTimerRef.current = window.setTimeout(() => {
        finishRouteTransition();
      }, MAX_TRANSITION_DURATION_MS);
    },
    [clearTimers, finishRouteTransition],
  );

  React.useEffect(() => {
    if (lastRouteKeyRef.current === null) {
      lastRouteKeyRef.current = routeKey;
      return;
    }

    if (lastRouteKeyRef.current !== routeKey) {
      lastRouteKeyRef.current = routeKey;
      finishRouteTransition();
    }
  }, [finishRouteTransition, routeKey]);

  React.useEffect(() => {
    const handleClickCapture = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }

      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }

      const anchor = target.closest("a[href]");
      if (!(anchor instanceof HTMLAnchorElement)) {
        return;
      }

      const rawHref = anchor.getAttribute("href");
      if (
        !rawHref ||
        rawHref === "#" ||
        rawHref.startsWith("#") ||
        anchor.target === "_blank" ||
        anchor.hasAttribute("download") ||
        anchor.dataset.routeLoader === "ignore"
      ) {
        return;
      }

      startRouteTransition(anchor.href);
    };

    const handlePopState = () => {
      startRouteTransition();
    };

    document.addEventListener("click", handleClickCapture, true);
    window.addEventListener("popstate", handlePopState);

    return () => {
      document.removeEventListener("click", handleClickCapture, true);
      window.removeEventListener("popstate", handlePopState);
    };
  }, [startRouteTransition]);

  React.useEffect(() => {
    return () => {
      clearTimers();
    };
  }, [clearTimers]);

  const transitionTargetPathname = normalizePathname(pendingHref ?? routeKey);
  const currentIsDashboardRoute = isDashboardRoute(routeKey);
  const targetIsDashboardRoute = isDashboardRoute(transitionTargetPathname);
  const shouldUseScopedDashboardOverlay =
    currentIsDashboardRoute && targetIsDashboardRoute;
  const overlayVariant = targetIsDashboardRoute
    ? "dashboard"
    : transitionTargetPathname === "/login"
      ? "auth"
      : "generic";

  const value = React.useMemo(
    () => ({
      isRouteTransitioning,
      isRouteLoadingVisible: showOverlay,
      pendingHref,
      startRouteTransition,
    }),
    [isRouteTransitioning, pendingHref, showOverlay, startRouteTransition],
  );

  return (
    <RouteTransitionContext.Provider value={value}>
      {children}
      {showOverlay && !shouldUseScopedDashboardOverlay ? (
        <RouteLoadingScreen
          overlay
          variant={overlayVariant}
          label="Carregando rota..."
          pathname={transitionTargetPathname}
        />
      ) : null}
    </RouteTransitionContext.Provider>
  );
}

export function useRouteTransition() {
  const context = React.useContext(RouteTransitionContext);

  if (!context) {
    throw new Error(
      "useRouteTransition must be used within a <RouteTransitionProvider />",
    );
  }

  return context;
}
