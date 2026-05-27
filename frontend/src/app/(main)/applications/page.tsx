"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Typography,
  Card,
  Tag,
  Space,
  Button,
  Modal,
  Input,
  Select,
  Statistic,
  Row,
  Col,
  Timeline,
  Empty,
  Spin,
  message,
} from "antd";
import {
  PlusOutlined,
  DashboardOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import api from "@/lib/api";

interface AppItem {
  id: string;
  title: string | null;
  company: string | null;
  status: string;
  notes: string;
  source_url: string | null;
  timeline: { status: string; timestamp: string; note: string }[] | null;
  created_at: string;
  updated_at: string;
}

const STATUS_FLOW = [
  { key: "draft", label: "草稿", color: "default" },
  { key: "submitted", label: "已投递", color: "blue" },
  { key: "screening", label: "筛选中", color: "orange" },
  { key: "interview", label: "面试", color: "purple" },
  { key: "offer", label: "Offer", color: "green" },
  { key: "accepted", label: "已接受", color: "cyan" },
  { key: "hired", label: "已入职", color: "geekblue" },
  { key: "rejected", label: "已拒绝", color: "red" },
  { key: "withdrawn", label: "已撤回", color: "default" },
  { key: "declined", label: "已婉拒", color: "default" },
];

const statusColors: Record<string, string> = Object.fromEntries(
  STATUS_FLOW.map((s) => [s.key, s.color]),
);
const statusLabels: Record<string, string> = Object.fromEntries(
  STATUS_FLOW.map((s) => [s.key, s.label]),
);

export default function ApplicationsPage() {
  const [apps, setApps] = useState<AppItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<"kanban" | "list">("kanban");
  const [createOpen, setCreateOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedApp, setSelectedApp] = useState<AppItem | null>(null);
  const [newApp, setNewApp] = useState({ company: "", title: "", notes: "", source_url: "" });
  const [stats, setStats] = useState<Record<string, number>>({});

  const fetchApps = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/api/applications?page_size=100");
      setApps(res.data.items);
      const sRes = await api.get("/api/applications/stats");
      setStats(sRes.data);
    } catch {
      setApps([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchApps();
  }, [fetchApps]);

  const handleCreate = async () => {
    if (!newApp.company && !newApp.title) return;
    try {
      await api.post("/api/applications", {
        company: newApp.company,
        title: newApp.title,
        notes: newApp.notes,
        source_url: newApp.source_url,
      });
      message.success("申请已创建");
      setCreateOpen(false);
      setNewApp({ company: "", title: "", notes: "", source_url: "" });
      fetchApps();
    } catch {
      message.error("创建失败");
    }
  };

  const handleStatusChange = async (appId: string, newStatus: string) => {
    try {
      await api.patch(`/api/applications/${appId}`, { status: newStatus });
      message.success(`状态已更新为 ${statusLabels[newStatus] || newStatus}`);
      fetchApps();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "状态更新失败");
    }
  };

  const kanbanColumns = ["draft", "submitted", "screening", "interview", "offer", "accepted"];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 24,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <Typography.Title level={4} style={{ margin: 0 }}>
          申请看板
        </Typography.Title>
        <Space>
          <Button
            icon={<DashboardOutlined />}
            type={viewMode === "kanban" ? "primary" : "default"}
            onClick={() => setViewMode("kanban")}
          >
            看板
          </Button>
          <Button
            icon={<UnorderedListOutlined />}
            type={viewMode === "list" ? "primary" : "default"}
            onClick={() => setViewMode("list")}
          >
            列表
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            新建申请
          </Button>
        </Space>
      </div>

      {/* 统计 */}
      <Row gutter={12} style={{ marginBottom: 24 }}>
        {STATUS_FLOW.slice(0, 8).map((s) => (
          <Col key={s.key} xs={12} sm={6} md={3}>
            <Card size="small">
              <Statistic
                title={s.label}
                value={stats[s.key] || 0}
                valueStyle={{
                  color:
                    s.color === "red" ? "#ff4d4f" : s.color === "green" ? "#52c41a" : "#1677ff",
                  fontSize: 20,
                }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {loading ? (
        <Spin size="large" style={{ display: "block", margin: "60px auto" }} />
      ) : viewMode === "kanban" ? (
        /* 看板视图 */
        <div style={{ display: "flex", gap: 16, overflowX: "auto", paddingBottom: 16 }}>
          {kanbanColumns.map((col) => {
            const colApps = apps.filter((a) => a.status === col);
            return (
              <div
                key={col}
                style={{
                  minWidth: 240,
                  maxWidth: 300,
                  flex: "1 0 240px",
                  background: "#fafafa",
                  borderRadius: 8,
                  padding: 12,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                  <Tag color={statusColors[col]}>{statusLabels[col]}</Tag>
                  <span style={{ color: "#888" }}>{colApps.length}</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, minHeight: 200 }}>
                  {colApps.map((app) => (
                    <Card
                      key={app.id}
                      size="small"
                      hoverable
                      onClick={() => {
                        setSelectedApp(app);
                        setDetailOpen(true);
                      }}
                      extra={
                        <Select
                          size="small"
                          value={app.status}
                          style={{ width: 100 }}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(val) => handleStatusChange(app.id, val)}
                          options={STATUS_FLOW.map((s) => ({ label: s.label, value: s.key }))}
                        />
                      }
                    >
                      <Typography.Text strong>{app.title || "无标题"}</Typography.Text>
                      <br />
                      <Typography.Text type="secondary">{app.company || "-"}</Typography.Text>
                      <br />
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {new Date(app.updated_at).toLocaleDateString()}
                      </Typography.Text>
                    </Card>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* 列表视图 */
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {apps.length === 0 ? (
            <Empty description="暂无申请记录" />
          ) : (
            apps.map((app) => (
              <Card
                key={app.id}
                size="small"
                hoverable
                onClick={() => {
                  setSelectedApp(app);
                  setDetailOpen(true);
                }}
              >
                <div
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
                >
                  <Space>
                    <Tag color={statusColors[app.status]}>
                      {statusLabels[app.status] || app.status}
                    </Tag>
                    <Typography.Text strong>{app.title || "无标题"}</Typography.Text>
                    {app.company && (
                      <Typography.Text type="secondary">@{app.company}</Typography.Text>
                    )}
                  </Space>
                  <span style={{ fontSize: 12, color: "#888" }}>
                    {new Date(app.updated_at).toLocaleDateString()}
                  </span>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* 新建弹窗 */}
      <Modal
        title="新建申请"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate}
        okText="创建"
      >
        <Input
          placeholder="公司名称"
          value={newApp.company}
          onChange={(e) => setNewApp((p) => ({ ...p, company: e.target.value }))}
          style={{ marginBottom: 8 }}
        />
        <Input
          placeholder="职位名称"
          value={newApp.title}
          onChange={(e) => setNewApp((p) => ({ ...p, title: e.target.value }))}
          style={{ marginBottom: 8 }}
        />
        <Input
          placeholder="职位链接（可选）"
          value={newApp.source_url}
          onChange={(e) => setNewApp((p) => ({ ...p, source_url: e.target.value }))}
          style={{ marginBottom: 8 }}
        />
        <Input.TextArea
          placeholder="备注"
          value={newApp.notes}
          onChange={(e) => setNewApp((p) => ({ ...p, notes: e.target.value }))}
          rows={3}
        />
      </Modal>

      {/* 详情弹窗 */}
      <Modal
        title="申请详情"
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={600}
      >
        {selectedApp && (
          <div>
            <Typography.Title level={5}>{selectedApp.title || "无标题"}</Typography.Title>
            <Space>
              <Tag color={statusColors[selectedApp.status]}>
                {statusLabels[selectedApp.status] || selectedApp.status}
              </Tag>
              {selectedApp.company && <span>@{selectedApp.company}</span>}
            </Space>
            {selectedApp.notes && (
              <Card size="small" title="备注" style={{ marginTop: 12 }}>
                {selectedApp.notes}
              </Card>
            )}
            {selectedApp.source_url && (
              <div style={{ marginTop: 12 }}>
                <a href={selectedApp.source_url} target="_blank" rel="noreferrer">
                  查看职位链接
                </a>
              </div>
            )}
            {selectedApp.timeline && selectedApp.timeline.length > 0 && (
              <Card size="small" title="状态时间线" style={{ marginTop: 12 }}>
                <Timeline
                  items={selectedApp.timeline.map((t) => ({
                    color:
                      statusColors[t.status] === "green"
                        ? "green"
                        : statusColors[t.status] === "red"
                          ? "red"
                          : "blue",
                    children: (
                      <div>
                        <Tag color={statusColors[t.status]}>
                          {statusLabels[t.status] || t.status}
                        </Tag>
                        <span style={{ fontSize: 12, color: "#888", marginLeft: 8 }}>
                          {new Date(t.timestamp).toLocaleString()}
                        </span>
                        {t.note && <div style={{ fontSize: 12, marginTop: 2 }}>{t.note}</div>}
                      </div>
                    ),
                  }))}
                />
              </Card>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
