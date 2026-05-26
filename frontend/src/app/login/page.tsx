"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Form, Input, Button, Card, Typography, message } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { useAppStore } from "@/store";
import api from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { setToken, setUser } = useAppStore();

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      const res = await api.post("/api/users/login", values);
      setToken(res.data.access_token);
      setUser(res.data.user);
      message.success("Login successful");
      router.push("/dashboard");
    } catch {
      message.error("Login failed");
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
          JobPilot Login
        </Typography.Title>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item name="email" rules={[{ required: true, message: "Email required" }]}>
            <Input prefix={<UserOutlined />} placeholder="Email" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "Password required" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="Password" size="large" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block size="large">
              Login
            </Button>
          </Form.Item>
          <div style={{ textAlign: "center" }}>
            <Button type="link" onClick={() => router.push("/register")}>
              Create an account
            </Button>
          </div>
        </Form>
      </Card>
    </div>
  );
}
