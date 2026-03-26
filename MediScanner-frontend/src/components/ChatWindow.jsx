import { useState, useRef, useEffect } from 'react'
import MessageBubble from './MessageBubble'

export default function ChatWindow({ apiUrl, sessionId, messages, setMessages, initialized, setInitialized, answerMode, setAnswerMode }) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [speakingIdx, setSpeakingIdx] = useState(null)
  const [listening, setListening] = useState(false)
  const [voicePopup, setVoicePopup] = useState(false)
  const [voiceText, setVoiceText] = useState('')
  const messagesEndRef = useRef(null)
  const synthRef = useRef(window.speechSynthesis)
  const recognitionRef = useRef(null)

  const startRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return
    const recognition = new SpeechRecognition()
    recognition.lang = 'ko-KR'
    recognition.continuous = false
    recognition.interimResults = false
    recognitionRef.current = recognition
    recognition.onstart = () => setListening(true)
    recognition.onresult = (e) => setVoiceText(e.results[0][0].transcript)
    recognition.onend = () => setListening(false)
    recognition.onerror = () => setListening(false)
    recognition.start()
  }

  // 음성 입력
  const handleVoice = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) { alert('이 브라우저는 음성 입력을 지원하지 않아요. Edge 또는 Chrome을 사용해주세요.'); return }
    setVoicePopup(true)
    setVoiceText('')
    startRecognition()
  }

  const handleVoiceConfirm = async () => {
    const text = voiceText.trim()
    recognitionRef.current?.stop()
    setVoicePopup(false)
    setVoiceText('')
    if (!text) return
    try {
      const res = await fetch(`${apiUrl}/api/voice-correct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      const data = await res.json()
      const corrected = data.corrected || text
      setInput(corrected)
      setTimeout(() => document.getElementById('mediscanner-send-btn')?.click(), 50)
    } catch {
      setInput(text)
      setTimeout(() => document.getElementById('mediscanner-send-btn')?.click(), 50)
    }
  }

  const handleVoiceCancel = () => {
    recognitionRef.current?.stop()
    setVoicePopup(false)
    setVoiceText('')
    setListening(false)
  }
  useEffect(() => {
    if (initialized) return
    const loadGreeting = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/profile/${sessionId}`)
        const data = await res.json()
        if (data.status === 'ok' && data.profile && data.profile.age) {
          const p = data.profile
          setMessages([{ role: 'assistant', text: '안녕하세요! 메디스캐너입니다 😊\n무엇이 궁금하세요?', profileDiseases: p.diseases || '' }])
        } else {
          setMessages([{ role: 'assistant', text: '안녕하세요! 메디스캐너입니다\n건강 관련 질문을 해주세요 😊' }])
        }
      } catch (e) {
        setMessages([{ role: 'assistant', text: '안녕하세요! 메디스캐너입니다\n건강 관련 질문을 해주세요 😊' }])
      }
      setInitialized(true)
    }
    loadGreeting()
  }, [apiUrl, initialized, setInitialized, setMessages])

  // 언마운트 시 TTS 중지
  useEffect(() => { return () => { synthRef.current.cancel() } }, [])

  // 메시지 수 변경 시 스크롤
  const prevMsgLenRef = useRef(0)
  useEffect(() => {
    if (messages.length !== prevMsgLenRef.current) {
      prevMsgLenRef.current = messages.length
      messagesEndRef.current?.scrollIntoView({ behavior: 'instant' })
    }
  }, [messages])

  // 로딩 시작 시 스크롤
  useEffect(() => {
    if (loading) setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'instant' }), 50)
  }, [loading])

  // TTS
  const handleSpeak = (text, idx) => {
    const synth = synthRef.current
    if (!synth) return
    if (speakingIdx === idx) { synth.cancel(); setSpeakingIdx(null); return }
    synth.cancel()
    setSpeakingIdx(null)

    const cleanText = text
      .replace(/⚠️|❌|💊|🔊|🏥|😊|※/g, '')
      .replace(/\(출처:[^)]*\)/g, '')
      .replace(/[①②③④⑤⑥⑦⑧]/g, '')
      .replace(/\n+/g, ' ')
      .trim()
    if (!cleanText) return

    const speak = () => {
      const utter = new SpeechSynthesisUtterance(cleanText)
      const voices = synth.getVoices()
      const koVoice = voices.find(v => v.lang.startsWith('ko'))
      if (koVoice) utter.voice = koVoice
      utter.lang = 'ko-KR'
      utter.rate = 0.9
      utter.pitch = 1.0
      utter.volume = 1.0
      utter.onend = () => setSpeakingIdx(null)
      utter.onerror = () => setSpeakingIdx(null)
      setSpeakingIdx(idx)
      synth.speak(utter)
    }

    if (synth.getVoices().length === 0) {
      synth.onvoiceschanged = () => { synth.onvoiceschanged = null; speak() }
    } else {
      speak()
    }
  }

  // 인사말 로드
  const handleSend = async () => {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: userMsg }, { role: 'assistant', text: '', isLoading: true }])
    setLoading(true)
    try {
      const res = await fetch(`${apiUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg, answer_mode: answerMode, user_id: sessionId }),
      })
      if (!res.ok) throw new Error('서버 오류')
      const data = await res.json()
      setMessages(prev => [
        ...prev.filter(m => !m.isLoading),
        {
          role: 'assistant', text: data.answer, sources: data.sources || [],
          detected_drugs: data.drug_names_detected || data.detected_drugs || [],
          question_type: data.question_type || 'medical',
          has_drug_api: data.has_drug_api || false, tokens: data.tokens || {},
          answer_mode: answerMode,
        }
      ])
    } catch (err) {
      setMessages(prev => [...prev.filter(m => !m.isLoading), { role: 'assistant', text: '죄송합니다. 일시적으로 오류가 발생했습니다. 다시 시도해주세요.' }])
    } finally { setLoading(false) }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  return (
    <div className="flex flex-col h-full">

      {/* 메시지 영역 */}
      <div className="flex-1 overflow-y-auto px-4 py-4" style={{ background: 'linear-gradient(180deg, #FFFDF5, #FFF9EA)' }}>
        {messages.map((msg, i) => (
          <div key={i}>
            {msg.isLoading ? (
              <div className="flex gap-2 mb-4">
                <div className="shrink-0 flex items-center justify-center"
                  style={{ width: 34, height: 34, background: 'linear-gradient(145deg, #FFD700, #B8860B)', borderRadius: '50%', fontSize: 16 }}>
                  🏥
                </div>
                <div style={{ background: 'white', border: '1px solid #E8DCC0', borderRadius: '18px 18px 18px 4px', padding: '13px 16px' }}>
                  <div className="flex items-center gap-2">
                    <span style={{ fontSize: 20 }}>🤔</span>
                    <div className="flex gap-1">
                      <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '0ms' }} />
                      <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '150ms' }} />
                      <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <>
                {msg.role === 'assistant' && msg.text && i > 0 && (
                  <div className="flex items-center gap-2 mb-1 ml-11">
                    {msg.answer_mode && (
                      <span style={{
                        fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 10,
                        background: msg.answer_mode === 'simple' ? '#E8F5E9' : '#E3F2FD',
                        color: msg.answer_mode === 'simple' ? '#2E7D32' : '#1565C0',
                        border: msg.answer_mode === 'simple' ? '1px solid #A5D6A7' : '1px solid #90CAF9',
                      }}>
                        {msg.answer_mode === 'simple' ? '간단' : '상세'}
                      </span>
                    )}
                    <button onClick={() => handleSpeak(msg.text, i)} className="px-2.5 py-1 rounded-full transition-all"
                      style={{
                        fontSize: 12, fontWeight: 600,
                        background: speakingIdx === i ? 'linear-gradient(135deg, #FFD700, #DAA520)' : 'rgba(218,165,32,0.08)',
                        color: speakingIdx === i ? '#1A1206' : '#B8860B',
                        border: speakingIdx === i ? '1px solid #DAA520' : '1px solid rgba(218,165,32,0.2)',
                      }}>
                      {speakingIdx === i ? '⏹ 멈춤' : '🔊 읽기'}
                    </button>
                  </div>
                )}
                <MessageBubble message={msg} />
              </>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* 간단/상세 토글 */}
      <div className="flex items-center gap-1.5 px-4 py-2 shrink-0" style={{ background: 'linear-gradient(180deg, #FFF8E0, #FFF3D0)', borderTop: '1px solid #E0D0A0' }}>
        <button onClick={() => {
          if (answerMode === 'simple') {
            const q = messages.filter(m => m.role === 'user').pop()
            if (q) setInput(q.text)
          } else {
            setAnswerMode('simple')
          }
        }} className="font-semibold px-3 py-1.5 rounded-full"
          style={{ fontSize: 13, background: answerMode === 'simple' ? 'linear-gradient(135deg, #FFD700, #DAA520)' : 'rgba(255,215,0,0.1)', color: answerMode === 'simple' ? '#1A1206' : '#B8860B', border: answerMode === 'simple' ? 'none' : '1px solid rgba(218,165,32,0.2)' }}>간단</button>
        <button onClick={() => {
          if (answerMode === 'detailed') {
            const q = messages.filter(m => m.role === 'user').pop()
            if (q) setInput(q.text)
          } else {
            setAnswerMode('detailed')
          }
        }} className="font-semibold px-3 py-1.5 rounded-full"
          style={{ fontSize: 13, background: answerMode === 'detailed' ? 'linear-gradient(135deg, #FFD700, #DAA520)' : 'rgba(255,215,0,0.1)', color: answerMode === 'detailed' ? '#1A1206' : '#B8860B', border: answerMode === 'detailed' ? 'none' : '1px solid rgba(218,165,32,0.2)' }}>상세</button>
        {loading && (
          <div className="flex items-center gap-1.5 ml-auto">
            <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '0ms' }} />
            <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '150ms' }} />
            <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '300ms' }} />
            <span style={{ fontSize: 12, color: '#8B6914', fontWeight: 600 }}>검색 중...</span>
          </div>
        )}
      </div>

      {/* 음성 입력 팝업 */}
      {voicePopup && (
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <div style={{ background: 'white', borderRadius: 20, padding: 20, width: '100%', maxWidth: 340, boxShadow: '0 10px 40px rgba(0,0,0,0.3)' }}>
            <div className="flex items-center gap-2 mb-3">
              <span style={{ fontSize: 22 }}>🎤</span>
              <p style={{ fontSize: 16, fontWeight: 700, color: '#2A1D08' }}>음성 입력</p>
              {listening && <span className="ml-auto" style={{ fontSize: 12, color: '#E65100', fontWeight: 600 }}>● 듣는 중...</span>}
            </div>

            <textarea
              value={voiceText}
              onChange={(e) => setVoiceText(e.target.value)}
              placeholder={listening ? '말씀해 주세요...' : '음성이 여기에 표시됩니다. 수정도 가능해요.'}
              style={{ width: '100%', minHeight: 100, padding: '10px 12px', borderRadius: 12, border: '1.5px solid #E0D0A0', fontSize: 15, fontWeight: 500, color: '#2A1D08', background: '#FFFDF5', resize: 'none', outline: 'none', lineHeight: 1.6 }}
            />

            <div className="flex gap-2 mt-3">
              <button onClick={startRecognition} disabled={listening}
                className="flex-1 py-2.5 rounded-full font-bold"
                style={{ fontSize: 13, background: listening ? '#E0D0A0' : '#FFF8E0', border: '1px solid #E0D0A0', color: '#8B6914', cursor: listening ? 'not-allowed' : 'pointer' }}>
                🎤 다시 말하기
              </button>
              <button onClick={handleVoiceCancel}
                className="py-2.5 px-4 rounded-full font-medium"
                style={{ fontSize: 13, background: '#FFF8E0', border: '1px solid #E0D0A0', color: '#8B6914' }}>
                취소
              </button>
              <button onClick={handleVoiceConfirm} disabled={!voiceText.trim()}
                className="flex-1 py-2.5 rounded-full font-bold"
                style={{ fontSize: 13, background: voiceText.trim() ? 'linear-gradient(135deg, #FFD700, #DAA520)' : '#E0D0A0', color: '#1A1206', opacity: voiceText.trim() ? 1 : 0.6 }}>
                확인
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 입력창 */}
      <div className="flex items-center gap-2 px-4 py-2.5 shrink-0" style={{ background: 'white', borderTop: '1px solid #E0D0A0' }}>
        <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
          placeholder="증상이나 건강 질문을 입력하세요.."
          className="flex-1 outline-none"
          style={{ border: '1.5px solid #E0D0A0', borderRadius: 22, padding: '11px 16px', fontSize: 14, fontWeight: 500, background: '#FFFDF5' }} />
        <button onClick={handleVoice} className="shrink-0 flex items-center justify-center"
          style={{ width: 38, height: 38, borderRadius: '50%', border: 'none', cursor: 'pointer',
            background: listening ? 'linear-gradient(145deg, #FF4444, #CC2222)' : 'linear-gradient(145deg, #FFF3D0, #FFE090)',
            boxShadow: '0 2px 8px rgba(218,165,32,0.3)',
          }}>
          <span style={{ fontSize: 22 }}>🎤</span>
        </button>
        <button id="mediscanner-send-btn" onClick={handleSend} disabled={loading || !input.trim()} className="shrink-0 flex items-center justify-center"
          style={{ width: 38, height: 38, background: 'linear-gradient(145deg, #FFD700, #DAA520, #B8860B)', borderRadius: '50%', boxShadow: '0 2px 10px rgba(255,215,0,0.35)', opacity: loading || !input.trim() ? 0.5 : 1 }}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1A1206" strokeWidth="3">
            <path d="M22 2L11 13" /><path d="M22 2L15 22L11 13L2 9L22 2Z" />
          </svg>
        </button>
      </div>

    </div>
  )
}
