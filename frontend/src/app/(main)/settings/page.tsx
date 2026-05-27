"use client";

import { useCallback, useEffect, useState } from "react";
import { Typography, Card, Form, Input, Button, Switch, Divider, message, Spin, Alert } from "antd";
import api from "@/lib/api";

export default function SettingsPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/api/users/profile");
      const data = res.data;
      form.setFieldsValue({
        full_name: data.full_name,
        email: data.email,
        location: data.location || "",
        summary: data.summary || "",
        skills: (data.skills || []).join(", "),
      });
    } catch {
      setError("Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const onFinish = async (values: Record<string, unknown>) => {
    setSaving(true);
    try {
      const skills = values.skills
        ? String(values.skills).split(",").map((s: string) => s.trim()).filter(Boolean)
        : [];
      await api.put("/api/users/profile", {
        full_name: values.full_name,
        location: values.location,
        summary: values.summary,
        skills,
      });
      message.success("Settings saved");
    } catch {
      message.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

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
        <Typography.Title level={4}>Settings</Typography.Title>
        <Alert type="error" message={error} showIcon />
      </div>
    );
  }

  return (
    <div>
      <Typography.Title level={4}>Settings</Typography.Title>
      <Card style={{ maxWidth: 600 }}>
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Typography.Title level={5}>Profile</Typography.Title>
          <Form.Item label="Full Name" name="full_name">
            <Input />
          </Form.Item>
          <Form.Item label="Email" name="email">
            <Input disabled />
          </Form.Item>
          <Form.Item label="Location" name="location">
            <Input placeholder="Beijing, Shanghai..." />
          </Form.Item>
          <Form.Item label="Summary" name="summary">
            <Input.TextArea rows={3} placeholder="Brief professional summary..." />
          </Form.Item>
          <Form.Item label="Skills (comma separated)" name="skills">
            <Input placeholder="Python, React, Docker..." />
          </Form.Item>
          <Divider />
          <Typography.Title level={5}>Notifications</Typography.Title>
          <Form.Item label="Email Notifications" name="email_notifications" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label="Interview Reminders" name="interview_reminders" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>
            Save Settings
          </Button>
        </Form>
      </Card>
    </div>
  );
}
