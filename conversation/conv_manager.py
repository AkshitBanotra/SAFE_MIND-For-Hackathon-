#!/usr/bin/env python3

import sqlite3
from llm.ollama_api import messages
from pathlib import Path
import queue
import threading

class ConversationManager:

    def __init__(self, dbfile):

        self.dbfile = dbfile
        self.conn = None
        self.cursor = None
        self.tracked = 0
        self.queue_tracked = 0
        self.messages = messages
        self.q = queue.Queue()

    def initialize(self):
        
        self.conn = sqlite3.connect(self.dbfile)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS victim_conv(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            victim_id TEXT,
            message TEXT
        )"""
                            )

        self.conn.commit()

    def add(self):

        print("Total messages:", len(self.messages))
        print("User messages:", sum(
            1 for msg in self.messages
            if msg.get("role") == "user"
        ))
        user_messages = []
        for msg in self.messages:
            if msg.get("role") == "user":
                user_messages.append(msg["content"])

        msg_limit = 10

        self.tracked = len(user_messages)
        print("User_messages:", self.tracked)
        
        batch = user_messages[self.queue_tracked: self.queue_tracked + msg_limit]

        print(batch)

        if self.tracked - self.queue_tracked >= msg_limit:
            self.q.put(batch)
            self.queue_tracked += msg_limit

        print("Already queued:", self.queue_tracked)

    def database_worker(self):

        self.conn = sqlite3.connect(self.dbfile)
        self.cursor = self.conn.cursor()

        while True:
            
            msgs = self.q.get()

            try:
                for message in msgs:
                    self.cursor.execute("""
                    INSERT INTO victim_conv(victim_id, message)
                    VALUES(?, ?)
                    """,
                                        (
                                        "PAT#1",
                                        message
                                        ))
                self.conn.commit()
            
            finally:
                self.q.task_done()

    def start_db_worker(self):

        self.db_thread = threading.Thread(
        target=self.database_worker,
        daemon=True
        )

        self.db_thread.start()

    def get_messages(self, victim_id):

        conn = sqlite3.connect(self.dbfile)
        cursor = conn.cursor()

        cursor.execute("""
        SELECT message
        FROM victim_conv
        WHERE victim_id=?
        ORDER BY id
        LIMIT 10 OFFSET ?
        """, (victim_id, self.queue_tracked - 10))

        result = []
        for row in cursor.fetchall():
            result.append(row[0])

        conn.close()

        return result

if __name__ == "__main__":

    dbfile = Path(__file__).resolve().parent / "conversations.db"

    conv = ConversationManager(dbfile)

    conv.initialize()
    conv.start_db_worker()
    conv.add()

    conv.q.join()

    print(conv.get_messages("PAT#1"))
