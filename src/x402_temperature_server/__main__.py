from __future__ import annotations

import uvicorn
import os


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("x402_temperature_server.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
