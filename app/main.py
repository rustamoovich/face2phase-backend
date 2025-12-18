from fastapi import FastAPI

app = FastAPI(title="Face2Phase API")

@app.get("/")
async def root():
    return {"status": "ok"}

