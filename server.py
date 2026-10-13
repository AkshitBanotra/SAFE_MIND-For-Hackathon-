#!/usr/bin/env python3

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.sse import StreamingResponse
from fastapi.responses import Response
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from llm.ollama_api import companion_response
from voice.tts import pipeline
import soundfile as sf
import shared
import json
from io import BytesIO
import numpy as np

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

class ChatRequest(BaseModel):
    
    message: str

class TTSRequest(BaseModel):

    text: str

@app.post("/chat")
def chat(request: ChatRequest):

    def event_stream():
        for chunk in companion_response(request.message, shared.q1, shared.q2):
            yield f"data: {json.dumps({'delta': chunk})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream")

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
