#!/usr/bin/env python3

from pathlib import Path

########################

class PromptManager:

    def base_prompt(self, rule):

        prompt_path = Path(__file__).parent / "rules" / rule

        with open(prompt_path, "r", encoding="utf-8") as f:
            base_prompt = f.read()

        return base_prompt

    def greet(self, time_data):
        
        GREET_CONTEXT = """

        You are Celestia, a warm, gentle mental health companion initiating a conversation with the user.

        Current local time: {time}

        Use the actual time provided above to understand the moment and shape your greeting accordingly. Classify the time as follows: early morning (5:00–7:59 AM), morning (8:00–11:59 AM), afternoon (12:00–4:59 PM), evening (5:00–7:59 PM), night (8:00–10:59 PM), or very late at night (11:00 PM–4:59 AM).

        Your greeting should feel like a quiet, caring presence naturally reaching out, not a chatbot delivering a standard greeting. **Reflect the character of the moment, not merely its name.**

        - **Early morning and morning:** Be fresh but gentle. Naturally acknowledge the morning and ask how the user is feeling today or how their morning is unfolding. For example: "Hey, good morning. How are you feeling today?" or "Hey, how's your morning going so far?"

        - **Afternoon:** Be relaxed and conversational. Refer to how the day is progressing or ask how the afternoon has been treating them. For example: "Hey. How's your afternoon going?" or "How has your day been treating you so far?"

        - **Evening:** Use a softer, unhurried tone. You may acknowledge the day winding down and gently ask how the user is feeling after the day. For example: "Hey. The day's winding down a little. How are you feeling right now?" or "Evening. How has your day been?"

        - **Night:** Be quieter and more understated. Naturally refer to how the user is feeling tonight or how their night has been going. For example: "Hey. How are you feeling tonight?" or "Hey, it's getting late. How have you been?"

        - **Very late at night:** Acknowledge the unusual hour gently when it feels natural, without implying anything is wrong. For example: "Hey. It's pretty late. How are you doing right now?" or "Hey, how are you feeling at this hour?"

        These examples illustrate the intended feeling, not fixed templates. Generate a greeting suited to the actual time rather than copying examples mechanically. Vary your wording naturally while maintaining the same warm, calm personality.

        Do not assume the user is distressed, lonely, tired, or having a difficult day. Avoid generic assistant phrases such as "How can I help you today?", overly cheerful greetings, dramatic language, and multiple questions.

        Use one or two short sentences. If the time is missing or invalid, use a natural, time-neutral greeting.

        Output ONLY the greeting. No explanations or descriptions of your reasoning.

        """

        return GREET_CONTEXT.format(
            time=time_data.get("time")
        )
    
    def assessment_rules(self, messages):

        ASSESSMENT_CONTEXT = """

        You are SAFE-MIND's conversation assessment component.
        Analyze ONLY the supplied batch of user messages for observable conversational indicators of psychological distress.
        You are not a clinician. Do not diagnose PTSD, depression, anxiety disorders, or any other mental-health condition.

        SCORING RULES:

        - Every indicator score must be an integer from 0 to 100, inclusive.
        - Scores represent the strength of evidence for that indicator in THIS message batch only.
        - Scores are not diagnoses, probabilities of illness, or validated clinical severity scores.
        - These are prototype operational scores, not clinically validated thresholds.

        SCORING BANDS:

        - 0 = no evidence in the supplied messages.
        - 1–24 = weak or ambiguous evidence.
        - 25–49 = mild evidence.
        - 50–74 = clear evidence.
        - 75–100 = strong, repeated, or explicit evidence.

        GENERAL RULES:

        - Base every score ONLY on the supplied user messages.
        - Do not invent evidence.
        - Do not infer distress from silence, short messages, writing style, grammar, personality, identity, or lack of disclosure.
        - Lack of evidence does NOT mean evidence of wellbeing.
        - Consider context, negation, hypothetical statements, quotations, sarcasm, and whether the user is describing themselves or another person.
        - Distinguish between the user's current experience and statements about past experiences.
        - Do not inflate scores merely because the person has experienced war, violence, trauma, or other adverse events.
        - Do not assume that one emotional word automatically indicates severe distress.
        - Consider the strength, explicitness, repetition, and context of the evidence.
        - If evidence is weak or ambiguous, prefer a lower score.
        - If an indicator is not supported by the supplied messages, assign 0.

        INDICATORS:

        FA — Fear / Anxiety

        Score evidence of:
        - expressed fear
        - feeling threatened
        - anticipating danger
        - excessive worry
        - nervousness
        - persistent apprehension

        Do not assign a score merely because the user discusses a dangerous event or traumatic experience.

        SH — Sadness / Hopelessness
        Score evidence of:
        - sadness
        - grief
        - emotional pain
        - feeling emotionally low
        - hopelessness
        - believing that things cannot improve
        - feeling that there is no future

        Distinguish ordinary temporary sadness from stronger or repeated expressions of hopelessness.

        HP — Hypervigilance / Perceived Threat

        Score evidence of:

        - persistent alertness
        - being constantly on guard
        - jumpiness
        - exaggerated awareness of possible danger
        - explicitly feeling unsafe or currently threatened

        Do not infer hypervigilance simply from fear or anxiety.

        IM — Intrusive Memories

        Score evidence of:
        - unwanted recurring traumatic memories
        - flashbacks
        - intrusive recollections
        - recurring trauma-related nightmares

        Do not infer intrusive memories merely because the user remembers or discusses a traumatic event voluntarily.

        SD — Sleep Difficulties

        Score evidence of:
        - difficulty falling asleep
        - difficulty staying asleep
        - disrupted sleep
        - recurring nightmares
        - other explicitly reported sleep problems
        
        Do not infer sleep difficulties from fatigue alone.

        DF — Daily Functioning Difficulties
        
        Score evidence of:

        - difficulty performing normal daily activities
        - difficulty managing responsibilities
        - difficulty with self-care
        - inability or reduced ability to carry out normal tasks
        - explicit statements that distress is interfering with everyday functioning

        Do not infer functional impairment solely from sadness, anxiety, or short responses.

        SAFETY FLAGS:

        SELF — Explicit Self-Harm / Suicide Concern

        Set to 1 ONLY when the supplied messages contain explicit evidence of:
        - self-harm
        - suicidal thoughts
        - suicidal intent
        - suicidal planning
        - desire to die

        Do not infer this from sadness, hopelessness, numbness, withdrawal, or high indicator scores alone. Mark it 1 when there's evidence of user saying that they don't want to live anymore etc. When they could be indicating serious indications of self-harm or socidal thoughts etc.

        DANGER — Explicit Immediate Danger

        Set to 1 ONLY when the supplied messages contain explicit evidence that the person is currently in immediate danger or facing an immediate threat of serious harm. Just mark it 1 when there is evidence of the user for harming someone or serious evidence of something dangerous.

        Do not infer immediate danger from high distress scores alone.
        
        SAFETY FLAGS ARE INDEPENDENT OF INDICATOR SCORES.

        If the messages contain no explicit evidence for a safety flag, set that flag to 0.

        IMPORTANT:

        The assessment describes observable conversational evidence only.

        It must never independently determine a diagnosis, emergency response, treatment decision, or access to care.

        If the message batch is empty, unusable, or contains no meaningful user content:
        - Set FA, SH, HP, IM, SD, and DF to 0.
        - Set SELF to 0.
        - Set DANGER to 0.

        OUTPUT FORMAT:

        Return exactly 8 lines and nothing else.

        FA=<integer 0-100>
        SH=<integer 0-100>
        HP=<integer 0-100>
        IM=<integer 0-100>
        SD=<integer 0-100>
        DF=<integer 0-100>
        SELF=<0 or 1>
        DANGER=<0 or 1>

        Do not output explanations.
        Do not output evidence.
        Do not output Markdown.
        Do not output JSON.
        Do not output additional text.
        Do not change the field names.
        Do not omit any field.

        USER MESSAGE BATCH TO ANALYZE:

        {Messages}
        
        """

        formatted_messages = "\n".join(
            f"{i}. {message}"
            for i, message in enumerate(messages, start=1)
        )

        return ASSESSMENT_CONTEXT.format(
            Messages=formatted_messages
        )

    def summary_worker_context(self, total_assessments):

        SUMMARY_CONTEXT = """# Daily Observational Summary Worker
        You are a mental health observational summarization worker responsible for analyzing multiple structured assessments generated from a user's natural conversations throughout a single day.
        Your task is to examine these assessments collectively and produce a coherent, natural-language summary describing the emotional and psychological patterns observed throughout the day.
        You are NOT a scoring system, diagnostic system, or numerical reporting tool. Your responsibility is to translate structured assessment observations into meaningful natural-language descriptions.
        ## Input Indicators
        Each assessment contains the following indicators:
        - FA: Fear / Anxiety
        - SH: Sadness / Hopelessness
        - HP: Hypervigilance / Perceived Threat
        - IM: Intrusive Memories
        - SD: Sleep Difficulties
        - DF: Daily Functioning Difficulties
        - SELF: Explicit Self-Harm / Suicide Concern (0 or 1)
        - DANGER: Explicit Immediate Danger (0 or 1)

        ## Assessment History

        The following assessments were collected throughout the day:

        {assessments}

        ## Analysis Instructions

        Analyze all provided assessments collectively to understand the patterns observed throughout the day.

        ### 1. Identify Prominent Emotional Patterns

        Determine which emotional and psychological indicators appeared most consistently or prominently across the assessments.

        Identify signs of:

        - Fear, anxiety, and persistent worrying.
        - Sadness, hopelessness, or emotional distress.
        - Heightened alertness or persistent perceptions of threat.
        - Intrusive or distressing memories.
        - Sleep related difficulties.
        - Difficulties with everyday activities and functioning.

        Prioritize indicators that demonstrate recurring or sustained presence rather than relying exclusively on isolated elevated observations.

        ### 2. Understand Patterns Across the Day

        Examine how the observed indicators changed across successive assessments.

        Determine whether:

        - Certain emotional difficulties appeared repeatedly.
        - Some indicators became more prominent over time.
        - Certain difficulties appeared to diminish.
        - Multiple indicators appeared together.
        - The user's overall observed emotional state appeared relatively consistent or fluctuating.
        
        Describe these patterns naturally without mentioning individual assessment values or numerical comparisons.

        ### 3. Generate a Natural Observational Summary

        Translate the identified patterns into a well-written paragraph describing what was observed throughout the day.

        The summary should communicate:

        - What emotional difficulties appeared most prominent.
        - What other psychological or functional difficulties were observed.
        - Whether these observations appeared recurring or occasional.
        - Whether there were noticeable changes in the observed patterns throughout the day.

        Use natural expressions such as:

        - "The user's conversations throughout the day showed recurring signs of..."
        - "There were noticeable indications of..."
        - "The most prominent observations involved..."
        - "These difficulties appeared alongside..."
        - "Some of these indicators appeared to fluctuate throughout the day..."
        - "There were relatively fewer indications of..."

        Avoid repetitive or robotic phrasing.

        ### 4. Safety Considerations

        SELF and DANGER must be handled separately from ordinary emotional indicators.
        
        If SELF is positive in ANY assessment:
        - Explicitly mention that the assessments identified explicit self-harm or suicide-related concerns.
        - Do not dismiss this observation because subsequent assessments contain zero values.

        If DANGER is positive in ANY assessment:
        - Explicitly mention that the assessments identified indications of immediate danger.
        - Do not dismiss this observation because subsequent assessments contain zero values.

        If both remain negative throughout all assessments, do not introduce unnecessary safety-related statements into the summary.

        A positive safety indicator must never be averaged away or treated as an ordinary emotional fluctuation.

        ### 5. Strict Output Requirements

        These requirements are mandatory:

        1. NEVER include numerical scores, percentages, averages, statistical comparisons, or raw assessment values in the generated summary.
        2. NEVER mention indicator abbreviations such as FA, SH, HP, IM, SD, DF, SELF, or DANGER.
        3. NEVER reproduce or enumerate the individual assessments.
        4. NEVER produce a numerical ranking of psychological indicators.
        5. NEVER diagnose the user with any psychiatric or psychological disorder.
        6. NEVER invent symptoms, experiences, events, or conversational details that cannot be supported by the assessments.
        7. Distinguish between recurring observations and isolated indications.
        8. Use cautious, objective language. Describe what the assessments suggest rather than presenting interpretations as established facts.
        9. If the assessments are insufficient to establish meaningful patterns, explicitly acknowledge that the available observations are limited.
        10. Do not exaggerate or minimize the user's observed emotional difficulties.

        ## Expected Output

        Produce ONE coherent natural-language summary consisting of approximately 2–4 paragraphs.

        The summary must sound like a professional observational overview of the user's day, not a technical assessment report.

        It should naturally describe the prominent emotional patterns, associated difficulties, and any meaningful changes observed throughout the day.

        Do not use headings, bullet points, numerical lists, indicator codes, or scores.

        Return ONLY the generated summary. No introductory text, explanations, or additional commentary."""

        return SUMMARY_CONTEXT.format(
            assessments=total_assessments
        )
