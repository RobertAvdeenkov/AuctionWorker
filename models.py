from sqlalchemy import Column,String,Integer,DateTime,ForeignKey,Boolean,func
from sqlalchemy.orm import DeclarativeBase,relationship

class Base(DeclarativeBase):pass

class User(Base):
    __tablename__='users'
    id=Column(Integer,primary_key=True)
    name=Column(String)
    password=Column(String)
    refresh_token=Column(String, default='')
    tg_id=Column(String, default='')
    distribution=Column(Boolean,default=False)

    lots=relationship('Lot',back_populates='user')
    bids=relationship('Bid',back_populates='user')
    messages=relationship('Message',back_populates='user')

class Lot(Base):
    __tablename__='lots'
    id=Column(Integer,primary_key=True)
    title=Column(String)
    ends_at=Column(DateTime)
    current_price=Column(Integer)
    start_price=Column(Integer)
    contact=Column(String)
    user_id=Column(Integer, ForeignKey('users.id'))

    user=relationship('User',back_populates='lots')
    bids=relationship('Bid',back_populates='lot')

class Bid(Base):
    __tablename__='bids'
    id=Column(Integer,primary_key=True)
    price=Column(Integer)
    by=Column(String)
    lot_id=Column(Integer, ForeignKey('lots.id'))
    user_id=Column(Integer, ForeignKey('users.id'))

    lot=relationship('Lot',back_populates='bids')
    user=relationship('User',back_populates='bids')

class Message(Base):
    __tablename__='messages'
    id=Column(Integer,primary_key=True)
    text=Column(String)
    user_id=Column(Integer, ForeignKey('users.id'))
    status=Column(String, default='pending')
    created_at=Column(DateTime, default=func.now())

    user=relationship('User',back_populates='messages')