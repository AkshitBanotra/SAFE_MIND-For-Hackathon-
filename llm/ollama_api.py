#!/usr/bin/env python3

import requests
import json
import re
from shared import llm_busy, SIGNALS, url
from core.PromptManager import PromptManager
from pathlib import Path

#############################

prompt = PromptManager()

message_path = Path(__file__).resolve().parent.parent / "conversation" / "messages.json"

with open(message_path) as g:
    messages = json.load(g)

if len(messages) == 0:
    messages.insert(0, {
                    "role": "system",
                    "content": prompt.base_prompt()})

def ollama_warmup():
    requests.post(url, json={"model": "batiai/gemma4-e2b:q4", "messages": [{"role": "user", "content": "hi"}], "stream": False})

def streaming_response(response, q1, q2=None):


    print("Companion: ", end='', flush=True)
    
        # Ollama sends responses in NDJSON [Newline Delimited JSON] format
        # for streaming (means each response or line is an independent JSON
        # object with a new line).
        # Standard JSON expects one valid object consisting of data under the
        # {} brackets.
        # response.iter_lines() will split each line in the incoming response
        # (which is the token itself) and it gets equal to line.
    assistance_response = ""
    buffer = ""
    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)
            #print(chunk)
            if "message" in chunk:
                if not chunk["message"]["content"].startswith(SIGNALS):
                    print(chunk["message"]["content"], end='', flush=True)
                assistance_response += chunk["message"]["content"]
                buffer += chunk["message"]["content"]
                if re.search(r'[.!?]', buffer):
                    if buffer.startswith(SIGNALS):
                        if q2 is not None:
                            q2.put(buffer.strip())
                    else:
                        q1.put(buffer.strip())
                        #print("message put...")
                    buffer = ""

    if buffer.strip():
        if buffer.startswith(SIGNALS):
            if q2 is not None:
                q2.put(buffer.strip())
            else:
                q1.put(buffer.strip())

    q1.put(None)
    if q2 is not None:
        q2.put(None)

    return assistance_response

def nyx_response(user_input, q1, q2):

    messages.append(
        {
    "role": "user",
    "content": user_input})

    data = {
            "model": "batiai/gemma4-e2b:q4",
            "messages": messages,
            "think": False,
            "stream": True,
            "options": {
                "temperature": 0.65, # Adjust creativity.
                "top_p": 0.9, # nucleus sampling - combined probability of tokens.
                "repeat_penalty": 1.15, # repeatition penality.
                "num_predict": 256, # max. token generation limit.
                "seed": 42
                }
            }

    llm_busy = True
    response = requests.post(url, json=data, stream=True)

    assistance_response = streaming_response(response, q1, q2)

    #if not assistance_response.startswith(INTENTS):
    messages.append({
        "role": "assistant",
        "content": assistance_response
    })
    
    with open("messages.json", "w") as h:
        json.dump(messages, h, indent=4)

    llm_busy = False
    print()
