import pytest_asyncio
from main import app
from database import get_db
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine
from fastapi.testclient import TestClient
import httpx
from sqlalchemy import delete,create_engine
from models import User,Base, Lot, Bid
from auth import create_token
from datetime import timedelta
from tasks import r

client=TestClient(app)

async def fetch(endpoint, method, cookies=None, data=None, json=False, jsondata=None):
    transport=httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1') as client:
        if method=='get':
            response=await client.get(endpoint, cookies=cookies if cookies else {})
            return response.status_code if not(json) else (response.status_code, response.json())
        elif method=='post':
            response=await client.post(endpoint, cookies=cookies if cookies else {}, data=data if data else {}, json=jsondata if jsondata else {})
            return response.status_code if not(json) else (response.status_code, response.json())
        elif method=='delete':
            response=await client.delete(endpoint, cookies=cookies if cookies else {})
            return response.status_code if not(json) else (response.status_code, response.json())

engine=create_async_engine('sqlite+aiosqlite:///test_auction.db')
sync_engine=create_engine('sqlite:///test_auction.db')
TestSession=sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) #type:ignore
Base.metadata.create_all(sync_engine)

async def get_overr_db():
    async with TestSession() as db: #type:ignore
        try:
            yield db
        finally:
            await db.close()

app.dependency_overrides[get_db]=get_overr_db

@pytest_asyncio.fixture
async def db():
    async with TestSession() as db: #type:ignore
        try:
            yield db
        finally:
            await db.close()

@pytest_asyncio.fixture(autouse=True)
async def clean_db(db):
    try:
        await db.execute(delete(User))
        await db.execute(delete(Lot))
        await db.execute(delete(Bid))
        await db.commit()
    finally:
        await db.close()

@pytest_asyncio.fixture(autouse=True)
async def clean_redis():
    yield
    if r:
        await r.connection_pool.disconnect()

async def test_reg():
    response=await fetch('/reg','post',data={'name':'test','password':'123'})
    assert response==303

async def test_wrong_reg():
    await fetch('/reg','post',data={'name':'test','password':'123'})
    response=await fetch('/reg','post',data={'name':'test','password':'1234'})
    assert response==409

async def test_login():
    await fetch('/reg','post',data={'name':'test','password':'123'})
    response=await fetch('/login','post',data={'name':'test','password':'123'})
    assert response==303

async def test_wrong_login():
    await fetch('/reg','post',data={'name':'test','password':'123'})
    response=await fetch('/login','post',data={'name':'test','password':'1234'})
    assert response==401

async def test_health():
    response=await fetch('/health','get')
    assert response==200 #type:ignore

async def test_add_lot():
    await fetch('/reg','post',data={'name':'test','password':'123'})
    response=await fetch('/lots','post', jsondata={'title':'test','price':'100','ends_at':'2026-12-31T21:20','contact':'123'}, cookies={'access_token':create_token('test',timedelta(hours=1))})
    assert response==200

async def test_delete_lot():
    await fetch('/reg','post',data={'name':'test','password':'123'})
    await fetch('/lots','post', jsondata={'title':'test','price':'100','ends_at':'2026-12-31T21:20','contact':'123'}, cookies={'access_token':create_token('test',timedelta(hours=1))})
    response=await fetch('/lots/1', 'delete', cookies={'access_token':create_token('test',timedelta(hours=1))})
    assert response==200

async def test_delete_lot_not_found():
    await fetch('/reg','post',data={'name':'test','password':'123'})
    await fetch('/lots','post', jsondata={'title':'test','price':'100','ends_at':'2026-12-31T21:20','contact':'123'}, cookies={'access_token':create_token('test',timedelta(hours=1))})
    response=await fetch('/lots/100', 'delete', cookies={'access_token':create_token('test',timedelta(hours=1))})
    assert response==404

async def test_delete_lot_forbidden():
    await fetch('/reg','post',data={'name':'new','password':'123'})
    await fetch('/lots','post', jsondata={'title':'test','price':'100','ends_at':'2026-12-31T21:20','contact':'123'}, cookies={'access_token':create_token('test',timedelta(hours=1))})
    response=await fetch('/lots/1', 'delete', cookies={'access_token':create_token('new',timedelta(hours=1))})
    assert response==404

async def test_load_lots():
    await fetch('/reg','post',data={'name':'test','password':'123'})
    response=await fetch('/lots','get', cookies={'access_token':create_token('test', timedelta(hours=1))})
    assert response==200

async def test_load_win_lots():
    await fetch('/reg','post',data={'name':'test','password':'123'})
    response=await fetch('/winlots', 'get',cookies={'access_token':create_token('test', timedelta(hours=1))})
    assert response==200

async def test_bids():
    await fetch('/reg','post',data={'name':'test','password':'123'})
    await fetch('/reg','post',data={'name':'new','password':'123'})
    await fetch('/lots','post', jsondata={'title':'test','price':'100','ends_at':'2026-12-31T21:20','contact':'123'}, cookies={'access_token':create_token('test',timedelta(hours=1))})
    response=await fetch('/lots/1/bid', 'post', cookies={'access_token':create_token('test', timedelta(hours=1))}, jsondata={'amount':'1200'}, json=True)
    assert response==200

async def test_logout():
    response=await fetch('/logout','get')
    assert response==303