"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Form, Input, Button, Card, Typography, message } from "antd";
import { UserOutlined, LockOutlined, MailOutlined } from "@ant-design/icons";
import api from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();

  const onFinish = async (values: { email: string; password: string; full_name: string }) => {
    try {
      await api.post("/api/users/register", values);
      message.success("Registration successful");
      router.push("/login");
    } catch {
      message.error("Registration failed");
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "#f0f2f5",
      }}
    >
      <Card style={{ width: 400 }}>
        <Typography.Title level={3} style={{ textAlign: "center" }}>
          Create Account
        </Typography.Title>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item name="full_name" rules={[{ required: true, message: "Name required" }]}>
            <Input prefix={<UserOutlined />} placeholder="Full Name" size="large" />
          </Form.Item>
          <Form.Item name="email" rules={[{ required: true, message: "Email required" }]}>
            <Input prefix={<MailOutlined />} placeholder="Email" size="large" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, min: 6, message: "Min 6 characters" }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="Password" size="large" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block size="large">
              Register
            </Button>
          </Form.Item>
          <div style={{ textAlign: "center" }}>
            <Button type="link" onClick={() => router.push("/login")}>
              Already have an account? Login
            </Button>
          </div>
        </Form>
      </Card>
    </div>
  );
}
