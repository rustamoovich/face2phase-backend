from fastapi import FastAPI
from app.api.endpoints import auth, events, media, biometrics, organizations, photographer_access

app = FastAPI(
    title="Face2Phase API",
    description="AI-powered event photo discovery platform with organizations and photographer management",
    version="2.0.0"
)

# Auth & Users
app.include_router(auth.router)

# Organizations
app.include_router(organizations.router)

# Photographer Access (before events to avoid path conflicts)
app.include_router(photographer_access.router)

# Events
app.include_router(events.router)

# Media
app.include_router(media.router)

# Biometrics & Feed
app.include_router(biometrics.router)
app.include_router(biometrics.feed_router)

@app.get("/")
async def root():
    return {"status": "ok"}

