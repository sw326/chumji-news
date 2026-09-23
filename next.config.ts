import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return {
      // Keep old dated Git assets working; serve later graphs from durable data.
      beforeFiles: [
        { source: "/fresh-food/index.html", destination: "/api/price-artifacts/latest" },
      ],
      afterFiles: [],
      fallback: [
        { source: "/fresh-food/:date/index.html", destination: "/api/price-artifacts/:date" },
      ],
    };
  },
};

export default nextConfig;
