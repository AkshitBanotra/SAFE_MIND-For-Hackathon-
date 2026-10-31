#!/usr/bin/env python3

import requests
import json
import re
import shared
from shared import llm_busy, SIGNALS, url
from core.PromptManager import PromptManager
from core.distress_engine import DistressEngine
from pathlib import Path

#############################

prompt = PromptManager()

message_path = Path(__file__).resolve().parent.parent / "conversation" / "messages.json"

config_path = Path(__file__).resolve().parent.parent / "config.json"

with open(message_path, "r") as g:
    messages = json.load(g)

def sysprompt_writer(rule):

    system_message = {
        "role": "system",
        "content": prompt.base_prompt(rule)
    }

    if messages and messages[0].get("role") == "system":
        messages[0] = system_message
    else:
        messages.insert(0, system_message)

# Initial Behaviour set...

sysprompt_writer("BASE_PROMPT_1.md")

def config_writer(data, flag):

    data["llm_analysed"] = flag
    with open(config_path, "w") as f:
        json.dump(data, f, indent=4)

def behaviour_adaptor():

    with open(config_path, "r") as f:
        data = json.load(f)

    distress = DistressEngine()
    
    while data["llm_analysed"]:

        distress.runtime_distress_score(shared.q3_2)
        distress_score = distress.score_checker()

        if distress_score == "[NORMAL]":
            sysprompt_writer("BASE_PROMPT_1.md") 
            print("Normal behaviour...")
            config_writer(data, False)
        elif distress_score == "[ATTENTIVE]":
            sysprompt_writer("BASE_PROMPT_2.md")
            print("Attentive behaviour...")
            config_writer(data, False)
        elif distress_score == "[ELEVATED]":
            sysprompt_writer("BASE_PROMPT_3.md")
            print("Elevated behaviour...")
            config_writer(data, False)
        elif distress_score == "[HIGH SUPPORT]":
            sysprompt_writer("BASE_PROMPT_4.md")
            print("High support behaviour...")
            config_writer(data, False)

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
                    yield chunk["message"]["content"]
                #assistance_response += chunk["message"]["content"]
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

    #return assistance_response

#def collected_response(response, q1, q2):

    #assistant_response = ""
    #for chunk in streaming_response(response, q1, q2):
        #assistant_response += chunk

    #return assistant_response

def companion_response(user_input, q1, q2):

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


    assistant_response = ""
    for chunk in streaming_response(response, q1, q2):
        assistant_response += chunk
        yield chunk

    #assistance_response = streaming_response(response, q1, q2)

    #if not assistance_response.startswith(INTENTS):
    messages.append({
        "role": "assistant",
        "content": assistant_response
    })
    
    with open("messages.json", "w") as h:
        json.dump(messages, h, indent=4)

    llm_busy = False

    print()
