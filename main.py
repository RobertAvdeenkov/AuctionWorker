from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from database import engine
from models import Base
from prometheus_client import Histogram, Counter, make_asgi_app
import time
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from tasks import router, r
from logger import logger

app=FastAPI()
metric=make_asgi_app()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_methods=['GET','POST','DELETE'],
    allow_headers=['*'],
    allow_origins=['http://127.0.0.1:8000']
)

app.mount('/metrics',metric)
app.mount("/templates", StaticFiles(directory="templates"), name="templates")
app.include_router(router)

COUNTER=Counter('HTTP_COUNTER', 'http counter', ['method','endpoint','status'])
REQUEST_LATENCY=Histogram('HTTP_LATENCY','http latency', ['method','endpoint'])

@app.on_event('startup')
async def startup():
    async with engine.begin() as con:
        await con.run_sync(Base.metadata.create_all)
        logger.info('Main app started')

@app.middleware('http')
async def rate_limit(request:Request,call_next):
    if request.method in ("POST","DELETE") and not(request.url.path.startswith('/lots') and request.url.path.endswith('/bid')):
        client=request.scope.get('client')
        f=request.headers.get('X-Forwarded-For')
        ip=f.split(',')[0].strip() if f else (client[0] if client else 'unknown')
        count=await r.get(f'{ip}:{request.url.path}')
        count=int(count)+1 if count else 1
        if count>3:
            return JSONResponse({'detail':'to many responses'},status_code=429)
        await r.setex(f'{ip}:{request.url.path}',60,str(count))
    response=await call_next(request)
    return response

@app.middleware('http')
async def metrics(request:Request, call_next):
    start=time.time()
    response=await call_next(request)
    final_time=time.time() - start

    COUNTER.labels(method=request.method, endpoint=request.url.path, status=response.status_code).inc()
    REQUEST_LATENCY.labels(method=request.method, endpoint=request.url.path).observe(final_time)

    return response

@app.get('/health')
async def health():
    return {'status':'ok'}