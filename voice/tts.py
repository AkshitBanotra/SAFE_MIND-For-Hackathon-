#!/usr/bin/env python3

import sounddevice as sd
import threading
from kokoro import KPipeline
import shared

##########################

pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M', device='cuda')

##########################

# For TTS warmup...

def tts_warmup():
    for _, _, audio in pipeline("warm up", voice='af_heart'):
        pass

###################################################################

def tts_worker(q1):

    while True:
        text = q1.get()
        if text == None:
            break
        #print("message get...")
        
        #for intent in intents:
            #if text == intent:
                #break

        generator = pipeline(   
                             text, 
                             voice='af_heart',
                             speed=0.92,
                             split_pattern=r'[.!?]+'
                             )
        # generator object will yield 3 values per chunk on each iteration.
        # gs is for graphemes string (the text chunk being spoken)
        # ps for phoneme representation (pronunciation information)
        # audio -> actual waveform data as numpy array (like audio consists of sampled waveform amplitudes represented as an array)
        for _, _, audio in generator:

            #if not speech_queue.empty():
                #break

            if audio is not None:
                #print(f"Playing: {gs}")
                #print(str(len(audio)/24000) + "s" + " and " + str(len(audio))
                shared.tts_playing = True
                sd.play(audio, 24000)
                sd.wait()
                shared.tts_playing = False
