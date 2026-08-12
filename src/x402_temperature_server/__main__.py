from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("x402_temperature_server.app:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    main()

