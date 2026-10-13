#!/usr/bin/env python3

import shared

class DistressEngine:

    def __init__(self):

        self.latest_score = None

    def runtime_distress_score(self):

        assessment = shared.q3.get()
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
