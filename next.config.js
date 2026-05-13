/** @type {import('next').NextConfig} */
const API_ORIGIN = process.env.CLIPFORGE_API_ORIGIN || 'http://127.0.0.1:8010';
const DIST_DIR = process.env.NODE_ENV === 'development' ? '.next-dev' : '.next';

const nextConfig = {
  reactStrictMode: true,
  distDir: DIST_DIR,
  async rewrites() {
    return [
      {
        source: '/api/agent/:path*',
        destination: `${API_ORIGIN}/api/agent/:path*`,
      },
      {
        source: '/api/config/:path*',
        destination: `${API_ORIGIN}/api/config/:path*`,
      },
      {
        source: '/output/:path*',
        destination: `${API_ORIGIN}/output/:path*`,
      },
      {
        source: '/downloads/:path*',
        destination: `${API_ORIGIN}/downloads/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
          { key: 'Cross-Origin-Embedder-Policy', value: 'require-corp' },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
