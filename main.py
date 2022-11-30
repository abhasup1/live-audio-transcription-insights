from fastapi import FastAPI, Request, WebSocket,Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, Callable
from deepgram import Deepgram
from dotenv import load_dotenv
import os
import pymongo
from bson.objectid import ObjectId

MONGO_CONFIG = {
    'host': "mongodb-pipelines.pipelines",
    'port': 27017,
    'database': "pipelines_data_v1",
    'user': "root",
    'password': os.environ['MONGO_PASSWORD']
             
}

url = f"mongodb://{MONGO_CONFIG['user']}:{MONGO_CONFIG['password']}@{MONGO_CONFIG['host']}:{MONGO_CONFIG['port']}"
client = pymongo.MongoClient(url)
pipelines_db = client[MONGO_CONFIG["database"]]
collection = pipelines_db['phoenix_conversational_intelligence']

load_dotenv()

app = FastAPI()
meeting_url="http://www.phoneix-hackathon-meet"
dg_client = Deepgram("ed2d63ab2b994f422a729422c073622d7a1c6b91")

templates = Jinja2Templates(directory="templates")

async def process_audio(fast_socket: WebSocket):
    async def get_transcript(data: Dict) -> None:
        if 'channel' in data:
            transcript = data['channel']['alternatives'][0]['transcript']
        
            if transcript:
                user_name="abhas"
                if user_name:
                    collection.update_one({
                                            '_id' : meeting_url
                                                    },{
                                            '$push' : {f"attendees.{user_name}.transcript": transcript}  
                                        }, True)

                    print(f"meeting_url:{meeting_url}",{"attendees":{f"{user_name}":{"transcript":transcript}}})
                await fast_socket.send_text(transcript)

    deepgram_socket = await connect_to_deepgram(get_transcript)

    return deepgram_socket

async def connect_to_deepgram(transcript_received_handler: Callable[[Dict], None]):
    try:
        socket = await dg_client.transcription.live({'punctuate': True, 'interim_results': False})
        socket.registerHandler(socket.event.CLOSE, lambda c: print(f'Connection closed with code {c}.'))
        socket.registerHandler(socket.event.TRANSCRIPT_RECEIVED, transcript_received_handler)
        
        return socket
    except Exception as e:
        raise Exception(f'Could not open socket: {e}')
 
@app.get("/", response_class=HTMLResponse)
def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/listen")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        deepgram_socket = await process_audio(websocket) 
        while True:
            data = await websocket.receive_bytes()
            deepgram_socket.send(data)
    except Exception as e:
        raise Exception(f'Could not process audio: {e}')
    finally:
        await websocket.close()

    