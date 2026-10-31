#!/usr/bin/env python3

import shared
import sqlite3
import json
from pathlib import Path

##########################################

class DistressEngine:

    def __init__(self):

        self.latest_score = None
        self.latest_assessment = None
        self.db_path = Path(__file__).resolve().parent / "distress.db"

    def runtime_distress_score(self, new_assessment):

        if new_assessment is not None:
            assessment = new_assessment.get()

            self.latest_assessment = assessment
            distress_values = {}
            safety_flags = {}

            
            for key, value in assessment.items():
                if key not in ("SELF", "DANGER"):
                    distress_values[key] = value
                else:
                    safety_flags[key] = value

            all_values = []
            for value in distress_values.values():
                all_values.append(value)

            if len(all_values) == 0:
                return None

            total = sum(all_values)
            distress_score = total / len(all_values)

            self.latest_score = distress_score

    def distress_db(self, action):

        def initialize():

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS assessments(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                behaviour_indicators TEXT,
                distress_score INT)"""
                                )

            conn.commit()

        def add():

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            assessment_json = json.dumps(self.latest_assessment)

            cursor.execute("""
            INSERT INTO assessments(behaviour_indicators, distress_score)
            VALUES(?, ?)
            """,
                                (
                                assessment_json,
                                self.latest_score
                                ))
            
            conn.commit()

        def distress_scores_fetch():

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
            SELECT distress_score
            FROM assessments
            """)

            distress_scores = cursor.fetchall() 

            return distress_scores

        def assessments_fetch():

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
            SELECT behaviour_indicators
            FROM assessments
            """)

            indicators = cursor.fetchall()

            return indicators

        def clear_daily_distress_data():

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
            UPDATE assessments
            SET distress_score = NULL;
            """)

            conn.commit()

        def clear_daily_indicators():

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
            UPDATE assessments
            SET behaviour_indicators = NULL;
            """)

            conn.commit()

        if action == "init":
            initialize()
        elif action == "insert":
            add()
        elif action == "fetch_1":
            return distress_scores_fetch()
        elif action == "fetch_2":
            return assessments_fetch()
        elif action == "rem_distress":
            clear_daily_distress_data()
        elif action == "rem_indicators":
            clear_daily_indicators()

    def score_checker(self):

        if self.latest_score == None:
            return "[NORMAL]"

        if 0 < self.latest_score <= 25:

            return "[NORMAL]"

        elif 25 < self.latest_score <= 55:

            return "[ATTENTIVE]"

        elif 55 < self.latest_score <= 75:

            return "[ELEVATED]"
    
        elif 75 < self.latest_score <= 100:
            return "[HIGH SUPPORT]"
