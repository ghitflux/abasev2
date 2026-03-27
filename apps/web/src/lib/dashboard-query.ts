"use client";

import { keepPreviousData } from "@tanstack/react-query";

export const DASHBOARD_QUERY_STALE_TIME = 30 * 1000;
export const DASHBOARD_QUERY_GC_TIME = 10 * 60 * 1000;
export const DASHBOARD_OPTIONS_STALE_TIME = 5 * 60 * 1000;

export const dashboardRetainedQueryOptions = {
  staleTime: DASHBOARD_QUERY_STALE_TIME,
  placeholderData: keepPreviousData,
} as const;

export const dashboardOptionsQueryOptions = {
  staleTime: DASHBOARD_OPTIONS_STALE_TIME,
} as const;
