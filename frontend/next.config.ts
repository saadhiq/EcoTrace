import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export to `out/` for Firebase Hosting; data access goes through
  // Firebase client SDKs or the Cloud Run API, so no SSR is needed.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
