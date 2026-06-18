/** @type {import('next').NextConfig} */
const nextConfig = {
  // Output standalone build for Docker (smaller image, no node_modules needed)
  output: 'standalone',
  experimental: {
    typedRoutes: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: false,
  },
}

module.exports = nextConfig