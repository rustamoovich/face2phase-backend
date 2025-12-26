from fastapi import FastAPI
from app.api.endpoints import auth, events, media, biometrics

app = FastAPI(title="Face2Phase API")

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(media.router)
app.include_router(biometrics.router)
app.include_router(biometrics.feed_router)

@app.get("/")
async def root():
    return {"status": "ok"}

