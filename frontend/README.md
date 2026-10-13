# SAFE-MIND Chat UI

A minimal, local-first chat client for the SAFE-MIND Python service.

## Run locally

```bash
npm install
cp .env.example .env.local
npm run dev
```

The frontend posts `{ "message": "..." }` to `NEXT_PUBLIC_API_URL/chat`. The default API base URL is `http://localhost:8000`. The endpoint should return an SSE stream with `data: {"delta":"..."}` events and may finish with `data: [DONE]`.

The microphone button captures audio in the browser and stops its tracks when turned off. The `MediaRecorder` stop handler is the marked integration point for a future local transcription endpoint; no transcription or model logic is included in this frontend.
