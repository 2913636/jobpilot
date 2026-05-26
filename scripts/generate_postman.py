#!/usr/bin/env python3
"""从 FastAPI OpenAPI schema 生成 Postman Collection。

Usage: python scripts/generate_postman.py > docs/postman_collection.json
"""

import json
import sys

OUTPUT_PATH = "docs/postman_collection.json"

# 微服务 OpenAPI 端点
SERVICES = {
    "User Service": "http://localhost:8001/openapi.json",
    "Resume Service": "http://localhost:8002/openapi.json",
    "Match Service": "http://localhost:8003/openapi.json",
    "Apply Service": "http://localhost:8004/openapi.json",
    "Interview Service": "http://localhost:8005/openapi.json",
    "Agent Service": "http://localhost:8006/openapi.json",
}


def build_collection():
    collection = {
        "info": {
            "name": "JobPilot API",
            "description": "Auto-generated Postman Collection from FastAPI OpenAPI schemas",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [],
        "variable": [
            {"key": "base_url", "value": "http://localhost:8001"},
            {"key": "token", "value": "{{JWT_TOKEN}}"},
        ],
    }

    for svc_name, svc_url in SERVICES.items():
        folder = {
            "name": svc_name,
            "item": [
                {
                    "name": f"Import OpenAPI: {svc_url}",
                    "request": {
                        "method": "GET",
                        "url": {"raw": svc_url, "host": [svc_url]},
                        "description": f"Import this URL into Postman to get the full {svc_name} collection.",
                    },
                }
            ],
        }
        collection["item"].append(folder)

    return collection


if __name__ == "__main__":
    collection = build_collection()
    print(json.dumps(collection, indent=2))
