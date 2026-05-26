/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["antd", "@ant-design/icons", "@ant-design/nextjs-registry"],
};

module.exports = nextConfig;
