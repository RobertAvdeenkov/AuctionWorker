from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse, FileResponse,RedirectResponse
from fastapi import Depends,Cookie,Form,HTTPException,Body,WebSocket
from database import get_db
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,text,desc
from models import User,Lot, Bid,Message
from logger import logger
from auth import create_token,get_by_token
from datetime import timedelta,datetime
import redis.asyncio as redis
import os
import aio_pika as pika
import json
from connetions import ConnectionManager
from prometheus_client import Counter,Gauge

router=APIRouter()
REDIS_URL=os.getenv('REDIS_URL')
if REDIS_URL:r=redis.from_url(REDIS_URL, decode_responses=True)
else: r=redis.Redis(decode_responses=True)

connection=None
channel=None
manager=ConnectionManager()
LOTS_COUNTER=Counter('lots_counter','Created lots counter')
ACTIVE_LOTS_COUNTER=Gauge('active_lots_counter','Active lots counter')

@router.on_event('startup')
async def startup():
    global connection,channel
    connection=await pika.connect_robust(os.getenv('RABBITMQ_URL',None))
    channel=await connection.channel()

@router.get('/')
async def login():
    return FileResponse('templates/login.html')

@router.get('/register')
async def register():
    return FileResponse('templates/register.html')

@router.get('/mainpage')
async def mainpage():
    return FileResponse('templates/mainpage.html')

@router.get('/mail')
async def mail():
    return FileResponse('templates/messages.html')

@router.websocket('/ws/lots')
async def web_lost(websocket:WebSocket, access_token=Cookie(), db:AsyncSession=Depends(get_db)):
    await get_by_token(access_token,db)
    await manager.connect(websocket)
    while True:
        try:
            await websocket.receive_text()
        except:
            await manager.disconnect(websocket)

@router.post('/reg')
async def reg(db:AsyncSession=Depends(get_db), name=Form(), password=Form()):
    result=(await db.execute(select(User).filter(User.name==name))).first()
    if result: raise HTTPException(409,'Такой пользователь уже есть!')
    target=User(name=name, password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())
    db.add(target)
    await db.commit()
    logger.info(f'New user: {name}')
    return RedirectResponse('/',status_code=303)

@router.post('/login')
async def log(db:AsyncSession=Depends(get_db), name=Form(), password=Form()):
    result=(await db.execute(select(User).filter(User.name==name))).first()
    if not(result): raise HTTPException(401,'Неправильный логин или пароль!')
    user=result[0]
    if not(bcrypt.checkpw(password.encode(), user.password.encode())): 
        raise HTTPException(401,'Неправильный логин или пароль!')
    response=RedirectResponse('/mainpage',status_code=303)
    refresh=create_token(name, timedelta(days=30))
    response.set_cookie('access_token', create_token(name, timedelta(minutes=60)),path='/')
    response.set_cookie('refresh_token', refresh, max_age=3600*24*30, path='/')
    user.refresh_token=refresh
    await db.commit()
    return response

@router.post('/refresh')
async def refresh(refresh_token=Cookie(), db:AsyncSession=Depends(get_db)):
    user=await get_by_token(refresh_token,db)
    if not(user.refresh_token==refresh_token): return JSONResponse({'message':'Неправильный токен'},status_code=401)
    response=JSONResponse({'status':'ok'})
    response.set_cookie('access_token',create_token(user.name, timedelta(hours=1)),path='/')
    return response

@router.get('/logout')
async def logout():
    response=RedirectResponse('/',status_code=303)
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')
    return response

@router.post('/lots')
async def add_lot(data=Body(), access_token=Cookie(), db:AsyncSession=Depends(get_db)):
    user=await get_by_token(access_token,db)
    if datetime.strptime(data['ends_at'].replace('T',' '),"%Y-%m-%d %H:%M")<datetime.now():
        raise HTTPException(400,'Дата должна быть позже настоящей!')
    target=Lot(title=data['title'], user_id=user.id, start_price=int(data['price']), current_price=int(data['price']),ends_at=datetime.strptime(data['ends_at'].replace('T',' '), "%Y-%m-%d %H:%M"), contact=data['contact'])
    db.add(target)
    await db.commit()
    await r.flushdb()
    LOTS_COUNTER.inc()

