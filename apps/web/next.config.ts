import path from "node:path";
import type { NextConfig } from "next";

const workspaceRoot = path.join(__dirname, "../..");

const nextConfig: NextConfig = {
  turbopack: {
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
