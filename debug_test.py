import sys
from fastapi import FastAPI
from cutctx.proxy.routes.memory import create_memory_router
app = FastAPI()
app.include_router(create_memory_router())
print([getattr(route, 'path', '') for route in app.routes])
