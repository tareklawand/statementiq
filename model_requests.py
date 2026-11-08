"""Bound model request size before parsing JSON or fetching financial data."""
import asyncio
import time
from starlette.responses import JSONResponse


class ModelRequestLimit:
    def __init__(self, app, max_bytes=65536, max_body_seconds=15):
        self.app=app;self.max_bytes=max_bytes;self.max_body_seconds=max_body_seconds

    async def __call__(self,scope,receive,send):
        guarded=scope.get('type')=='http' and scope.get('method')=='POST' and scope.get('path') in {'/api/research/forecast','/api/research/export-model','/api/download-pdf'}
        if not guarded:return await self.app(scope,receive,send)
        chunks=[];total=0;deadline=time.monotonic()+self.max_body_seconds
        while True:
            try:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise asyncio.TimeoutError
                message=await asyncio.wait_for(receive(),timeout=remaining)
            except asyncio.TimeoutError:
                return await JSONResponse({'detail':'The request did not finish uploading. Please try again.'},status_code=408,
                    headers={'Cache-Control':'no-store'})(scope,receive,send)
            if message['type']=='http.disconnect':return
            chunk=message.get('body',b'');total+=len(chunk)
            if total>self.max_bytes:
                return await JSONResponse({'detail':'Model request exceeds the 64 KB limit.'},status_code=413)(scope,receive,send)
            chunks.append(chunk)
            if not message.get('more_body',False):break
        first=True
        async def replay():
            nonlocal first
            if first:
                first=False
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        return await self.app(scope,replay,send)
