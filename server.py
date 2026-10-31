#!/usr/bin/env python3

import asyncio
import threading
from pathlib import Path
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.sse import StreamingResponse
from fastapi.responses import Response
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from llm.ollama_api import companion_response, streaming_response, messages, behaviour_adaptor
from core.distress_engine import DistressEngine
from core.PromptManager import PromptManager
from voice.tts import pipeline, tts_worker
from voice.stt import callback, stt_worker, stt_start
import soundfile as sf
import shared
import json
import queue
from io import BytesIO
import conversation.conv_manager
import numpy as np
import time
import re
from datetime import datetime

############################################

parent_path = Path(__file__).resolve().parent

json_path = parent_path / "config.json"

dbfile = parent_path / "conversation" / "conversations.db"

conv = conversation.conv_manager.ConversationManager(dbfile)
conv.initialize()

prompt = PromptManager()

new_message = threading.Event()

distress = DistressEngine()

############################################

def tts_streaming():
        for audio in tts_worker(shared.q1):
            if audio is not None:
                shared.tts_queue.put(audio)

###########################################

def auto_trigger(message, trigger):
    
    runtime_message = [
        {
            "role": "system",
            "content": message
        },
        {
            "role": "user",
            "content": trigger
        }
    ]
    payload = {"model": "batiai/gemma4-e2b:q4", "messages": runtime_message, "think": False, "stream": True}
    response = requests.post(shared.url, json=payload)
    print(response)
    for chunk in streaming_response(response, shared.q1, None):
        yield chunk

###########################################

def parse_assessment(raw: str) -> dict[str, int]:

    EXPECTED_KEYS = {
        "FA", "SH", "HP", "IM",
        "SD", "DF", "SELF", "DANGER"
    }

    pattern = r"(?m)^\s*([A-Z]+)\s*=\s*(\d+)\s*$"

    pairs = re.findall(pattern, raw)
    result = {}

    for key, value in pairs:
        if key not in EXPECTED_KEYS:
            continue

        if key in result:
            raise ValueError(f"Duplicate assessment key: {key}")

        result[key] = int(value)

    missing = EXPECTED_KEYS - result.keys()

    if missing:
        raise ValueError(f"Missing assessment keys: {sorted(missing)}")

    return result

###########################################

def assessment_worker():

    with open(json_path, "r") as f:
        data = json.load(f)

    last_accessed = 0
    while True:
        if conv.queue_tracked >= last_accessed + 5:
            trigger = """
            Assess the supplied batch of user messages using the defined indicators
            and scoring rules. Return in the specified format.
            """

            runtime_message = [
                {
                    "role": "system",
                    "content": prompt.assessment_rules(conv.get_messages("PAT#1"))
                },
                {
                    "role": "user",
                    "content": trigger
                }
            ]
            
            payload = {"model": "batiai/gemma4-e2b:q4", "messages": runtime_message, "think": False, "stream": False }

            response = requests.post(shared.url, json=payload)
            print(response)
            assessment = response.json()["message"]["content"]
            assessment_values = parse_assessment(assessment)
            shared.q3_1.put(assessment_values)
            shared.q3_2.put(assessment_values)
            distress.runtime_distress_score(shared.q3_1)
            distress.distress_db("insert")
            data["llm_analysed"] = True
            with open(json_path, "w") as f:
                json.dump(data, f, indent=4)
            print(assessment)
            print("RAW ASSESSMENT:", repr(assessment))
            last_accessed += 5

        time.sleep(0.2)

###########################################

def assessment_generator():

    conv.start_db_worker()

    assessment_thread = threading.Thread(
    target=assessment_worker,
    daemon=True
    )

    distress.distress_db("init")

    assessment_thread.start()
 
    while True:
        new_message.wait()
        new_message.clear()

        behaviour_adaptor_thread = threading.Thread(
        target=behaviour_adaptor,
        daemon=True
        )

        behaviour_adaptor_thread.start()
        conv.add()

###########################################

def time_date_info():

    now = datetime.now()
    current_time = now.strftime("%I:%M %p")

    time_data = {
        "time": current_time
    }

    return time_data

