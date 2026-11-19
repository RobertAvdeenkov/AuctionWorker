from fastapi import WebSocket
import json
from logger import logger
from prometheus_client import Gauge

WS_CONNECTION_COUNTER=Gauge('ws_counter','Websockets connection counter')

class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, websocket):
        await websocket.accept()
        self.connections.append(websocket)
        WS_CONNECTION_COUNTER.inc()

    async def disconnect(self,websocket):
        try:
            if websocket in self.connections: self.connections.remove(websocket)
            await websocket.close()
        finally:
            logger.info(f'{websocket} disconnected')
            WS_CONNECTION_COUNTER.dec()

    async def broadcast(self, data, redis):
        for i in self.connections:
            await i.send_text(json.dumps(data))
        await redis.flushdb()
        

    