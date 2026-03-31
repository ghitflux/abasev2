import path from "node:path";
import type { NextConfig } from "next";

const workspaceRoot = path.join(__dirname, "../..");
const distDir = process.env.NEXT_DIST_DIR?.trim() || ".next";

const nextConfig: NextConfig = {
  distDir,
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
  turbopack:
    process.env.NODE_ENV === "test"
      ? undefined
      : {
          root: workspaceRoot,
        },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
    ],
  },
};

export default nextConfig;
