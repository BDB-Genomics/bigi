import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  async rewrites() {
    return [
      {
        source: '/:owner/:repo',
        destination: '/api/index',
      },
    ]
  },
};

export default nextConfig;
