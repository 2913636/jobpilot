"use client";

import React, { useState, useCallback, useEffect } from "react";
import {
  Typography,
  Input,
  Card,
  Row,
  Col,
  Tag,
  Space,
  Button,
  Modal,
  Select,
  Progress,
  Spin,
  Empty,
  List,
  Divider,
  Statistic,
  Tabs,
} from "antd";
import {
  SearchOutlined,
  SwapOutlined,
  DollarOutlined,
  NodeIndexOutlined,
  EnvironmentOutlined,
  BankOutlined,
} from "@ant-design/icons";
import api from "@/lib/api";

interface Job {
  id: string;
  title: string;
  company: string;
  description: string;
  location: string | null;
  remote: boolean;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  skills: string[];
  experience_level: string | null;
  source: string;
  created_at: string;
}

interface CompareResult {
  report_markdown: string;
  dimensions: { name: string; scores: Record<string, number>; analysis: string }[];
  radar_data: Record<string, number[]>;
  job_names: string[];
}

interface CareerPath {
  path: {
    step: number;
    action: string;
    skills_to_acquire: string[];
    estimated_months: number;
    resources: string[];
  }[];
  total_months: number;
  alternative_roles: string[];
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [remoteOnly, setRemoteOnly] = useState<boolean | undefined>();
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [comparing, setComparing] = useState(false);
  const [careerOpen, setCareerOpen] = useState(false);
  const [careerResult, setCareerResult] = useState<CareerPath | null>(null);
  const [careerLoading, setCareerLoading] = useState(false);
  const [targetRole, setTargetRole] = useState("");

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (query) params.set("q", query);
      if (location) params.set("location", location);
      if (remoteOnly !== undefined) params.set("remote", String(remoteOnly));
      params.set("page", String(page));
      params.set("page_size", "20");
      const res = await api.get(`/api/matches/jobs/search?${params}`);
      setJobs(res.data.items);
      setTotal(res.data.total);
    } catch {
      // 服务不可用时静默降级
      setJobs([]);
    }
    setLoading(false);
  }, [query, location, remoteOnly, page]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const handleSearch = () => {
    setPage(1);
    fetchJobs();
  };

  const handleCompare = async () => {
    if (selected.length < 2) return;
    setComparing(true);
    setCompareOpen(true);
    try {
      const res = await api.post("/api/matches/match/compare", { job_ids: selected });
      setCompareResult(res.data);
    } catch {
      setCompareResult(null);
    }
    setComparing(false);
  };

  const handleCareerPath = async () => {
    if (!targetRole) return;
    setCareerLoading(true);
    setCareerOpen(true);
    try {
      const res = await api.get("/api/matches/career/path", {
        params: { from_skills: ["python", "javascript"], target_role: targetRole },
      });
      setCareerResult(res.data);
    } catch {
      setCareerResult(null);
    }
    setCareerLoading(false);
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id].slice(0, 5),
    );
  };

  const fmtSalary = (lo: number | null, hi: number | null, cur: string | null) => {
    if (!lo && !hi) return "薪资面议";
    const c = cur || "CNY";
    const fmt = (n: number) => (n >= 10000 ? `${(n / 10000).toFixed(0)}万` : `${n}`);
    if (lo && hi) return `${fmt(lo)}-${fmt(hi)} ${c}`;
    return `${lo ? fmt(lo) : fmt(hi!)} ${c}`;
  };

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
          职位搜索
        </Typography.Title>
        <Space>
          <Button icon={<SwapOutlined />} disabled={selected.length < 2} onClick={handleCompare}>
            对比 ({selected.length})
          </Button>
          <Button icon={<NodeIndexOutlined />} onClick={() => setCareerOpen(true)}>
            职业路径
          </Button>
        </Space>
      </div>

      {/* 搜索栏 */}
      <Row gutter={12} style={{ marginBottom: 24 }}>
        <Col xs={24} md={8}>
          <Input.Search
            placeholder="搜索职位/公司/技能..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onSearch={handleSearch}
            enterButton={<SearchOutlined />}
            size="large"
          />
        </Col>
        <Col xs={12} md={5}>
          <Input
            placeholder="地点"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            size="large"
            prefix={<EnvironmentOutlined />}
          />
        </Col>
        <Col xs={12} md={3}>
          <Select
            value={remoteOnly}
            onChange={setRemoteOnly}
            size="large"
            style={{ width: "100%" }}
            placeholder="远程"
            allowClear
            options={[
              { label: "全部", value: undefined },
              { label: "远程", value: true },
              { label: "现场", value: false },
            ]}
          />
        </Col>
        <Col xs={24} md={2}>
          <Button size="large" block onClick={handleSearch} type="primary">
            搜索
          </Button>
        </Col>
      </Row>

      {/* 职位卡片 */}
      {loading ? (
        <Spin size="large" style={{ display: "block", margin: "60px auto" }} />
      ) : (
        <List
          grid={{ gutter: 16, xs: 1, sm: 1, md: 2, lg: 2, xl: 2, xxl: 3 }}
          dataSource={jobs}
          locale={{ emptyText: <Empty description="暂无职位，试试修改搜索条件" /> }}
          pagination={{
            current: page,
            total,
            pageSize: 20,
            onChange: setPage,
            showTotal: (t) => `共 ${t} 个职位`,
          }}
          renderItem={(job: Job) => (
            <List.Item>
              <Card
                hoverable
                style={{ border: selected.includes(job.id) ? "2px solid #1677ff" : undefined }}
                onClick={() => toggleSelect(job.id)}
                actions={[
                  <Button
                    key="select"
                    type="link"
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleSelect(job.id);
                    }}
                  >
                    {selected.includes(job.id) ? "已选" : "选择对比"}
                  </Button>,
                ]}
              >
                <Typography.Title level={5} style={{ marginBottom: 4 }}>
                  {job.title}
                </Typography.Title>
                <Space style={{ marginBottom: 8 }}>
                  <BankOutlined /> {job.company}
                  {job.location && (
                    <>
                      <EnvironmentOutlined /> {job.location}
                    </>
                  )}
                  {job.remote && <Tag color="green">远程</Tag>}
                </Space>
                <div style={{ marginBottom: 8 }}>
                  <DollarOutlined />{" "}
                  {fmtSalary(job.salary_min, job.salary_max, job.salary_currency)}
                </div>
                <Space wrap>
                  {(job.skills || []).slice(0, 5).map((s) => (
                    <Tag key={s} color="blue">
                      {s}
                    </Tag>
                  ))}
                </Space>
                <Typography.Paragraph
                  ellipsis={{ rows: 2 }}
                  type="secondary"
                  style={{ marginTop: 8 }}
                >
                  {(job.description || "").slice(0, 200)}
                </Typography.Paragraph>
              </Card>
            </List.Item>
          )}
        />
      )}

      {/* 对比弹窗 */}
      <Modal
        title="岗位对比分析"
        open={compareOpen}
        onCancel={() => setCompareOpen(false)}
        width={900}
        footer={null}
      >
        {comparing ? (
          <Spin />
        ) : compareResult ? (
          <Tabs
            items={[
              {
                key: "report",
                label: "对比报告",
                children: (
                  <div
                    dangerouslySetInnerHTML={{
                      __html: compareResult.report_markdown.replace(/\n/g, "<br/>"),
                    }}
                    style={{ maxHeight: 500, overflow: "auto" }}
                  />
                ),
              },
              {
                key: "radar",
                label: "维度对比",
                children: (
                  <div>
                    {compareResult.dimensions.map((d) => (
                      <Card key={d.name} size="small" style={{ marginBottom: 8 }}>
                        <Typography.Text strong>{d.name}</Typography.Text>
                        <div style={{ marginTop: 8 }}>
                          {Object.entries(d.scores).map(([name, score]) => (
                            <div key={name} style={{ marginBottom: 4 }}>
                              <div style={{ display: "flex", justifyContent: "space-between" }}>
                                <span>{name}</span>
                                <span>{Math.round(score as number)}/10</span>
                              </div>
                              <Progress
                                percent={(score as number) * 10}
                                size="small"
                                showInfo={false}
                              />
                            </div>
                          ))}
                        </div>
                        <Typography.Paragraph type="secondary" style={{ marginTop: 4 }}>
                          {d.analysis}
                        </Typography.Paragraph>
                      </Card>
                    ))}
                  </div>
                ),
              },
            ]}
          />
        ) : (
          <Empty description="对比失败，请检查服务是否可用" />
        )}
      </Modal>

      {/* 职业路径弹窗 */}
      <Modal
        title="职业路径模拟"
        open={careerOpen}
        onCancel={() => setCareerOpen(false)}
        width={700}
        footer={null}
      >
        <Space style={{ marginBottom: 16 }}>
          <Input
            placeholder="目标角色 (如 senior software engineer)"
            value={targetRole}
            onChange={(e) => setTargetRole(e.target.value)}
            style={{ width: 300 }}
          />
          <Button
            type="primary"
            onClick={handleCareerPath}
            loading={careerLoading}
            icon={<NodeIndexOutlined />}
          >
            分析路径
          </Button>
        </Space>
        {careerResult && (
          <div>
            <Statistic title="预估总时长" value={careerResult.total_months} suffix="月" />
            <Divider />
            {careerResult.path.map((s) => (
              <Card key={s.step} size="small" style={{ marginBottom: 8 }}>
                <Typography.Text strong>
                  第 {s.step} 步：{s.action}
                </Typography.Text>
                <div style={{ marginTop: 4 }}>
                  {s.skills_to_acquire.map((sk) => (
                    <Tag key={sk} color="green">
                      {sk}
                    </Tag>
                  ))}
                  <Tag color="orange">~{s.estimated_months} 个月</Tag>
                </div>
              </Card>
            ))}
            {careerResult.alternative_roles.length > 0 && (
              <Card size="small" title="备选角色">
                <Space wrap>
                  {careerResult.alternative_roles.map((r) => (
                    <Tag key={r} color="purple">
                      {r}
                    </Tag>
                  ))}
                </Space>
              </Card>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
