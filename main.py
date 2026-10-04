#!/usr/bin/env python3

import os
import socket
from pathlib import Path
import threading
import json
import requests
from llm.ollama_api import ollama_warmup, streaming_response, nyx_response, messages
from voice.tts import tts_warmup, tts_worker
from pathlib import Path
import re
import shared
import time
import voice.stt
#import core.dispatcher
from core.PromptManager import PromptManager
import subprocess
from datetime import datetime
import json
import conversation.conv_manager
#from filelock import FileLock

###########################

parent = Path(__file__).resolve().parent

sound_path1 = parent / "sounds" / "ux_sound_1.mp3"
sound_path2 = parent / "sounds" / "ux_sound_2.mp3"
sound_path3 = parent / "sounds" / "ux_sound_3.mp3"
sound_path4 = parent / "sounds" / "ux_sound_4.mp3"
json_path = parent / "config.json"

dbfile = Path(__file__).resolve().parent / "conversation" / "conversations.db"
conv = conversation.conv_manager.ConversationManager(dbfile)
conv.initialize()
prompt = PromptManager()

#lock = FileLock(parent/"config.json.lock")

#######################################

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
    assistant_message = streaming_response(response, shared.q1, None)
    tts_worker(shared.q1)

##########################################

def assessment_worker():

    assessment_schema = {
        "type": "object",
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": ["1.0"]
            },
        "indicators": {
            "type": "object",
            "properties": {
                "fear": {"$ref": "#/$defs/indicator"},
                "anxiety": {"$ref": "#/$defs/indicator"},
                "hopelessness": {"$ref": "#/$defs/indicator"},
                "sadness_grief": {"$ref": "#/$defs/indicator"},
                "anger_irritability": {"$ref": "#/$defs/indicator"},
                "guilt_shame": {"$ref": "#/$defs/indicator"},
                "hypervigilance": {"$ref": "#/$defs/indicator"},
                "intrusive_memories": {"$ref": "#/$defs/indicator"},
                "avoidance": {"$ref": "#/$defs/indicator"},
                "emotional_numbness": {"$ref": "#/$defs/indicator"},
                "sleep_difficulties": {"$ref": "#/$defs/indicator"},
                "social_withdrawal": {"$ref": "#/$defs/indicator"},
                "daily_functioning_difficulty": {
                    "$ref": "#/$defs/indicator"
                },
                "perceived_safety_concern": {
                    "$ref": "#/$defs/indicator"
                }
            },
            "required": [
                "fear", "anxiety", "hopelessness", "sadness_grief",
                "anger_irritability", "guilt_shame", "hypervigilance",
                "intrusive_memories", "avoidance", "emotional_numbness",
                "sleep_difficulties", "social_withdrawal",
                "daily_functioning_difficulty", "perceived_safety_concern"
            ],
            "additionalProperties": False
        },
        "safety_flags": {
            "type": "object",
            "properties": {
                "explicit_self_harm_or_suicide_concern": {
                    "type": "boolean"
                },
                "explicit_immediate_danger": {
                    "type": "boolean"
                }
            },
            "required": [
                "explicit_self_harm_or_suicide_concern",
                "explicit_immediate_danger"
            ],
            "additionalProperties": False
        }
    },
    "required": ["schema_version", "indicators", "safety_flags"],
    "additionalProperties": False,
    "$defs": {
    "indicator": {
        "type": "object",
        "properties": {
            "score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100
                    },
                    "evidence": {
                        "type": "string"
                    }
                },
                "required": ["score", "evidence"],
                "additionalProperties": False
            }
        }
    }

    last_accessed = 0
    while True:
        if conv.queue_tracked >= last_accessed + 10:
            trigger = """
            Assess the supplied batch of user messages using the defined indicators
            and scoring rules. Return only the JSON object specified in the schema.
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
            
            payload = {"model": "batiai/gemma4-e2b:q4", "messages": runtime_message, "think": False, "stream": False, "format": assessment_schema}

            response = requests.post(shared.url, json=payload)
            print(response)
            assessment = response.json()["message"]["content"]
            assessment = json.loads(assessment)
            print(assessment)
            last_accessed += 10

        time.sleep(0.2)

def time_date_info():

    now = datetime.now()
    current_time = now.strftime("%I:%M %p")

    time_data = {
        "time": current_time
    }

    return time_data

#########################################

def clear_screen():
    #\033[H moves the cursor to the top left; \033[2J clears the entire screen
    print("\033[H\033[2J", end="")

#########################################

def llm_toggle():
    
    socket_path = "/tmp/my_socket"

    # Remove old socket file if it exists.

    try:
        os.unlink(socket_path)
    except FileNotFoundError:
        pass

    # Create Unix domain socket.

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    # Bind socket to filesystem path

    server.bind(socket_path)

    # Listen for connections

    server.listen(1)

    try:
        while True:
            connection, _ = server.accept()
            print("Client connected...")

            data = connection.recv(1024)
            if not data:
                break

            if data == b'LLM_TOGGLE':
                print("Data recieved...")
                shared.llm_listen = not shared.llm_listen
                if shared.llm_listen:
                    subprocess.run(["notify-send", "[COMPANION]", "Listening..."])
                    subprocess.run(["paplay", sound_path2])
                else:
                    subprocess.run(["notify-send", "[COMPANION]", "Going Silent..."])
                    subprocess.run(["paplay", sound_path3])
                print("LLM_LISTEN STATE: ", str(shared.llm_listen))

    finally:
      
        connection.close()
        server.close()

        # Remove socket file
        try:
            os.unlink(socket_path)
        except FileNotFoundError:
            pass

###########################

subprocess.run(["notify-send", "[COMPANION]", "Initializing..."])
subprocess.run(["paplay", sound_path1])
time.sleep(0.5)
subprocess.run(["notify-send", "[COMPANION]", "Loading models..."])
subprocess.run(["notify-send", "[COMPANION]", "Warming up..."])

ollama_warmup()
tts_warmup()

subprocess.run(["notify-send", "[COMPANION]", "ready."])
subprocess.run(["paplay", sound_path1])

time.sleep(0.5)

# For startup greet.

greet = "Hello."
auto_trigger(prompt.greet(time_date_info()), greet)

########################

#exit_messages = [ "/exit", "goodbye", "bye" ]

stt_thread = threading.Thread(
        target=voice.stt.stt_start,
        daemon=True
        )

uds_thread = threading.Thread(
        target=llm_toggle,
        daemon=True
        )
#stt_thread.start()
#uds_thread.start()

conv.start_db_worker()
assessment_thread = threading.Thread(
    target=assessment_worker,
    daemon=True
)
assessment_thread.start()

clear_screen()

while True:
    #speech = voice.stt.speech_queue.get()
    #user_input = f"you:{speech}"
    user_input = input("you: ")
    #print(user_input)
    t1 = threading.Thread(target=nyx_response, args=(user_input, shared.q1, shared.q2))
    t2 = threading.Thread(target=tts_worker, args=(shared.q1,))
    #t3 = threading.Thread(target=core.dispatcher.intent_route, args=(shared.q2,))

    t1.start()
    t2.start()
    #t3.start()

    t1.join()
    t2.join()
    #t3.join()

    conv.add()

print()
