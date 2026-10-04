#!/usr/bin/env python3

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Message(BaseModel):
    name: str
    age: int


@app.post("/message")
def receive_message(data: Message):

    print("Server received:")
    print("Name:", data.name)
    print("Age:", data.age)

    return {
        "reply": f"Hello {data.name}!",
        "received_age": data.age
    }
