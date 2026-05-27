"""Temporal Worker — 注册所有工作流并启动 worker loop。

Usage:
    python -m services.agent_service.worker

Cron schedules:
    - DailyScanWorkflow:  每天 08:00 UTC
    - BackupWorkflow:     每周日 03:00 UTC
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from temporalio.client import Client
from temporalio.worker import Worker

from services.agent_service.workflows.daily_scan import DailyScanWorkflow
from services.agent_service.workflows.application import ApplicationWorkflow
from services.agent_service.workflows.backup import BackupWorkflow

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "temporal:7233")
TASK_QUEUE = "jobpilot-task-queue"


async def register_cron_schedules(client: Client) -> None:
    """Register cron-triggered workflow schedules."""
    schedules = [
        {
            "id": "daily-scan-schedule",
            "workflow": "DailyScanWorkflow",
            "cron": "0 8 * * *",
            "description": "每天 08:00 UTC 扫描新职位并匹配通知",
        },
        {
            "id": "backup-schedule",
            "workflow": "BackupWorkflow",
            "cron": "0 3 * * 0",
            "description": "每周日 03:00 UTC 执行全量备份",
        },
    ]

    for sched in schedules:
        try:
            await client.create_schedule(
                sched["id"],
                schedule=temporalio.client.Schedule(
                    spec=temporalio.client.ScheduleSpec(
                        cron_expressions=[sched["cron"]],
                    ),
                    action=temporalio.client.ScheduleActionStartWorkflow(
                        sched["workflow"],
                        id=f"{sched['id']}-${{schedule_trigger_time}}",
                        task_queue=TASK_QUEUE,
                    ),
                ),
            )
            print(f"  ✅ {sched['id']}: {sched['workflow']} ({sched['cron']})")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  ♻️  {sched['id']}: already exists")
            else:
                print(f"  ⚠️  {sched['id']}: {e}")


async def main():
    print(f"Connecting to Temporal at {TEMPORAL_HOST}...")
    client = await Client.connect(TEMPORAL_HOST)

    print("Registering cron schedules...")
    await register_cron_schedules(client)

    print(f"Starting worker on task queue '{TASK_QUEUE}'...")
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DailyScanWorkflow, ApplicationWorkflow, BackupWorkflow],
    )

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
