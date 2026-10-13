#!/usr/bin/env python3

import queue

#######################

q1 = queue.Queue()
q2 = queue.Queue()
q3 = queue.Queue()

#######################

model = "batiai/gemma4-e2b:q4"

###################

llm_busy = False
tts_playing = False
llm_listen = False
llm_active = False

####################

url = "http://localhost:11434/api/chat"

SIGNALS = ("[HELP]")
