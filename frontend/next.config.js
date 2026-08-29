/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "a.espncdn.com",
        pathname: "/i/teamlogos/**",
      },
    ],
  },
  async rewrites() {
    const backendUrl =
      process.env.INTERNAL_BACKEND_URL ||
      (process.env.NODE_ENV === "development"
        ? "http://localhost:8000"
        : "http://backend:8000");
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

