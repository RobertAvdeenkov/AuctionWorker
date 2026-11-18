import aio_pika as pika
from fastapi import FastAPI
import os
from logger import logger
import asyncio
import json
from database import SessionLocal
from sqlalchemy import text

app=FastAPI()

connection=None
channel=None

background_tasks = set()

def spawn(coro):
    t = asyncio.create_task(coro)
    background_tasks.add(t)
    t.add_done_callback(background_tasks.discard)
    return t

async def main():
    queue=await channel.declare_queue('dlx_queue') #type:ignore
    await channel.declare_queue('retry_queue', arguments={'x-message-ttl': 30000, 'x-dead-letter-exchange': '', 'x-dead-letter-routing-key': 'sites'}) #type:ignore

    async def callback(message:pika.IncomingMessage):
        async with message.process():
            body=json.loads(message.body.decode())
            async with SessionLocal() as db: #type:ignore
                await db.execute(text(f'''
                UPDATE messages set status=\'Failed\' where id={int(body['id'])}'
                '''))
                await db.commit()

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
    logger.info('DLX worker Started')

@app.get('/')
async def root():
    return {'status':'ok'}