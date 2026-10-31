#!/usr/bin/env python3

import os

# Prevent CPU thread oversubscription when running multiple models concurrently.

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

from faster_whisper import WhisperModel
from silero_vad import load_silero_vad
import subprocess

import sounddevice as sd
import numpy as np
import torch

import queue
import threading

import shared

speech_queue = queue.Queue()

stt_queue = queue.Queue()

model_size = "distil-small.en"

model = WhisperModel(
    model_size,
    device="cpu",
    compute_type="int8",
    cpu_threads=4,
)

model_vad = load_silero_vad()

samplerate = 16000
CHUNK = 512
THRESHOLD = 0.5
SHORT_MAX_SILENCE = 25
LONG_MAX_SILENCE = 313
buffer = []
is_speaking = False
silence = 0

def callback(raw_audio):

    global buffer
    global silence
    global is_speaking

    #if not shared.llm_listen:
        #return

    if shared.tts_playing:
        return

    if shared.llm_busy:
        return

    audio_chunk = raw_audio.flatten()

    audio_chunk = torch.from_numpy(audio_chunk).float()

    confidence = model_vad(
        audio_chunk,
        samplerate
    ).item()

    if confidence > THRESHOLD:
        if not is_speaking:
            is_speaking = True
        
        silence = 0
        chunk = raw_audio.flatten().copy()
        buffer.append(chunk)
    else:
        if is_speaking:
            buffer.append(raw_audio.flatten().copy())

            if len(buffer) > 0:
                silence += 1
                if silence >= LONG_MAX_SILENCE:
                    shared.llm_listen = False
                    print("LLM_LISTENING_STATE: ", shared.llm_listen)
                else:
                    if silence >= SHORT_MAX_SILENCE:
                        # print("Speech ended")
                        audio = np.concatenate(buffer)
                        audio = audio.copy()
                        stt_queue.put(audio)
                        buffer.clear()
                        silence = 0
                        is_speaking = False

def stt_worker():

    while True:
        audio = stt_queue.get()

        segments, info = model.transcribe(
            audio,
            language="en",
            condition_on_previous_text=False,
            hotwords="Nyx",
            beam_size=1,
            )

        text = ""
        for segment in segments:
            text += segment.text.strip()

        if text:
            shared.speech_queue.put(text)
            shared.user_transcript.put(text)

def stt_start():

    worker = threading.Thread(
        target=stt_worker,
        daemon=True,
    )

    worker.start()
