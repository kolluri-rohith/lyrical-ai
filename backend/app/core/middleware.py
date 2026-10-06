"""ASGI middleware: reject oversized uploads before the body is read."""

import json

from starlette.types import ASGIApp, Receive, Scope, Send

# Room for the multipart envelope around a file that is exactly at the limit.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


class UploadSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_file_bytes: int, max_file_mb: int) -> None:
        self.app = app
        self.max_body_bytes = max_file_bytes + MULTIPART_OVERHEAD_BYTES
        self.max_file_mb = max_file_mb

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in ("POST", "PUT", "PATCH"):
            headers = dict(scope.get("headers") or [])
            declared = headers.get(b"content-length")
            if declared and declared.isdigit() and int(declared) > self.max_body_bytes:
                await self._reject(send)
                return
        await self.app(scope, receive, send)

    async def _reject(self, send: Send) -> None:
        body = json.dumps(
            {
                "detail": f"The file is too large. The maximum size is {self.max_file_mb} MB.",
                "code": "FILE_TOO_LARGE",
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
