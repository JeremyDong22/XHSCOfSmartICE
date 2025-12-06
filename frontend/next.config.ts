// Next.js configuration
// Version: 1.3 - Correct allowedDevOrigins format for LAN access
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow LAN access during development
  allowedDevOrigins: [
    "http://192.168.1.51:3000",
    "http://192.168.1.51",
    "192.168.1.51:3000",
    "192.168.1.51",
  ],
};

export default nextConfig;
