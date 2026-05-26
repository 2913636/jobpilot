"use client";

import React from "react";
import { Skeleton as AntSkeleton, Card, Space } from "antd";

interface SkeletonCardProps {
  count?: number;
}

export function SkeletonCard({ count = 3 }: SkeletonCardProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i} style={{ marginBottom: 16 }}>
          <AntSkeleton active avatar paragraph={{ rows: 2 }} />
        </Card>
      ))}
    </>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div style={{ padding: 24 }}>
      <AntSkeleton active title paragraph={{ rows: 1 }} style={{ marginBottom: 24 }} />
      {Array.from({ length: rows }).map((_, i) => (
        <AntSkeleton key={i} active paragraph={{ rows: 1 }} style={{ marginBottom: 12 }} />
      ))}
    </div>
  );
}

export function SkeletonDashboard() {
  return (
    <div style={{ padding: 24 }}>
      <AntSkeleton active title paragraph={{ rows: 1 }} style={{ marginBottom: 24 }} />
      <Space style={{ width: "100%" }} direction="vertical" size="middle">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <AntSkeleton active paragraph={{ rows: 2 }} />
          </Card>
        ))}
      </Space>
    </div>
  );
}

export function SkeletonInterview() {
  return (
    <div style={{ padding: 24 }}>
      <Space style={{ width: "100%" }} direction="vertical" size="large">
        <Card style={{ minHeight: 300, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <AntSkeleton.Avatar active size={120} shape="circle" />
        </Card>
        <Card>
          <AntSkeleton active paragraph={{ rows: 4 }} />
        </Card>
      </Space>
    </div>
  );
}
