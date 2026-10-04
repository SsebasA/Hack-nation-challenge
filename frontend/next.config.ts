import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The SPARK Lab API allows both localhost:3000 and 127.0.0.1:3000; let the dev server be opened from either.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
