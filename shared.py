#!/usr/bin/env python3

import queue

#######################

q1 = queue.Queue()
q2 = queue.Queue()
q3_1 = queue.Queue()
q3_2 = queue.Queue()
shared_assessment_1 = None
shared_assessment_2 = None

tts_queue = queue.Queue()

speech_queue = queue.Queue()
user_transcript = queue.Queue()

#######################

model = "batiai/gemma4-e2b:q4"

###################

llm_busy = False
tts_playing = False
llm_listen = False
llm_active = False
new_assessment = None

####################

url = "http://localhost:11434/api/chat"

SIGNALS = ("[HELP]")
