/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["antd", "@ant-design/icons", "@ant-design/nextjs-registry"],

  // ISR + 图片优化
  images: {
    formats: ["image/avif", "image/webp"],
    deviceSizes: [375, 640, 768, 1024, 1280],
    imageSizes: [16, 32, 48, 64, 96],
  },

  // 压缩
  compress: true,

  // 安全 headers
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },

  // ESLint 10.x 与 Next.js 14 built-in lint 不兼容，构建时跳过
  eslint: { ignoreDuringBuilds: true },

  // 实验性 ISR
  experimental: {
    optimizeCss: true,
    optimizePackageImports: ["antd", "@ant-design/icons"],
  },
};

module.exports = nextConfig;
