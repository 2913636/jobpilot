# Dependency License Audit

Generated: 2026-05-27

## License Summary

| License | Count | Risk |
|---------|-------|------|
| MIT | 16 | Compatible |
| Apache 2.0 | 13 | Compatible |
| BSD | 6 | Compatible |
| AGPL | 1 | **Review Required** |

## Backend (Python)

### MIT License

| Package | Version | Usage |
|---------|---------|-------|
| fastapi | >=0.110.0 | Web framework |
| uvicorn[standard] | >=0.29.0 | ASGI server |
| pydantic | >=2.0.0 | Data validation |
| sqlalchemy[asyncio] | >=2.0.29 | ORM |
| alembic | >=1.13.0 | Migrations |
| redis | >=5.0.0 | Cache client |
| pyjwt | >=2.8.0 | JWT auth |
| python-docx | >=1.1.0 | Resume parsing (DOCX) |
| pytest | >=8.0.0 | Testing |
| temporalio | >=1.6.0 | Workflow engine |
| anthropic | >=0.30.0 | AI model inference |
| minio | >=7.2.0 | Object storage client |

### Apache 2.0 License

| Package | Version | Usage |
|---------|---------|-------|
| asyncpg | >=0.29.0 | PostgreSQL driver |
| elasticsearch[async] | >=8.14.0 | Search engine client |
| pymilvus | >=2.4.0 | Vector database client |
| neo4j | >=5.21.0 | Graph database client |
| bcrypt | >=4.1.0 | Password hashing |
| python-multipart | >=0.0.9 | Form parsing |
| sentence-transformers | >=2.7.0 | Text embeddings |
| xgboost | >=2.0.0 | ML model |
| pytesseract | >=0.3.10 | OCR |
| nats-py | >=0.0.5 | Message queue |
| aiokafka | >=0.10.0 | Event streaming |
| livekit-api | >=0.7.0 | WebRTC |
| pytest-asyncio | >=0.23.0 | Testing |

### BSD License

| Package | Version | Usage |
|---------|---------|-------|
| httpx | >=0.27.0 | HTTP client |
| numpy | >=1.26.0 | Numerical computing |
| scrapy | >=2.11.0 | Web crawling |
| scrapy-playwright | >=0.0.40 | Headless browser |
| fakeredis[lua] | >=2.21.0 | Testing mock |
| Pillow | >=10.0.0 | Image processing |
| pdfplumber | >=0.11.0 | PDF text extraction |

### AGPL License — RESOLVED

| Package | Version | Usage |
|---------|---------|-------|
| ~~PyMuPDF~~ | ~~>=1.24.0~~ | ~~PDF resume parsing~~ → Replaced by pdfplumber (MIT) |

## Frontend (Node.js)

### MIT License

| Package | Version | Usage |
|---------|---------|-------|
| next | 14.2.5 | React framework |
| react | ^18.3.1 | UI library |
| react-dom | ^18.3.1 | DOM renderer |
| antd | ^5.20.0 | UI components |
| @ant-design/icons | ^5.4.0 | Icon library |
| axios | ^1.7.3 | HTTP client |
| zustand | ^4.5.4 | State management |
| tailwindcss | ^3.4.9 | CSS framework |
| autoprefixer | ^10.4.20 | PostCSS plugin |
| postcss | ^8.4.41 | CSS processor |
| @eslint/js | ^10.0.1 | Linter |
| eslint | ^10.4.0 | Linter |

### Apache 2.0 License

| Package | Version | Usage |
|---------|---------|-------|
| typescript | ^5.5.4 | Type checking |
| typescript-eslint | ^8.60.0 | ESLint TS plugin |
| @ant-design/nextjs-registry | ^1.0.0 | Antd SSR integration |

## Conclusion

All dependencies are compatible with the MIT license used by JobPilot. No license conflicts detected.

- **PyMuPDF (AGPL)**: Replaced with `pdfplumber` (MIT) in Round 4 polish. All MIT, Apache 2.0, and BSD dependencies are permissively licensed and compatible with commercial use.
