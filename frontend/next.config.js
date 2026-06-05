/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // In Docker dev: frontend container calls backend container by service name
  // Browser calls: http://localhost:3000/api/... → proxied to backend:8000
  async rewrites() {
    const backendUrl = process.env.BACKEND_INTERNAL_URL || "http://backend:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/screenshots/:path*",
        destination: `${backendUrl}/screenshots/:path*`,
      },
      {
        source: "/reports/:path*",
        destination: `${backendUrl}/reports/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
