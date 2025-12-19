---
alwaysApply: true
---

Project: Face2Phase
Stack: FastAPI, PostgreSQL + pgvector, SQLAlchemy (Async), Docker.
Goal: Biometric photo sharing platform.

Rules:
- Always use async/await for database calls.
- Use Pydantic v2 for schemas.
- Do not remove comments explaining complex logic.
- When generating SQL models, remember we use pgvector(512).
- Keep code modular: separate models, schemas, and routers.