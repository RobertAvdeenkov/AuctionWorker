from aiogram import Bot,Dispatcher,types,F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from database import SessionLocal
from sqlalchemy import select
from models import User
import bcrypt
from fastapi import FastAPI
import asyncio
import os
from aiogram.utils.keyboard import InlineKeyboardBuilder
from logger import logger
import json
import uuid

connection=None
channel=None

app=FastAPI()

class Form(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()

Token=os.getenv('TOKEN', '')

background_tasks = set()

def spawn(coro):
    t = asyncio.create_task(coro)
    background_tasks.add(t)
    t.add_done_callback(background_tasks.discard)
    return t

bot=Bot(token=Token)
dp=Dispatcher()

@dp.message(Command('start'))
async def start(message:types.Message, state:FSMContext):
    data=await state.get_data()
    user=data.get('user')
    builder=InlineKeyboardBuilder()
    if user:
        builder.button(text='Настроить рассылку', callback_data='settings')
        builder.adjust(1)
        await message.answer(f'''
        Здравствуйте, {user}!
        ''', reply_markup=builder.as_markup())
        return
    else:
        await message.answer('Введите логин')
        await state.set_state(Form.waiting_for_login)

@dp.message(Form.waiting_for_login)
async def wait_password(message:types.Message, state:FSMContext):
    login=message.text
    await state.update_data(login=login)
    await message.answer('Введите пароль')
    await state.set_state(Form.waiting_for_password)

@dp.message(Form.waiting_for_password)
async def authorization(message:types.Message, state:FSMContext):
    data=await state.get_data()
    login=data.get('login')
    if login and message.text:
        async with SessionLocal() as db: #type:ignore
            result=(await db.execute(select(User).filter(User.name==login))).first()
            if not(result):
                await message.answer('Неправильный логин или пароль')
                return
            user=result[0]
            if not(bcrypt.checkpw(message.text.encode(), user.password.encode())):
                await message.answer('Неправильный логин или пароль')
                return
            await state.update_data(user=user.name)
            user.tg_id=message.from_user.id #type:ignore
            await db.commit()
            await message.answer('Авторизация прошла успешно!\nВведите /start, чтобы продолжить')
            await state.set_state(None)
            return
    else:
        await message.answer('Введите /start, чтобы продолжить')
        return

@dp.message(F.data=='settings')
async def settings(message:types.Message, state:FSMContext):
    data=await state.get_data()
    name=data.get('user')
    if name:
        builder=InlineKeyboardBuilder()
        async with SessionLocal() as db: #type:ignore
            result=(await db.execute(select(User).filter(User.name==name))).first()
            if not(result):
                await message.answer('Произошла ошибка')
                await state.clear()
                return
            user=result[0]
            builder.button(text=f'{'Включить' if not(user.distribution) else 'Отключить'} рассылку', callback_data='distribution')
            await message.answer('Настройки', reply_markup=builder.as_markup())
            return
    else:
        await message.answer('Введите /start, чтобы продолжить')
        return

@dp.message(F.data=='distribution')
async def distribution_setting(message:types.Message, state:FSMContext):
    data=await state.get_data()
    name=data.get('user')
    if name:
        builder=InlineKeyboardBuilder()
        async with SessionLocal() as db: #type:ignore
            result=(await db.execute(select(User).filter(User.name==name))).first()
            if not(result):
                await message.answer('Произошла ошибка')
                await state.clear()
                return
            user=result[0]
            if user.distribution==False:
                user.distribution=True
            else:
                user.distribution=False
            await db.commit()
            await message.answer('Успешно!')
            return

@app.on_event('startup')
async def startup():
    await bot.delete_webhook(drop_pending_updates=True)
    spawn(dp.start_polling(bot))

@app.get('/')
async def root():
    return {'status':'ok'}