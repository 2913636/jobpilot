"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Typography,
  Card,
  Button,
  Space,
  Tag,
  Progress,
  Row,
  Col,
  Statistic,
  Modal,
  Spin,
  Empty,
  message,
  List,
} from "antd";
import {
  VideoCameraOutlined,
  PlayCircleOutlined,
  SoundOutlined,
  TrophyOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";
import api from "@/lib/api";

interface InterviewSession {
  id: string;
  room_name: string;
  status: string;
  transcript: { speaker: string; text: string; timestamp: string }[] | null;
  emotions: { timestamp: string; confidence_score: number }[] | null;
  started_at: string | null;
  ended_at: string | null;
}

interface Report {
  id: string;
  overall_score: number;
  scores: Record<string, number>;
  strengths: string[];
  weaknesses: string[];
  detailed_feedback: string;
  recommendations: { type: string; title: string; url: string }[];
  question_results: { question_index: number; score: number; feedback: string }[];
}

export default function InterviewPage() {
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(false);
  const [currentQ, setCurrentQ] = useState("");
  const [answer, setAnswer] = useState("");
  const [caption, setCaption] = useState<string[]>(["点击开始面试..."]);
  const [reportOpen, setReportOpen] = useState(false);
  const [emotion, setEmotion] = useState({ smile: 0, eye: 0, confidence: 50 });
  const wsRef = useRef<WebSocket | null>(null);

  const startInterview = async () => {
    setLoading(true);
    try {
      const res = await api.post("/api/interviews/start", {});
      setSession(res.data);
      setActive(true);
      setCaption(["面试已开始！"]);
      // 获取 AI 问候语
      addCaption("AI面试官: 你好！欢迎参加今天的面试。请简单介绍一下你自己。");
    } catch {
      message.error("启动面试失败");
    }
    setLoading(false);
  };

  const submitAnswer = async () => {
    if (!answer.trim() || !session) return;
    addCaption(`你: ${answer}`);
    const text = answer;
    setAnswer("");
    try {
      const res = await api.post(`/api/interviews/${session.id}/answer`, { text });
      if (res.data.next_question) {
        setTimeout(() => addCaption(`AI面试官: ${res.data.next_question}`), 1000);
        setCurrentQ(res.data.next_question);
      }
      if (res.data.is_complete) {
        setActive(false);
        addCaption("面试结束！正在生成报告...");
        generateReport();
      }
    } catch {
      message.error("提交失败");
    }
  };

  const generateReport = async () => {
    if (!session) return;
    try {
      const res = await api.post(`/api/interviews/${session.id}/report`);
      setReport(res.data);
      setReportOpen(true);
    } catch {
      message.error("报告生成失败");
    }
  };

  const addCaption = (text: string) => {
    setCaption((prev) => [...prev.slice(-20), text]);
  };

  // 连接 WebSocket 获取实时表情分析
  useEffect(() => {
    if (!active || !session) return;

    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost";
    const wsUrl = apiBase.replace(/^http/, "ws") + `/api/interviews/ws/${session.id}`;
    let fallbackInterval: ReturnType<typeof setInterval> | null = null;

    const connectWs = () => {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          // 发送模拟 landmarks（实际使用 MediaPipe）
          const sendLandmarks = () => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({
                landmarks: Array.from({ length: 468 }, () => ({
                  x: Math.random(), y: Math.random(), z: Math.random() * 0.01,
                })),
              }));
            }
          };
          sendLandmarks();
          fallbackInterval = setInterval(sendLandmarks, 2000);
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "emotion_result" && msg.data) {
              setEmotion({
                smile: msg.data.smile_ratio ?? Math.random() * 0.4 + 0.4,
                eye: msg.data.eye_contact ?? Math.random() * 0.3 + 0.6,
                confidence: msg.data.confidence ?? Math.random() * 20 + 65,
              });
            }
          } catch {
            // ignore parse errors
          }
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch {
        // WebSocket unavailable, use fallback
      }
    };

    connectWs();

    // Fallback: 若 WebSocket 未连接成功，使用模拟数据
    const fallbackTimer = setTimeout(() => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        fallbackInterval = setInterval(() => {
          setEmotion({
            smile: Math.random() * 0.4 + 0.4,
            eye: Math.random() * 0.3 + 0.6,
            confidence: Math.random() * 20 + 65,
          });
        }, 2000);
      }
    }, 3000);

    return () => {
      if (fallbackInterval) clearInterval(fallbackInterval);
      clearTimeout(fallbackTimer);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [active, session]);

  const scoreColor = (s: number) => (s >= 80 ? "#52c41a" : s >= 60 ? "#faad14" : "#ff4d4f");

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
          AI 模拟面试
        </Typography.Title>
        <Space>
          {!active && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={startInterview}
              loading={loading}
              size="large"
            >
              开始面试
            </Button>
          )}
          {report && (
            <Button icon={<TrophyOutlined />} onClick={() => setReportOpen(true)}>
              查看报告 ({report.overall_score}分)
            </Button>
          )}
        </Space>
      </div>

      <Row gutter={16}>
        {/* 视频区域 */}
        <Col xs={24} md={14}>
          <Card
            title={
              <Space>
                <VideoCameraOutlined /> 面试窗口
              </Space>
            }
            style={{ minHeight: 400, background: "#1a1a2e", borderRadius: 12 }}
            styles={{
              body: { padding: 0 },
              header: { color: "#fff", borderBottom: "1px solid #333" },
            }}
          >
            <div
              style={{
                height: 350,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
              }}
            >
              {active ? (
                <>
                  <div
                    style={{
                      width: 120,
                      height: 120,
                      borderRadius: "50%",
                      background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginBottom: 16,
                      fontSize: 48,
                    }}
                  >
                    🤖
                  </div>
                  <Typography.Text style={{ color: "#ccc", fontSize: 16 }}>
                    AI 面试官
                  </Typography.Text>
                  {currentQ && (
                    <Typography.Text
                      style={{ color: "#fff", marginTop: 12, textAlign: "center", maxWidth: 400 }}
                    >
                      &ldquo;{currentQ}&rdquo;
                    </Typography.Text>
                  )}
                </>
              ) : (
                <Empty
                  description="点击「开始面试」启动 AI 模拟面试"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              )}
            </div>
          </Card>
        </Col>

        {/* 实时字幕 + 指标 */}
        <Col xs={24} md={10}>
          <Card
            title={
              <Space>
                <SoundOutlined /> 实时字幕
              </Space>
            }
            size="small"
            style={{ height: 250, overflow: "auto", marginBottom: 16 }}
          >
            {caption.map((line, i) => (
              <div
                key={i}
                style={{
                  padding: "4px 8px",
                  marginBottom: 4,
                  borderRadius: 6,
                  background: line.startsWith("你:")
                    ? "#e6f7ff"
                    : line.startsWith("AI")
                      ? "#f6ffed"
                      : "#fafafa",
                  fontSize: 13,
                }}
              >
                {line}
              </div>
            ))}
          </Card>
          <Card title="实时指标" size="small">
            <Row gutter={8}>
              <Col span={8}>
                <Statistic
                  title="微笑率"
                  value={Math.round(emotion.smile * 100)}
                  suffix="%"
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="视线接触"
                  value={Math.round(emotion.eye * 100)}
                  suffix="%"
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="自信度"
                  value={Math.round(emotion.confidence)}
                  valueStyle={{ fontSize: 18, color: scoreColor(emotion.confidence) }}
                />
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      {/* 回答输入 */}
      {active && (
        <Card style={{ marginTop: 16 }}>
          <div style={{ display: "flex", gap: 12 }}>
            <input
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitAnswer()}
              placeholder="输入你的回答..."
              style={{
                flex: 1,
                padding: "10px 14px",
                fontSize: 15,
                borderRadius: 8,
                border: "1px solid #d9d9d9",
              }}
            />
            <Button
              type="primary"
              onClick={submitAnswer}
              size="large"
              icon={<CheckCircleOutlined />}
            >
              提交
            </Button>
          </div>
        </Card>
      )}

      {/* 报告弹窗 */}
      <Modal
        title="面试评估报告"
        open={reportOpen}
        onCancel={() => setReportOpen(false)}
        width={800}
        footer={null}
      >
        {report ? (
          <div>
            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <Progress
                type="dashboard"
                percent={report.overall_score}
                strokeColor={scoreColor(report.overall_score)}
                format={() => (
                  <span
                    style={{
                      fontSize: 28,
                      fontWeight: 700,
                      color: scoreColor(report.overall_score),
                    }}
                  >
                    {report.overall_score}
                  </span>
                )}
              />
            </div>

            <Row gutter={16} style={{ marginBottom: 16 }}>
              {Object.entries(report.scores || {}).map(([k, v]) => (
                <Col span={Math.floor(24 / Object.keys(report.scores).length)} key={k}>
                  <Card size="small">
                    <Statistic
                      title={k}
                      value={Math.round(v as number)}
                      suffix="分"
                      valueStyle={{ color: scoreColor(v as number), fontSize: 22 }}
                    />
                  </Card>
                </Col>
              ))}
            </Row>

            <Row gutter={16}>
              <Col span={12}>
                <Card size="small" title="强项">
                  {(report.strengths || []).map((s, i) => (
                    <Tag key={i} color="green" style={{ marginBottom: 4 }}>
                      {s}
                    </Tag>
                  ))}
                </Card>
              </Col>
              <Col span={12}>
                <Card size="small" title="弱项">
                  {(report.weaknesses || []).map((s, i) => (
                    <Tag key={i} color="red" style={{ marginBottom: 4 }}>
                      {s}
                    </Tag>
                  ))}
                </Card>
              </Col>
            </Row>

            <Card size="small" title="反馈" style={{ marginTop: 12 }}>
              <Typography.Paragraph>{report.detailed_feedback}</Typography.Paragraph>
            </Card>

            {report.recommendations && report.recommendations.length > 0 && (
              <Card size="small" title="推荐资源" style={{ marginTop: 12 }}>
                <List
                  dataSource={report.recommendations}
                  renderItem={(r: { type: string; title: string; url: string }) => (
                    <List.Item>
                      <Tag>{r.type}</Tag>
                      {r.url ? (
                        <a href={r.url} target="_blank">
                          {r.title}
                        </a>
                      ) : (
                        r.title
                      )}
                    </List.Item>
                  )}
                />
              </Card>
            )}
          </div>
        ) : (
          <Spin />
        )}
      </Modal>
    </div>
  );
}
