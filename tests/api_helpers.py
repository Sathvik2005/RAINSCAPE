import asyncio
import httpx


def request(app, method, url, *, params=None):
    async def run():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, url, params=params)
    return asyncio.run(run())