@router.get('/lots')
async def get_lots(access_token=Cookie(), db:AsyncSession=Depends(get_db)):
    user=await get_by_token(access_token,db)
    data=await r.get(f'{user.name}:lots')
    if data: return {'lots':json.loads(data)}
    lots=(await db.execute(text(f'''
    SELECT 
        lots.id AS li,
        lots.title AS lt,
        lots.current_price AS cp,
        lots.ends_at AS en,
        lots.contact AS c,
        bids.by AS leader,
        bids.price AS max_price,
        lots.user_id
    FROM lots
    LEFT JOIN bids ON bids.lot_id = lots.id
    WHERE lots.ends_at > CURRENT_TIMESTAMP
    AND (bids.price IS NULL OR bids.price = (
        SELECT MAX(price) FROM bids WHERE lot_id = lots.id
    ))
    ORDER BY lots.ends_at DESC
    '''))).all()
    all_lots=[]
    if lots:
        for i in lots:
            try: all_lots.append({'id':i[0], 'title':i[1],'current_price':i[2],'ends_at':i[3].strftime("%Y-%m-%d %H:%M"), 'leader':i[5], 'contact':i[4], 'is_owner':1 if i[-1]==user.id else 0})
            except Exception as e: break
    ACTIVE_LOTS_COUNTER.set(len(all_lots))
    await r.setex(f'{user.name}:lots',60, json.dumps(all_lots))
    return {'lots':all_lots}

@router.post('/lots/{id}/bid')
async def bid_add(id:int, access_token=Cookie(), db:AsyncSession=Depends(get_db), data=Body()):
    user=await get_by_token(access_token,db)
    result=(await db.execute(text(f'''
    select lots.id, lots.current_price, MAX(bids.by), MAX(bids.price), lots.ends_at, lots.title, bids.lot_id
    from lots
    full outer JOIN bids ON lots.id=bids.lot_id
    where lots.id={id}
    group by lots.id, bids.lot_id
    '''))).first()
    if not(result): raise HTTPException(404,'Такого лота нет!')
    date=result[4]
    if date<datetime.now():raise HTTPException(403,'Аукцион закончился')
    new_price=int(data['amount'])
    if new_price>2147483646:raise HTTPException(400,'Достигнута максимальная сумма ставки')
    if new_price-int(result[1])<10:raise HTTPException(400,'Минимальная ставка: 10 единиц')
    if not(result[3]): 
        if result[1]>new_price:
            raise HTTPException(400,'Ставка должна быть выше текущей')
    elif result[3]>new_price:raise HTTPException(400,'Ставка должна быть выше текущей')
    target=Bid(price=int(data['amount']),by=user.name, lot_id=int(id), user_id=user.id)
    db.add(target)
    await manager.broadcast({'price':int(data['amount']), 'by':user.name, 'lot_id':int(id), 'user_id':user.id, 'type':'bid'}, redis=r)
    await db.execute(text(f'UPDATE lots set current_price={new_price} where id={id}'))
    if date-datetime.now()<timedelta(minutes=1): await db.execute(text(f'UPDATE lots SET ends_at = datetime(\'now\', \'+1 minute\') WHERE id = {id}'))
    await db.commit()
    if result[2]!=user.name: await channel.default_exchange.publish(routing_key='main_queue', message=pika.Message(json.dumps({'user':result[2], 'title':result[5], 'id':result[0], 'sent':False}).encode())) #type:ignore
    await r.flushdb()

@router.get('/messages')
async def messages(access_token=Cookie(), db:AsyncSession=Depends(get_db)):
    user=await get_by_token(access_token,db)
    data=await r.get(f'{user.name}:messages')
    if data: return {'messages':json.loads(data)}
    result=(await db.execute(select(Message).filter(Message.user_id==user.id).order_by(desc(Message.created_at)))).all()
    all_messages=[]
    for i in result:
        message=i[0]
        all_messages.append({'status':message.status, 'text':message.text,'created_at':message.created_at.strftime('%Y.%M.%d %H:%M')})
    await r.setex(f'{user.name}:messages',60,json.dumps(all_messages))
    return {'messages':all_messages}

@router.delete('/lots/{id}')
async def delete_lot(id:int, access_token=Cookie(), db:AsyncSession=Depends(get_db)):
    user=await get_by_token(access_token,db)
    result=(await db.execute(select(Lot).filter(Lot.id==id))).first()
    if not(result): raise HTTPException(404,'Такого лота нет')
    lot=result[0]
    if lot.user_id!=user.id: raise HTTPException(403,'Вы не владелец лота!')
    await db.delete(lot)
    await db.commit()
    await r.flushdb()

@router.get('/winlot')
async def winlots():
    return FileResponse('templates/wininglots.html')

@router.get('/winlots')
async def load_winlots(access_token=Cookie(), db:AsyncSession=Depends(get_db)):
    user=await get_by_token(access_token,db)
    data=await r.get(f'{user.name}:win')
    if data: return {'lots':json.loads(data)}
    result=(await db.execute(text(f'''
    select lots.id, lots.title, lots.contact, bids.by, MAX(bids.price), MAX(lots.contact)
    from lots
    INNER join bids ON bids.lot_id=lots.id
    where lots.ends_at<CURRENT_TIMESTAMP and bids.by=:user_name
    group by lots.id, lots.title, lots.contact, bids.by
    '''), {'user_name':user.name})).all()
    all_winlots=[]
    for i in result:
            try: all_winlots.append({'title':i[1], 'contact':i[-1]})
            except Exception as e: break
    await r.setex(f'{user.name}:win',60, json.dumps(all_winlots))
    return {'lots':all_winlots}