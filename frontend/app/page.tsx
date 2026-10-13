'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { startVoiceAudio } from './voice-audio'

type Role = 'user' | 'assistant'
type Message = { id: number; role: Role; content: string; streaming?: boolean }

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [micError, setMicError] = useState('')
  const [chatError, setChatError] = useState('')
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [voiceAssistant, setVoiceAssistant] = useState(false)
  const [speakingId, setSpeakingId] = useState<number | null>(null)
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const voiceStreamRef = useRef<MediaStream | null>(null)
  const voiceSocketRef = useRef<WebSocket | null>(null)
  const stopVoiceAudioRef = useRef<(() => Promise<void>) | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const nextId = useRef(1)

  useEffect(() => {
    const container = scrollRef.current
    if (container) container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
  }, [messages, isSending])

  const stopMicrophone = useCallback(() => {
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') recorder.stop()
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    mediaRecorderRef.current = null
    mediaStreamRef.current = null
    setIsListening(false)
  }, [])

  useEffect(() => () => {
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') recorder.stop()
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    void stopVoiceAudioRef.current?.()
    voiceStreamRef.current?.getTracks().forEach((track) => track.stop())
    voiceSocketRef.current?.close()
  }, [])

  function updateMessage(id: number, content: string, streaming?: boolean) {
    setMessages((current) => current.map((message) => message.id === id
      ? { ...message, content, ...(streaming === undefined ? {} : { streaming }) }
      : message))
  }

  async function sendMessage() {
    const text = input.trim()
    if (!text || isSending || isListening) return
    setInput('')
    setChatError('')
    if (inputRef.current) inputRef.current.style.height = 'auto'
    const userId = nextId.current++
    const assistantId = nextId.current++
    setMessages((current) => [...current,
      { id: userId, role: 'user', content: text },
      { id: assistantId, role: 'assistant', content: '', streaming: true },
    ])
    setIsSending(true)
    let assistantText = ''
    try {
      const response = await fetch(`${API_URL.replace(/\/$/, '')}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ message: text }),
      })
      if (!response.ok) throw new Error(`Chat service returned ${response.status}.`)
      if (!response.body) throw new Error('The chat service returned no response stream.')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let doneEvent = false

      const consumeEvent = (event: string) => {
        const data = event.split(/\r?\n/)
          .filter((line) => line.startsWith('data:'))
          .map((line) => line.slice(5).replace(/^ /, ''))
          .join('\n')
        if (!data) return
        if (data.trim() === '[DONE]') { doneEvent = true; return }
        let delta: string
        try {
          const parsed: unknown = JSON.parse(data)
          if (typeof parsed === 'object' && parsed !== null && 'delta' in parsed && typeof parsed.delta === 'string') {
            delta = parsed.delta
          } else {
            return
          }
        } catch {
          delta = data
        }
        if (delta) {
          assistantText += delta
          updateMessage(assistantId, assistantText, true)
        }
      }

      while (!doneEvent) {
        const { value, done } = await reader.read()
        buffer += decoder.decode(value, { stream: !done })
        // SSE events end at a blank line; accept LF and CRLF, including boundaries split across chunks.
        const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
        const events = normalized.split('\n\n')
        buffer = events.pop() ?? ''
        for (const event of events) {
          consumeEvent(event)
          if (doneEvent) break
        }
        if (done) {
          if (buffer.trim()) consumeEvent(buffer)
          break
        }
      }
      if (!assistantText.trim()) {
        updateMessage(assistantId, 'The chat service returned an empty response. Please try again.', false)
      } else {
        updateMessage(assistantId, assistantText, false)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to connect to the chat service.'
      updateMessage(assistantId, 'I couldn’t connect to Safe Mind. Check that the local service is running, then try again.', false)
      setChatError(message)
    } finally {
      setIsSending(false)
    }
  }

  async function toggleMicrophone() {
    setMicError('')
    if (isListening) { stopMicrophone(); return }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setMicError('Microphone recording is not supported in this browser.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data) }
      recorder.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        if (!audioBlob.size) return
        const form = new FormData()
        form.append('audio', audioBlob, 'speech.webm')
        try {
          const response = await fetch(`${API_URL.replace(/\/$/, '')}/stt`, { method: 'POST', body: form })
          if (!response.ok) throw new Error('Speech transcription failed.')
          const result = await response.json() as { text?: string }
          if (result.text?.trim()) setInput((current) => `${current}${current ? ' ' : ''}${result.text?.trim()}`)
          else setMicError('I didn’t catch that. Try speaking again.')
        } catch {
          setMicError('Could not transcribe audio. Check that the local service is running.')
        }
      }
      recorder.start()
      mediaStreamRef.current = stream
      mediaRecorderRef.current = recorder
      setIsListening(true)
    } catch {
      setMicError('Microphone permission was denied or the microphone is unavailable.')
      stopMicrophone()
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendMessage() }
  }

  function newConversation() {
    setMessages([])
    setChatError('')
    setIsSidebarOpen(false)
  }

  async function toggleVoiceAssistant() {
    if (voiceAssistant) {
      await stopVoiceAudioRef.current?.()
      stopVoiceAudioRef.current = null
      voiceStreamRef.current = null
      voiceSocketRef.current?.close()
      voiceSocketRef.current = null
      setVoiceAssistant(false)
      return
    }
    setChatError('')
    if (!navigator.mediaDevices?.getUserMedia || typeof AudioWorkletNode === 'undefined') {
      setChatError('Live voice is not supported in this browser.')
      return
    }
    let stream: MediaStream | null = null
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } })
      const configuredUrl = process.env.NEXT_PUBLIC_VOICE_WS_URL
      const socketUrl = configuredUrl ?? `${API_URL.replace(/^http/, 'ws').replace(/\/$/, '')}/voice`
      const socket = new WebSocket(socketUrl)
      socket.binaryType = 'arraybuffer'
      voiceSocketRef.current = socket
      await new Promise<void>((resolve, reject) => {
        socket.onopen = () => resolve()
        socket.onerror = () => reject(new Error('WebSocket connection failed.'))
        socket.onclose = () => {
          if (voiceSocketRef.current === socket) {
            voiceSocketRef.current = null
            void stopVoiceAudioRef.current?.()
            stopVoiceAudioRef.current = null
            voiceStreamRef.current?.getTracks().forEach((track) => track.stop())
            voiceStreamRef.current = null
            setVoiceAssistant(false)
          }
        }
      })
      stopVoiceAudioRef.current = await startVoiceAudio(stream, (frame) => {
        if (socket.readyState === WebSocket.OPEN) socket.send(frame)
      })
      voiceStreamRef.current = stream
      setVoiceAssistant(true)
    } catch {
      stream?.getTracks().forEach((track) => track.stop())
      voiceStreamRef.current = null
      voiceSocketRef.current?.close()
      voiceSocketRef.current = null
      setVoiceAssistant(false)
      setChatError('Could not start live voice. Check microphone permission and the voice WebSocket service.')
    }
  }

  async function speakMessage(message: Message) {
    if (speakingId === message.id) { setSpeakingId(null); return }
    setSpeakingId(message.id)
    try {
      const response = await fetch(`${API_URL.replace(/\/$/, '')}/tts`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: message.content }),
      })
      if (!response.ok) throw new Error()
      const url = URL.createObjectURL(await response.blob())
      const audio = new Audio(url)
      audio.onended = () => { URL.revokeObjectURL(url); setSpeakingId(null) }
      audio.onerror = () => { URL.revokeObjectURL(url); setSpeakingId(null); setChatError('Could not play generated speech.') }
      await audio.play()
    } catch {
      setSpeakingId(null)
      setChatError('Could not generate speech. Check the TTS service and try again.')
    }
  }

  return (
    <main className={`safe-mind-shell theme-${theme}`}>
      <header className="topbar">
        <div className="brand-wrap">
          <button className="icon-button mobile-menu" onClick={() => setIsSidebarOpen((open) => !open)} aria-label="Toggle sidebar" aria-expanded={isSidebarOpen}><MenuIcon /></button>
          <div className="brand-mark" aria-hidden="true"><BrainIcon /></div>
          <div><div className="brand-name">Safe Mind</div><div className="brand-subtitle">A space to untangle your thoughts</div></div>
        </div>
        <div className="header-actions">
          <button className="theme-toggle" onClick={() => setTheme((current) => current === 'light' ? 'dark' : 'light')} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`} title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}>{theme === 'light' ? <MoonIcon /> : <SunIcon />}</button>
          <button className={`assistant-toggle ${voiceAssistant ? 'enabled' : ''}`} onClick={() => void toggleVoiceAssistant()} aria-pressed={voiceAssistant}><span className="toggle-indicator" />{voiceAssistant ? 'Voice on' : 'Voice assistant'}</button>
        </div>
      </header>
      <div className="workspace">
        {isSidebarOpen && <button className="sidebar-backdrop" aria-label="Close sidebar" onClick={() => setIsSidebarOpen(false)} />}
        <aside className={`sidebar ${isSidebarOpen ? 'sidebar-open' : ''}`}>
          <button className="new-chat" onClick={newConversation}><PlusIcon />New conversation</button>
          {messages.length > 0 && <><div className="sidebar-section-label">Today</div><button className="conversation active"><span className="conversation-dot" /><span className="conversation-copy"><strong>Current conversation</strong><small>Just now</small></span></button></>}
          <div className="sidebar-spacer" />
          <div className="privacy-card"><LockIcon /><div><strong>Your conversation stays private.</strong><p>Designed for local-first, privacy-focused support.</p></div></div>
        </aside>
        <section className="chat-panel">
          <div className="chat-scroll" ref={scrollRef}>
            {messages.length === 0 && <div className="chat-intro"><div className="intro-orb"><BrainIcon /></div><span className="eyebrow">A MOMENT FOR YOU</span><h1>What&apos;s on your mind?</h1><p>Take your time. Start wherever feels right.</p></div>}
            <div className="message-stack">
              {messages.map((message) => <div key={message.id} className={`message-row ${message.role}`}>
                {message.role === 'assistant' && <div className="avatar assistant-avatar"><PulseIcon /></div>}
                <div className="message-content"><div className={`bubble ${message.role}`}>{message.content || (message.streaming ? <span className="typing-dots"><i /><i /><i /></span> : null)}</div>{message.role === 'assistant' && message.content && !message.streaming && <button className={`speak-button ${speakingId === message.id ? 'speaking' : ''}`} onClick={() => void speakMessage(message)} title="Listen to this response" aria-label="Listen to this response"><SpeakerIcon /></button>}</div>
              </div>)}
            </div>
          </div>
          <div className="composer-area">
            {micError && <div className="mic-error" role="status">{micError}</div>}
            {chatError && <div className="chat-error" role="status">{chatError}</div>}
            {isListening && <div className="listening-bar" role="status"><span className="live-dot" />Listening…<span className="wave"><i /><i /><i /><i /><i /></span><button onClick={stopMicrophone}>Turn off</button></div>}
            <div className="composer">
              <textarea ref={inputRef} value={input} onChange={(event) => { setInput(event.target.value); event.currentTarget.style.height = 'auto'; event.currentTarget.style.height = `${Math.min(event.currentTarget.scrollHeight, 160)}px` }} onKeyDown={handleKeyDown} rows={1} placeholder={isListening ? 'Speak naturally…' : 'Tell me what’s on your mind…'} disabled={isListening} aria-label="Message Safe Mind" />
              <div className="composer-actions">
                <button className={`voice-button ${isListening ? 'recording' : ''}`} onClick={() => void toggleMicrophone()} aria-label={isListening ? 'Turn microphone off' : 'Turn microphone on'} title={isListening ? 'Turn microphone off' : 'Use voice'}><MicIcon /></button>
                <button className="send-button" onClick={() => void sendMessage()} disabled={!input.trim() || isSending || isListening} aria-label="Send message"><ArrowUpIcon /></button>
              </div>
            </div>
            <div className="composer-hint">Enter to send · Shift + Enter for a new line</div>
          </div>
        </section>
      </div>
    </main>
  )
}

