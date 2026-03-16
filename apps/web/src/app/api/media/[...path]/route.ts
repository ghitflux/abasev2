import { NextResponse } from "next/server";

import { BACKEND_BASE_URL } from "@/lib/env";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

function copyIfPresent(
  source: Headers,
  target: Headers,
  name: string,
) {
  const value = source.get(name);
  if (value) {
    target.set(name, value);
  }
}

export async function GET(request: Request, { params }: RouteContext) {
  const { path } = await params;
  const target = new URL(
    `${BACKEND_BASE_URL}/media/${path.map(encodeURIComponent).join("/")}`,
  );
  const incomingUrl = new URL(request.url);
  incomingUrl.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value);
  });

  const response = await fetch(target, {
    method: "GET",
    cache: "no-store",
    redirect: "manual",
  });

  const headers = new Headers();
  copyIfPresent(response.headers, headers, "content-type");
  copyIfPresent(response.headers, headers, "content-disposition");
  copyIfPresent(response.headers, headers, "content-length");
  copyIfPresent(response.headers, headers, "last-modified");
  copyIfPresent(response.headers, headers, "cache-control");

  const payload = await response.arrayBuffer();
  return new NextResponse(payload, {
    status: response.status,
    headers,
  });
}
