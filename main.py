from fastapi import FastAPI, Request, WebSocket,Form,Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, Callable
from deepgram import Deepgram
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import logging
import os
import pymongo
from bson.objectid import ObjectId
import time

MONGO_CONFIG = {
    # 'host': "mongodb-pipelines.pipelines",
    'host': 'localhost',
    'port': 27017,
    'database': "pipelines_data_v1",
    'user': "root",
    'password': os.environ.get('MONGO_PASSWORD') or "fifkubBEJEVUxytg"
}

url = f"mongodb://{MONGO_CONFIG['user']}:{MONGO_CONFIG['password']}@{MONGO_CONFIG['host']}:{MONGO_CONFIG['port']}"
client = pymongo.MongoClient(url)
pipelines_db = client[MONGO_CONFIG["database"]]
collection = pipelines_db['phoenix_conversational_intelligence']

load_dotenv()

app = FastAPI()
dg_client = Deepgram("ed2d63ab2b994f422a729422c073622d7a1c6b91")

templates = Jinja2Templates(directory="templates")

logging.config.fileConfig('config/logging.conf', disable_existing_loggers=False)
logger = logging.getLogger(__name__)


async def process_audio(fast_socket: WebSocket, user_id: str,meet_id:str):
    async def get_transcript(data: Dict) -> None:
        if 'channel' in data:
            transcript = data['channel']['alternatives'][0]['transcript']
        
            if transcript:
                if user_id:
                    collection.update_one({
                                            '_id' : meet_id
                                                    },{
                                            '$push' : {f"attendees.{user_id}.transcript": transcript}  
                                        }, True)

                    print(f"meeting_url:{meet_id}",{"attendees":{f"{user_id}":{"transcript":transcript}}})
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
async def websocket_endpoint(websocket: WebSocket,
                             user_id:str = Query(...),
                             meet_id:str = Query(...)):
    await websocket.accept()
    logging.info(f"user id is : {user_id} and meeting_id is {meet_id}")
    
    for excp_ctr in range(0,6):
        try:
            deepgram_socket = await process_audio(websocket,user_id,meet_id) 
            while True:
                data = await websocket.receive_bytes()
                deepgram_socket.send(data)
        except Exception as e:
            if excp_ctr==5:
                raise Exception(f'Could not process audio: {e}')
        finally:
            if excp_ctr==5:
                await websocket.close()
        logging.info("retrying without raising excewption")
        time.sleep(2)


@app.get("/process_meeting")
def generate_meeting_insights(meeting_id:str = Query(...)):
    doc = collection.find_one({'_id': meeting_id})['attendees']

    meeting_insights = {}

    summarizer_tokenizer = AutoTokenizer.from_pretrained("slauw87/bart_summarisation")
    summarizer_model = AutoModelForSeq2SeqLM.from_pretrained("slauw87/bart_summarisation")

    f = open('config/interview_transcript_1.txt', 'r')

    def fetch_full_transcript(meeting_id):
        doc = collection.find_one({'_id': meeting_id})
        full_transcript = []

        if doc is None:
            return full_transcript

        for user_id, user_transcript in doc['attendees'].items():
            logging.info(f"\n {user_id} \n")
            logging.info(len(user_transcript['transcript']))
            transcript = ' '.join(user_transcript['transcript'])
            logging.info(transcript)
            full_transcript.append(transcript)
            logging.info("\n\n\n")

        return full_transcript

    full_transcript = fetch_full_transcript(meeting_id)
    inputs = summarizer_tokenizer([' '.join(full_transcript)], max_length=1024, return_tensors="pt")
    summary_ids = summarizer_model.generate(inputs["input_ids"], num_beams=2, min_length=0)
    logging.info ("\n\n Generating Summary \n")
    summary_output = \
        summarizer_tokenizer.batch_decode(summary_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
    logging.info (f"\n {summary_output} \n\n")
    meeting_insights["summary"] = summary_output

    qa_tokenizer = AutoTokenizer.from_pretrained("MaRiOrOsSi/t5-base-finetuned-question-answering")
    qa_model = AutoModelForSeq2SeqLM.from_pretrained("MaRiOrOsSi/t5-base-finetuned-question-answering")

    meeting_insights["insights"] = []
    for question in open('config/recruitment_questions.txt', 'r').read().split('\n'):
        if not question:
            continue

        qa_input = f"question: {question} context: {summary_output}"

        encoded_input = qa_tokenizer([qa_input], return_tensors='pt', max_length=512, truncation=True)
        output = qa_model.generate(input_ids=encoded_input.input_ids, attention_mask=encoded_input.attention_mask)
        output = qa_tokenizer.decode(output[0], skip_special_tokens=True)

        if output:
            logging.info(qa_input)
            logging.info(f"\n\n {output} \n\n")
            meeting_insights["insights"].append( {"question": question, "insight": output} )

    return {"message": meeting_insights}
