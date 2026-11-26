import aio_pika as pika
from fastapi import FastAPI
import os
from logger import logger
import asyncio
import json
from database import SessionLocal
from sqlalchemy import select
from models import Message,User
from aiogram import Bot
from datetime import datetime

app=FastAPI()
TOKEN=os.getenv('TOKEN')
if TOKEN:
    bot=Bot(token=TOKEN)

connection=None
channel=None

background_tasks = set()

def spawn(coro):
    t = asyncio.create_task(coro)
    background_tasks.add(t)
    t.add_done_callback(background_tasks.discard)
    return t

async def main():
    queue=await channel.declare_queue('main_queue') #type:ignore
    await channel.declare_queue('retry_queue', arguments={'x-message-ttl': 30000, 'x-dead-letter-exchange': '', 'x-dead-letter-routing-key': 'sites'}) #type:ignore
    await channel.declare_queue('dlx_queue') #type:ignore

    async def callback(message:pika.IncomingMessage):
        async with message.process():
            body=json.loads(message.body.decode())
            async with SessionLocal() as db: #type:ignore
                if body['user']:
                    user=(await db.execute(select(User).filter(User.name==body['user']))).first()[0] #type:ignore
                    if not(body['sent']):
                        target=Message(text=f'Вашу ставку в {body['title']} перебили!', user_id=user.id, status='success', created_at=datetime.now())
                        db.add(target)
                        await db.commit()
                        await db.refresh(target)

                    try:
                        logger.info('TG message started')
                        if user.tg_id and user.distribution and TOKEN:
                            await bot.send_message(chat_id=int(user.tg_id), text=f'Вашу ставку в {body['title']} перебили!')
                            logger.info('TG message was sent')
                    except:
                        logger.info('Retry message started')
                        await channel.default_exchange.publish(message=pika.Message(json.dumps({'title':body['title'], 'user':body['user'], 'sent':True, 'id':target.id, 'tg':user.tg_id}).encode()), routing_key='retry') #type:ignore

    await queue.consume(callback) #type:ignore

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        return

@app.on_event('startup')
async def startup():
    global channel,connection
    connection=await pika.connect_robust(os.getenv('RABBITMQ_URL',None))
    channel=await connection.channel()
    spawn(main())
    logger.info('Main worker Started')

@app.get('/')
async def root():
    return {'status':'ok'}
