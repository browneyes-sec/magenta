"""Allow running the API server with: python -m magenta.api"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "magenta.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
