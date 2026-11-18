import logging
import json
from datetime import datetime

class Formatter(logging.Formatter):
    def format(self,record):
        data={
            'time':datetime.fromtimestamp(record.created).isoformat(),
            'level':record.levelname,
            'message':record.getMessage()
        }
        if record.exc_info:
            data['exc_info']=self.formatException(record.exc_info)
        return json.dumps(data)

def setup_logger():
    logger=logging.getLogger('app')
    logger.setLevel(logging.INFO)

    handler=logging.StreamHandler()
    handler.setFormatter(Formatter())

    logger.addHandler(handler)
    return logger

logger=setup_logger()