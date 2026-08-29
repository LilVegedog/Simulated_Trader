import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

/** Dev proxy target: the real FastAPI backend by default, or the mock via API_PROXY_TARGET. */
const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

/**
 * Static export served by FastAPI. In dev only, proxy /api to the backend;
 * compression is off there because gzipping the SSE stream buffers it.
 */
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  agentRules: false,
  ...(isDev && {
    compress: false,
    rewrites: async () => [
      { source: "/api/:path*", destination: `${apiTarget}/api/:path*` },
    ],
  }),
};

export default nextConfig;