###########################################

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    stt_start()
    
    print("STT worker started")

    assessment_generator_thread = threading.Thread(
        target=assessment_generator,
        daemon=True
    )

    assessment_generator_thread.start()

    tts_thread = threading.Thread(
        target=tts_streaming,
        daemon=True
    )
    
    tts_thread.start()
    
    print("TTS worker started")

    yield

    # Shutdown
    print("FastAPI shutting down")

###########################################

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3000/therapist"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

##########################################

class ChatRequest(BaseModel):
    
    message: str

#########################################

class TTSRequest(BaseModel):

    text: str

#########################################

@app.get("/greeting")
def greet():

    greet = "Greet me with time awareness according to your instructions."
    def event():
        for text in auto_trigger(prompt.greet(time_date_info()), greet):
            yield f"data: {json.dumps({'delta': text})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event(),
        media_type="text/event-stream"
    )

#########################################

@app.post("/chat")
def chat(request: ChatRequest):

    if request.message:
        new_message.set()

    def event_stream():
        for chunk in companion_response(request.message, shared.q1, shared.q2):
            yield f"data: {json.dumps({'delta': chunk})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream")

#########################################

@app.post("/tts")
def tts(request: TTSRequest):

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required.")

    audio_chunks = []
    for _, _, audio in pipeline(
            request.text,
            voice='af_heart',
            speed=0.92,
            split_pattern=r'[.!?]+'
    ):
        if audio is not None:
            audio_chunks.append(audio)

    combined_audio = np.concatenate(audio_chunks)

    filelink_buffer = BytesIO()
    sf.write(filelink_buffer, combined_audio, 24000, format="WAV", subtype="PCM_16")

    return Response(content=filelink_buffer.getvalue(), media_type="audio/wav")

############################################

def produce_chunks(user_input, output_queue):
    try:
        for chunk in companion_response(
            user_input, shared.q1, shared.q2
        ):
            output_queue.put(("chunk", chunk))

    except Exception as exc:
        output_queue.put(("error", str(exc)))

    finally:
        output_queue.put(("done", None))

#################################################

@app.websocket("/voice")
async def voice_chat(websocket: WebSocket):

    await websocket.accept()

    async def send_audio():
        
        while True:
            audio = await asyncio.to_thread(shared.tts_queue.get)
            await websocket.send_bytes(audio)

    audio_task = asyncio.create_task(send_audio())

    try:
        while True:
            audio = await websocket.receive_bytes()

            if len(audio) != 512 * 4:
                continue

            audio_chunk = np.frombuffer(audio, dtype=np.float32)
            callback(audio_chunk)

            try:
                text = shared.user_transcript.get_nowait()
            except queue.Empty:
                text = None

            if text:
                await websocket.send_json({
                    "type": "user_transcript",
                    "text": text,
                })

            try:
                user_input = shared.speech_queue.get_nowait()
            except queue.Empty:
                user_input = None

            if not user_input:
                continue

            output_queue = queue.Queue()

            llm_thread = threading.Thread(
                target=produce_chunks,
                args=(user_input, output_queue),
                daemon=True
            )
            llm_thread.start()

            while True:
                message_type, payload = await asyncio.to_thread(
                    output_queue.get
                )

                if message_type == "chunk":
                    await websocket.send_json({
                        "type": "text_delta",
                        "delta": payload,
                    })

                elif message_type == "error":
                    await websocket.send_json({
                        "type": "error",
                        "message": payload,
                    })

                elif message_type == "done":
                    await websocket.send_json({
                        "type": "text_done",
                    })
                    break
    
    except WebSocketDisconnect:
        pass

    finally:
        audio_task.cancel()

####################################################

# Therapist side interface...

@app.get("/therapist/distress/today")
def distress_index():

    now = datetime.now()
    current_date = now.strftime("%d %B %Y")

    distress_scores = distress.distress_db("fetch_1")

    #distress.distress_db("rem_distress")

    total = 0
    count = 0
    for row in distress_scores:

        if row[0] is not None:
            total = total + row[0]
            count += 1

    if count > 0:
        distress_index = total / count
        distress_index = round(distress_index)
    else:
        distress_index = None

    print("Distress Index: ", distress_index)

    if distress_index is None:
        raise HTTPException(status_code=404, detail="No distress score for today.")

    return {
            "date": current_date,
            "distress_score": distress_index
    }
