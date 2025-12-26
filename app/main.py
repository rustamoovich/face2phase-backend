from fastapi import FastAPI
from app.api import auth
from app.api.endpoints import events, media

app = FastAPI(title="Face2Phase API")

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(media.router)

@app.get("/")
async def root():
    return {"status": "ok"}