function PulseIcon() { return <svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M5 17h5l2.4-7 4.2 14 2.6-9H27" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" /></svg> }
function BrainIcon() { return <svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M15.8 7.2a4 4 0 0 0-7.4 2 4.3 4.3 0 0 0-2.2 7.4 4 4 0 0 0 2.3 6.8 3.9 3.9 0 0 0 7.3 1.8V7.2Zm.4 0a4 4 0 0 1 7.4 2 4.3 4.3 0 0 1 2.2 7.4 4 4 0 0 1-2.3 6.8 3.9 3.9 0 0 1-7.3 1.8V7.2Z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/><path d="M10 12c2 0 3 1.2 3 3m-3 4c2 0 3-1 3-3m9-4c-2 0-3 1.2-3 3m3 4c-2 0-3-1-3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg> }
function SpeakerIcon() { return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 10v4h4l5 4V6l-5 4H4Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"/><path d="M16 9a4 4 0 0 1 0 6m2.5-8.5a7.5 7.5 0 0 1 0 11" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg> }
function MoonIcon() { return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20.3 15.4A8.5 8.5 0 0 1 8.6 3.7 8.6 8.6 0 1 0 20.3 15.4Z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg> }
function SunIcon() { return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.7"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg> }
function MicIcon() { return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="8" y="3" width="8" height="12" rx="4" stroke="currentColor" strokeWidth="1.8" /><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M8.5 21h7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg> }
function ArrowUpIcon() { return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 19V5M6.5 10.5 12 5l5.5 5.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg> }
function MenuIcon() { return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg> }
function PlusIcon() { return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg> }
function LockIcon() { return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="5" y="10" width="14" height="10" rx="2.2" stroke="currentColor" strokeWidth="1.8" /><path d="M8 10V7.5a4 4 0 0 1 8 0V10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg> }
