from jose import jwt,JWTError,ExpiredSignatureError
from database import SessionLocal
import os
from sqlalchemy import select
from fastapi import HTTPException
from datetime import datetime
from models import User

SECRET=os.getenv('SECRET')
ALGORITHM=os.getenv('ALGORITHM')

def create_token(user:str,timedelta):
    payload={
        'sub':user,
        'exp':datetime.utcnow()+timedelta
    }
    return jwt.encode(payload,SECRET,ALGORITHM)

async def get_by_token(token:str):
    try:
        data=jwt.decode(token,SECRET,algorithms=[ALGORITHM])
        async with SessionLocal() as db: #type:ignore
            result=(await db.execute(select(User).filter(User.name==data['sub']))).first()
            if not result: raise HTTPException(404,'Такого пользователя нет')
            return result[0]
    except ExpiredSignatureError:
        raise HTTPException(401,'Токен протух!')
    except JWTError:
        raise HTTPException(401,'Неправильный токен!')
    
