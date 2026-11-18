import aio_pika as pika
from fastapi import FastAPI
import os
from logger import logger
import asyncio
import json
from tasks import r
from aiogram import Bot

app=FastAPI()

connection=None
channel=None
TOKEN=os.getenv('TOKEN')
if TOKEN:
    bot=Bot(token=TOKEN)

background_tasks = set()

def spawn(coro):
    t = asyncio.create_task(coro)
    background_tasks.add(t)
    t.add_done_callback(background_tasks.discard)
    return t

async def main():
    queue=await channel.declare_queue('retry_queue', arguments={'x-message-ttl': 30000, 'x-dead-letter-exchange': '', 'x-dead-letter-routing-key': 'sites'}) #type:ignore
    main_queue=await channel.declare_queue('main_queue') #type:ignore
    dlx_queue=await channel.declare_queue('dlx_queue') #type:ignore

    async def callback(message:pika.IncomingMessage):
        async with message.process():
            body=json.loads(message.body.decode())
            count=await r.get(f'{body['id']}:tg:message')
            if count: count=int(count)+1
            else: count=1
            if count>3:
                await channel.default_exchange.publish(message=pika.Message(json.dumps({'id':body['id']}).encode()), routing_key='dlx_queue') #type:ignore
            try:
                await bot.send_message(chat_id=int(body['tg']), text=body['message'])
            except:
                await r.set((f'{body['id']}:tg:message'), count)
                await channel.default_exchange.publish(routing_key='retry', message=pika.Message(json.dumps({'tg':body['tg'], 'id':body['id'], 'message':f'Вашу ставку в {body['title']} перебили!'}).encode())) #type:ignore

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
    logger.info('Retry worker Started')

@app.get('/')
async def root():
    return {'status':'ok'}
