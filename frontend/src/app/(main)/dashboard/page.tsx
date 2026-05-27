"use client";

import { useCallback, useEffect, useState } from "react";
import { Typography, Card, Row, Col, Statistic, Spin, Alert, List, Tag } from "antd";
import {
  FileTextOutlined,
  SearchOutlined,
  FormOutlined,
  CheckCircleOutlined,
  UserOutlined,
  BarChartOutlined,
} from "@ant-design/icons";
import api from "@/lib/api";

interface DashboardData {
  resumes: number;
  jobs: number;
  applications: number;
  interviews: number;
  appStats: Record<string, number>;
}

const STATUS_COLORS: Record<string, string> = {
  draft: "default",
  submitted: "blue",
  screening: "geekblue",
  reviewing: "purple",
  interview: "orange",
  offer: "green",
  accepted: "cyan",
  hired: "green",
  rejected: "red",
  withdrawn: "default",
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [appStatsRes, resumesRes, jobsRes] = await Promise.allSettled([
        api.get("/api/applications/stats"),
        api.get("/api/resumes?page_size=1"),
        api.get("/api/matches/jobs/search?page=1&page_size=1"),
      ]);

      const appStats: Record<string, number> =
        appStatsRes.status === "fulfilled" ? appStatsRes.value.data : {};

      const resumeCount =
        resumesRes.status === "fulfilled"
          ? resumesRes.value.data?.total ?? resumesRes.value.data?.length ?? 0
          : 0;

      const jobCount =
        jobsRes.status === "fulfilled"
          ? jobsRes.value.data?.total ?? jobsRes.value.data?.items?.length ?? 0
          : 0;

      const totalApps = Object.values(appStats).reduce((sum, v) => sum + v, 0);

      setData({
        resumes: resumeCount,
        jobs: jobCount,
        applications: totalApps,
        interviews: appStats["interview"] ?? 0,
        appStats,
      });
    } catch {
      setError("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <Typography.Title level={4}>Dashboard</Typography.Title>
        <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />
      </div>
    );
  }

  const topStats = [
    { title: "Resumes", value: data?.resumes ?? 0, icon: <FileTextOutlined />, color: "#1677ff" },
    { title: "Jobs Matched", value: data?.jobs ?? 0, icon: <SearchOutlined />, color: "#52c41a" },
    { title: "Applications", value: data?.applications ?? 0, icon: <FormOutlined />, color: "#fa8c16" },
    { title: "Interviews", value: data?.interviews ?? 0, icon: <CheckCircleOutlined />, color: "#722ed1" },
  ];

  return (
    <div>
      <Typography.Title level={4}>Dashboard</Typography.Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        {topStats.map((stat) => (
          <Col xs={24} sm={12} md={6} key={stat.title} style={{ marginBottom: 16 }}>
            <Card>
              <Statistic
                title={stat.title}
                value={stat.value}
                prefix={stat.icon}
                valueStyle={{ color: stat.color }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {data && Object.keys(data.appStats).length > 0 && (
        <Card title={<span><BarChartOutlined /> Application Status Breakdown</span>} style={{ maxWidth: 600 }}>
          <List
            size="small"
            dataSource={Object.entries(data.appStats)}
            renderItem={([status, count]) => (
              <List.Item
                extra={
                  <Tag color={STATUS_COLORS[status] ?? "default"}>
                    {status}
                  </Tag>
                }
              >
                <List.Item.Meta title={count} />
              </List.Item>
            )}
          />
        </Card>
      )}
    </div>
  );
}
