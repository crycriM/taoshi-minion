import argparse
import uvicorn
from fastapi import FastAPI
from .router import router

app = FastAPI(title="Taoshi Signal Bridge", version="1.0.0")
app.include_router(router)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run(
        "signal_bridge.main:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )
