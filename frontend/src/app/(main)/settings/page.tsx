"use client";

import { Typography, Card, Form, Input, Button, Switch, Divider, message } from "antd";

export default function SettingsPage() {
  const onFinish = () => {
    message.success("Settings saved");
  };

  return (
    <div>
      <Typography.Title level={4}>Settings</Typography.Title>
      <Card style={{ maxWidth: 600 }}>
        <Form layout="vertical" onFinish={onFinish}>
          <Typography.Title level={5}>Profile</Typography.Title>
          <Form.Item label="Full Name" name="full_name">
            <Input />
          </Form.Item>
          <Form.Item label="Email" name="email">
            <Input disabled />
          </Form.Item>
          <Divider />
          <Typography.Title level={5}>Notifications</Typography.Title>
          <Form.Item label="Email Notifications" name="email_notifications" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label="Interview Reminders" name="interview_reminders" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Button type="primary" htmlType="submit">
            Save Settings
          </Button>
        </Form>
      </Card>
    </div>
  );
}
