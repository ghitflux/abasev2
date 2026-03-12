import { proxyRequestForPath } from "@/app/api/_proxy";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

async function proxyRequest(request: Request, { params }: RouteContext) {
  const { path } = await params;
  return proxyRequestForPath(request, path);
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PATCH = proxyRequest;
export const PUT = proxyRequest;
export const DELETE = proxyRequest;
