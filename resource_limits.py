"""Bound expensive public work without queuing liveness behind that work."""
import threading
from starlette.responses import JSONResponse

EXPENSIVE_PATHS = frozenset({
    "/api/analyze", "/api/research/peers", "/api/research/filing-review",
    "/api/research/filing-snapshot", "/api/research/model-baseline",
    "/api/research/forecast", "/api/research/export-model", "/api/download-pdf",
})
DOCUMENT_PATHS = frozenset({
    "/api/research/filing-review", "/api/research/export-model", "/api/download-pdf",
})


class ExpensiveRequestLimit:
    def __init__(self, app, max_active=4, max_documents=1):
        self.app = app
        self.active = threading.BoundedSemaphore(max_active)
        self.documents = threading.BoundedSemaphore(max_documents)

    async def __call__(self, scope, receive, send):
        path = scope.get("path")
        if scope.get("type") != "http" or path not in EXPENSIVE_PATHS:
            return await self.app(scope, receive, send)
        slots = [self.active] + ([self.documents] if path in DOCUMENT_PATHS else [])
        acquired = []
        try:
            for slot in slots:
                if not slot.acquire(blocking=False):
                    return await JSONResponse(
                        {"detail": "The analysis service is busy. Please try again shortly."},
                        status_code=503,
                        headers={"Retry-After": "5", "Cache-Control": "no-store",
                                 "X-StatementIQ-Error-Code": "service_busy"},
                    )(scope, receive, send)
                acquired.append(slot)
            await self.app(scope, receive, send)
        finally:
            for slot in reversed(acquired):
                slot.release()
