#!/usr/bin/env python3

import os
import socket
from pathlib import Path
import threading
import json
import requests
from llm.ollama_api import ollama_warmup, streaming_response, companion_response, messages, behaviour_adaptor
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
import re

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
    for _ in streaming_response(response, shared.q1, None):
        pass
    tts_worker(shared.q1)

##########################################

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

##########################################

def assessment_worker():

    with open(json_path, "r") as f:
        data = json.load(f)

    last_accessed = 0
    while True:
        if conv.queue_tracked >= last_accessed + 5:
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
            
            payload = {"model": "batiai/gemma4-e2b:q4", "messages": runtime_message, "think": False, "stream": False }

            response = requests.post(shared.url, json=payload)
            print(response)
            assessment = response.json()["message"]["content"]
            shared.q3.put(parse_assessment(assessment))
            data["llm_analysed"] = True
            with open(json_path, "w") as f:
                json.dump(data, f, indent=4)
            print(assessment)
            print("RAW ASSESSMENT:", repr(assessment))
            last_accessed += 5

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

########################################

def run_companion_response(user_input):

    for _ in companion_response(user_input, shared.q1, shared.q2):
        pass

#######################################
while True:
    #speech = voice.stt.speech_queue.get()
    #user_input = f"you:{speech}"
    user_input = input("you: ")
    #print(user_input)
    t1 = threading.Thread(target=run_companion_response, args=(user_input,))
    t2 = threading.Thread(target=tts_worker, args=(shared.q1,))
    behaviour_adaptor_thread = threading.Thread(target=behaviour_adaptor,)

    t1.start()
    t2.start()
    behaviour_adaptor_thread.start()

    t1.join()
    t2.join()

    conv.add()

print()
