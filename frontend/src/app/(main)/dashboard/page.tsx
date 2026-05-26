"use client";

import { Typography, Card, Row, Col, Statistic } from "antd";
import {
  FileTextOutlined,
  SearchOutlined,
  FormOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";

export default function DashboardPage() {
  return (
    <div>
      <Typography.Title level={4}>Dashboard</Typography.Title>
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic title="Resumes" value={12} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Jobs Matched" value={48} prefix={<SearchOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Applications" value={8} prefix={<FormOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Interviews" value={3} prefix={<CheckCircleOutlined />} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
