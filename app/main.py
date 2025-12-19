from fastapi import FastAPI
from app.api import auth

app = FastAPI(title="Face2Phase API")

app.include_router(auth.router)

@app.get("/")
async def root():
    return {"status": "ok"}

