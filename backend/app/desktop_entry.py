import uvicorn
import os


def _resolve_backend_port() -> int:
    """Return the backend port from SCYTHE_BACKEND_PORT when provided."""
    configured_port = os.getenv("SCYTHE_BACKEND_PORT", "3001")
    try:
        return int(configured_port)
    except ValueError as error:
        raise ValueError(
            f"SCYTHE_BACKEND_PORT must be an integer, got {configured_port!r}"
        ) from error


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=_resolve_backend_port(),
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
