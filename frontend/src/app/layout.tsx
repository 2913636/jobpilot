import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import ErrorBoundary from "@/components/ErrorBoundary";
import "./globals.css";

export const metadata: Metadata = {
  title: "JobPilot",
  description: "AI-powered job matching platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AntdRegistry>
          <ErrorBoundary>{children}</ErrorBoundary>
        </AntdRegistry>
      </body>
    </html>
  );
}
