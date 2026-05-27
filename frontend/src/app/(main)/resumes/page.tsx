"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Typography,
  Button,
  Table,
  Tag,
  Upload,
  Modal,
  Card,
  Descriptions,
  Progress,
  Space,
  message,
  Spin,
  Tabs,
  List,
  Empty,
  Tooltip,
} from "antd";
import {
  PlusOutlined,
  UploadOutlined,
  FileTextOutlined,
  RobotOutlined,
  BarChartOutlined,
  HistoryOutlined,
  ExperimentOutlined,
  DeleteOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import type { UploadFile } from "antd";
import type { ColumnsType } from "antd/es/table";
import api from "@/lib/api";

interface ResumeItem {
  id: string;
  title: string;
  source_type: string;
  status: string;
  ats_score: number | null;
  created_at: string;
  updated_at: string;
}

interface ResumeDetail {
  id: string;
  title: string;
  content: Record<string, unknown>;
  source_type: string;
  status: string;
  ats_score: number | null;
  created_at: string;
  updated_at: string;
  versions: {
    id: string;
    version_number: number;
    content: Record<string, unknown>;
    created_at: string;
  }[];
}

interface ATSScore {
  score: number;
  breakdown: Record<string, number>;
  missing_keywords: string[];
  suggestions: string[];
}

const sourceColors: Record<string, string> = {
  upload: "blue",
  generated: "green",
  manual: "default",
};
const statusColors: Record<string, string> = {
  draft: "default",
  active: "green",
  archived: "orange",
};

export default function ResumesPage() {
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<ResumeDetail | null>(null);
  const [atsResult, setAtsResult] = useState<ATSScore | null>(null);
  const [scoring, setScoring] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [scoreOpen, setScoreOpen] = useState(false);
  const [uploading, setUploading] = useState(false);

  const fetchResumes = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/api/resumes");
      setResumes(res.data);
    } catch {
      message.error("Failed to load resumes");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchResumes();
  }, [fetchResumes]);

  const handleUpload = async (file: UploadFile) => {
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file as unknown as Blob);
      const res = await api.post("/api/resumes/parse", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      message.success(
        `Parsed successfully (confidence: ${Math.round(res.data.confidence * 100)}%)`,
      );
      setUploadOpen(false);
      fetchResumes();
    } catch {
      message.error("Upload failed");
    }
    setUploading(false);
    return false; // Prevent default upload
  };

  const handleViewDetail = async (id: string) => {
    try {
      const res = await api.get(`/api/resumes/${id}`);
      setDetail(res.data);
      setDetailOpen(true);
    } catch {
      message.error("Failed to load resume detail");
    }
  };

  const handleScore = async (id: string) => {
    setScoring(true);
    setScoreOpen(true);
    try {
      const res = await api.post("/api/resumes/score", { resume_id: id });
      setAtsResult(res.data);
    } catch {
      message.error("Scoring failed");
    }
    setScoring(false);
  };

  const columns: ColumnsType<ResumeItem> = [
    {
      title: "Title",
      dataIndex: "title",
      key: "title",
      render: (t: string, r: ResumeItem) => (
        <Space>
          {r.source_type === "generated" ? <RobotOutlined /> : <FileTextOutlined />}
          <a onClick={() => handleViewDetail(r.id)}>{t}</a>
        </Space>
      ),
    },
    {
      title: "Source",
      dataIndex: "source_type",
      key: "source",
      render: (s: string) => <Tag color={sourceColors[s] || "default"}>{s}</Tag>,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (s: string) => <Tag color={statusColors[s] || "default"}>{s}</Tag>,
    },
    {
      title: "ATS Score",
      dataIndex: "ats_score",
      key: "ats_score",
      render: (v: number | null, r: ResumeItem) =>
        v != null ? (
          <Tooltip title={`${v}/100`}>
            <Progress
              type="circle"
              size={32}
              percent={v}
              strokeColor={v >= 80 ? "#52c41a" : v >= 60 ? "#faad14" : "#ff4d4f"}
            />
          </Tooltip>
        ) : (
          <Button size="small" onClick={() => handleScore(r.id)}>
            Score
          </Button>
        ),
    },
    {
      title: "Updated",
      dataIndex: "updated_at",
      key: "updated",
      render: (d: string) => new Date(d).toLocaleDateString(),
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: unknown, r: ResumeItem) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => handleViewDetail(r.id)}>
            View
          </Button>
          <Button size="small" icon={<BarChartOutlined />} onClick={() => handleScore(r.id)}>
            Score
          </Button>
        </Space>
      ),
    },
  ];

  const scoreColor = (s: number) => (s >= 80 ? "#52c41a" : s >= 60 ? "#faad14" : "#ff4d4f");

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          My Resumes
        </Typography.Title>
        <Space>
          <Button icon={<PlusOutlined />} onClick={() => setUploadOpen(true)}>
            Upload Resume
          </Button>
        </Space>
      </div>

      <Table<ResumeItem>
        columns={columns}
        dataSource={resumes}
        rowKey="id"
        loading={loading}
        locale={{ emptyText: <Empty description="No resumes yet. Upload or generate one!" /> }}
      />

      {/* Upload Modal */}
      <Modal
        title="Upload Resume"
        open={uploadOpen}
        onCancel={() => setUploadOpen(false)}
        footer={null}
      >
        <Upload.Dragger
          accept=".pdf,.docx,.doc,.txt"
          customRequest={({ file }) => handleUpload(file as UploadFile)}
          showUploadList={false}
        >
          <p className="ant-upload-drag-icon">
            <UploadOutlined style={{ fontSize: 48, color: "#1677ff" }} />
          </p>
          <p>Click or drag a file to upload</p>
          <p style={{ color: "#888" }}>Supports PDF, DOCX, TXT</p>
        </Upload.Dragger>
        {uploading && <Spin style={{ display: "block", marginTop: 16 }} />}
      </Modal>

      {/* Detail Modal */}
      <Modal
        title={detail?.title || "Resume Detail"}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        width={800}
        footer={null}
      >
        {detail && (
          <Tabs
            items={[
              {
                key: "content",
                label: "Content",
                children: (
                  <Card>
                    {detail.content && typeof detail.content === "object" && (
                      <>
                        {detail.content.full_name && (
                          <Descriptions column={2} size="small" bordered>
                            <Descriptions.Item label="Name">
                              {String(detail.content.full_name)}
                            </Descriptions.Item>
                            <Descriptions.Item label="Email">
                              {String(detail.content.email || "-")}
                            </Descriptions.Item>
                            <Descriptions.Item label="Phone">
                              {String(detail.content.phone || "-")}
                            </Descriptions.Item>
                            <Descriptions.Item label="Location">
                              {String(detail.content.location || "-")}
                            </Descriptions.Item>
                          </Descriptions>
                        )}
                        {detail.content.summary && (
                          <Card size="small" title="Summary" style={{ marginTop: 12 }}>
                            {String(detail.content.summary)}
                          </Card>
                        )}
                        {Array.isArray(detail.content.skills) &&
                          detail.content.skills.length > 0 && (
                            <Card size="small" title="Skills" style={{ marginTop: 12 }}>
                              <Space wrap>
                                {(detail.content.skills as string[]).map((s: string) => (
                                  <Tag key={s} color="blue">
                                    {s}
                                  </Tag>
                                ))}
                              </Space>
                            </Card>
                          )}
                        {Array.isArray(detail.content.experience) &&
                          detail.content.experience.length > 0 && (
                            <Card size="small" title="Experience" style={{ marginTop: 12 }}>
                              {(detail.content.experience as Array<Record<string, unknown>>).map(
                                (exp, i) => (
                                  <Card key={i} size="small" style={{ marginBottom: 8 }}>
                                    <Typography.Text strong>
                                      {String(exp.title || "")}
                                    </Typography.Text>
                                    {" at "}
                                    <Typography.Text>{String(exp.company || "")}</Typography.Text>
                                    {Array.isArray(exp.highlights) && exp.highlights.length > 0 && (
                                      <ul style={{ marginTop: 4 }}>
                                        {(exp.highlights as string[]).map((h, j) => (
                                          <li key={j}>{h}</li>
                                        ))}
                                      </ul>
                                    )}
                                  </Card>
                                ),
                              )}
                            </Card>
                          )}
                      </>
                    )}
                  </Card>
                ),
              },
              {
                key: "versions",
                label: (
                  <span>
                    <HistoryOutlined /> Versions
                  </span>
                ),
                children: (
                  <List
                    dataSource={detail.versions || []}
                    renderItem={(v) => (
                      <List.Item>
                        <List.Item.Meta
                          title={`Version ${v.version_number}`}
                          description={new Date(v.created_at).toLocaleString()}
                        />
                      </List.Item>
                    )}
                    locale={{ emptyText: "No versions" }}
                  />
                ),
              },
            ]}
          />
        )}
      </Modal>

      {/* ATS Score Modal */}
      <Modal
        title="ATS Score Analysis"
        open={scoreOpen}
        onCancel={() => {
          setScoreOpen(false);
          setAtsResult(null);
        }}
        footer={null}
      >
        {scoring ? (
          <Spin />
        ) : (
          atsResult && (
            <div>
              <div style={{ textAlign: "center", marginBottom: 24 }}>
                <Progress
                  type="dashboard"
                  percent={atsResult.score}
                  strokeColor={scoreColor(atsResult.score)}
                  format={() => (
                    <span
                      style={{ fontSize: 28, fontWeight: 700, color: scoreColor(atsResult.score) }}
                    >
                      {atsResult.score}
                    </span>
                  )}
                />
              </div>
              <Card size="small" title="Category Breakdown">
                {Object.entries(atsResult.breakdown).map(([cat, score]) => (
                  <div key={cat} style={{ marginBottom: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <Typography.Text>{cat}</Typography.Text>
                      <Typography.Text>{Math.round(score as number)}</Typography.Text>
                    </div>
                    <Progress
                      percent={Math.round(score as number)}
                      showInfo={false}
                      size="small"
                      strokeColor={scoreColor(score as number)}
                    />
                  </div>
                ))}
              </Card>
              {atsResult.missing_keywords.length > 0 && (
                <Card size="small" title="Missing Keywords" style={{ marginTop: 12 }}>
                  <Space wrap>
                    {atsResult.missing_keywords.map((k) => (
                      <Tag key={k} color="red">
                        {k}
                      </Tag>
                    ))}
                  </Space>
                </Card>
              )}
              {atsResult.suggestions.length > 0 && (
                <Card size="small" title="Suggestions" style={{ marginTop: 12 }}>
                  <ul style={{ paddingLeft: 20 }}>
                    {atsResult.suggestions.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>
          )
        )}
      </Modal>
    </div>
  );
}
