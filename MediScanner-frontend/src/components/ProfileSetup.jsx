import { useState, useRef } from 'react'

const COMMON_DISEASES = [
  '고혈압', '당뇨병', '관절염', '골다공증',
  '치매', '폐질환', '심장질환', '만성신장병',
]

export default function ProfileSetup({ apiUrl, sessionId, onComplete, onSkip, onExit }) {
  const [age, setAge] = useState('')
  const [selectedDiseases, setSelectedDiseases] = useState([])
  const [customDisease, setCustomDisease] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [medications, setMedications] = useState('')
  const [saving, setSaving] = useState(false)
  const [fadeOut, setFadeOut] = useState(false)
  const [ocrLoading, setOcrLoading] = useState(false)
  const [submitActive, setSubmitActive] = useState(false)
  const [skipActive, setSkipActive] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const fileInputRef = useRef(null)
  const recognitionRef = useRef(null)

  const toggleDisease = (disease) => {
    setSelectedDiseases(prev =>
      prev.includes(disease) ? prev.filter(d => d !== disease) : [...prev, disease]
    )
  }

  const addCustomDisease = () => {
    const trimmed = customDisease.trim()
    if (trimmed && !selectedDiseases.includes(trimmed)) {
      setSelectedDiseases(prev => [...prev, trimmed])
    }
    setCustomDisease('')
    setShowCustomInput(false)
  }

  const handleVoiceMed = () => {
    if (isListening) {
      recognitionRef.current?.stop()
      setIsListening(false)
      return
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) { alert('이 브라우저는 음성 인식을 지원하지 않습니다.'); return }
    const recognition = new SpeechRecognition()
    recognition.lang = 'ko-KR'
    recognition.continuous = false
    recognition.interimResults = false
    recognition.onstart = () => setIsListening(true)
    recognition.onresult = (e) => {
      const transcript = e.results[0][0].transcript.replace(/[.。]/g, '').trim()
      setMedications(prev => prev ? `${prev}, ${transcript}` : transcript)
    }
    recognition.onend = () => setIsListening(false)
    recognition.onerror = () => setIsListening(false)
    recognitionRef.current = recognition
    recognition.start()
  }

  const handleMedOCR = (e) => {
    const file = e.target.files[0]
    if (!file) return
    setOcrLoading(true)

    const reader = new FileReader()
    reader.onload = async (ev) => {
      const base64 = ev.target.result.split(',')[1]
      try {
        const res = await fetch(`${apiUrl}/api/camera/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image_base64: base64, user_id: 'default' }),
        })
        const data = await res.json()
        if (data.drug_names && data.drug_names.length > 0) {
          const existing = medications.trim()
          const newMeds = existing ? `${existing}, ${data.drug_names.join(', ')}` : data.drug_names.join(', ')
          setMedications(newMeds)
        }
      } catch (err) {
        console.log('OCR 실패')
      }
      setOcrLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
    reader.readAsDataURL(file)
  }

  const handleSubmit = async () => {
    setSaving(true)
    try {
      await fetch(`${apiUrl}/api/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: sessionId,
          name: '',
          age: parseInt(age) || 0,
          diseases: selectedDiseases.join(', '),
          medications: medications.trim(),
        }),
      })
    } catch (e) {}
    setSaving(false)
    setFadeOut(true)
    setTimeout(() => onComplete(), 500)
  }

  const handleSkip = () => {
    setFadeOut(true)
    setTimeout(() => onSkip(), 500)
  }

  const customDiseases = selectedDiseases.filter(d => !COMMON_DISEASES.includes(d))

  return (
    <div
      className={`flex flex-col h-full transition-opacity duration-500 ${fadeOut ? 'opacity-0' : 'opacity-100'}`}
      style={{ background: '#FFFDF5' }}
    >
      {/* 메인 헤더 */}
      <div className="flex items-center justify-between shrink-0" style={{ background: 'linear-gradient(135deg, #FFD700, #DAA520, #B8860B)', padding: '28px 20px 10px', boxShadow: '0 4px 20px rgba(218,165,32,0.2)' }}>
        <div className="flex items-center gap-2.5">
          <img src="/logo.png" alt="메디스캐너" style={{
              width: 46, height: 46,
              filter: 'sepia(40%) saturate(70%) brightness(1.05)',
              WebkitMaskImage: 'radial-gradient(circle, black 62%, transparent 78%)',
              maskImage: 'radial-gradient(circle, black 62%, transparent 78%)',
            }} />
          <div>
            <div className="text-white font-bold" style={{ fontSize: 16, letterSpacing: 0.5, textShadow: '0 1px 4px rgba(0,0,0,0.15)' }}>메디스캐너</div>
            <div style={{ color: 'rgba(255,255,255,0.95)', fontSize: 11, fontWeight: 600 }}>AI 의료 상담</div>
          </div>
        </div>
        <button onClick={onExit}
          style={{ background: 'rgba(255,255,255,0.25)', border: '1.5px solid rgba(255,255,255,0.5)', borderRadius: 20, padding: '4px 14px', color: '#3A1A00', fontSize: 13, fontWeight: 700, cursor: 'pointer', letterSpacing: 1, boxShadow: '0 2px 8px rgba(0,0,0,0.15)', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 16, fontWeight: 900 }}>⊠</span> 종료
        </button>
      </div>

      {/* 콘텐츠 */}
      <div className="flex flex-col flex-1 px-5 pt-3 pb-3" style={{ maxWidth: 375, alignSelf: 'center', width: '100%' }}>

        <div className="flex flex-col items-center mb-3">
          <div className="flex items-center justify-center shrink-0"
            style={{ width: 42, height: 42, fontSize: 22, background: 'linear-gradient(145deg, #FFD700, #DAA520)', borderRadius: 12, boxShadow: '0 4px 16px rgba(218,165,32,0.3)' }}>
            👤
          </div>
          <h2 className="mt-1 font-bold" style={{ fontSize: 18, color: '#2A1D08' }}>건강 프로필 등록</h2>
          <p className="mt-0.5 text-center" style={{ fontSize: 12, color: '#6B4D10', fontWeight: 700 }}>맞춤 의료 상담을 위해 건강 정보를 입력해주세요</p>
        </div>

        <div className="w-full flex flex-col gap-3">

          {/* 나이 */}
          <div>
            <label style={{ fontSize: 15, color: '#5A3E00', fontWeight: 700 }}>나이</label>
            <input type="number" value={age} onChange={e => setAge(e.target.value)} placeholder="65"
              className="w-full mt-1 px-3 py-2 rounded-lg outline-none"
              style={{ fontSize: 14, fontWeight: 500, background: '#FFF8E0', border: '1px solid #E0D0A0', color: '#2A1D08' }} />
          </div>

          {/* 기저질환 */}
          <div>
            <label style={{ fontSize: 15, color: '#5A3E00', fontWeight: 700 }}>기저질환 (해당하는 것 모두 선택)</label>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {COMMON_DISEASES.map(disease => (
                <button key={disease} onClick={() => toggleDisease(disease)}
                  className="px-2.5 py-1 rounded-full font-medium"
                  style={{
                    fontSize: 12,
                    background: selectedDiseases.includes(disease) ? 'linear-gradient(135deg, #C96010, #A04000)' : '#FFF8E0',
                    color: selectedDiseases.includes(disease) ? '#FFFFFF' : '#8B7A50',
                    border: selectedDiseases.includes(disease) ? '1px solid #A04000' : '1px solid #E0D0A0',
                    boxShadow: selectedDiseases.includes(disease) ? '0 1px 4px rgba(160,64,0,0.3)' : 'none',
                  }}>
                  {selectedDiseases.includes(disease) ? '✓ ' : ''}{disease}
                </button>
              ))}
              {customDiseases.map(disease => (
                <button key={disease} onClick={() => toggleDisease(disease)}
                  className="px-2.5 py-1 rounded-full font-medium"
                  style={{ fontSize: 12, background: 'linear-gradient(135deg, #C96010, #A04000)', color: '#FFFFFF', border: '1px solid #A04000' }}>
                  ✓ {disease}
                </button>
              ))}
              <button onClick={() => setShowCustomInput(true)}
                className="px-2.5 py-1 rounded-full font-medium"
                style={{ fontSize: 12, background: '#FFF8E0', color: '#8B7A50', border: '1px dashed #DAA520' }}>
                + 기타
              </button>
            </div>
            {showCustomInput && (
              <div className="flex gap-1 mt-1">
                <input type="text" value={customDisease} onChange={e => setCustomDisease(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && addCustomDisease()} placeholder="질환명 입력" autoFocus
                  className="flex-1 px-3 py-1.5 rounded-lg outline-none"
                  style={{ fontSize: 12, background: '#FFF8E0', border: '1px solid #E0D0A0', color: '#2A1D08' }} />
                <button onClick={addCustomDisease} className="px-3 py-1.5 rounded-lg font-medium"
                  style={{ fontSize: 12, background: 'linear-gradient(135deg, #FFD700, #DAA520)', color: '#1A1206' }}>추가</button>
                <button onClick={() => { setShowCustomInput(false); setCustomDisease('') }}
                  className="px-2.5 py-1.5 rounded-lg"
                  style={{ fontSize: 12, color: '#A89060', background: '#FFF8E0', border: '1px solid #E0D0A0' }}>취소</button>
              </div>
            )}
            {selectedDiseases.length > 0 && (
              <p className="mt-1" style={{ fontSize: 11, color: '#B8860B', fontWeight: 500 }}>선택됨: {selectedDiseases.join(', ')}</p>
            )}
          </div>

          {/* 복용 중인 약 */}
          <div>
            <label style={{ fontSize: 15, color: '#5A3E00', fontWeight: 700 }}>복용 중인 약</label>
            <div className="flex gap-1.5 mt-1">
              <input type="text" value={medications} onChange={e => setMedications(e.target.value)}
                placeholder="약 이름 직접 입력"
                className="flex-1 px-3 py-2 rounded-lg outline-none"
                style={{ fontSize: 14, fontWeight: 500, background: '#FFF8E0', border: '1px solid #E0D0A0', color: '#2A1D08' }} />
              <input type="file" accept="image/*" capture="environment" ref={fileInputRef}
                onChange={handleMedOCR} className="hidden" />
              <button onClick={() => fileInputRef.current?.click()} disabled={ocrLoading}
                className="shrink-0 flex items-center justify-center rounded-lg"
                style={{ width: 40, height: 40, background: ocrLoading ? '#E0D0A0' : 'linear-gradient(135deg, #FFD700, #DAA520)', border: '1px solid #DAA520', cursor: ocrLoading ? 'wait' : 'pointer' }}>
                {ocrLoading ? (
                  <div style={{
                    width: 20, height: 20,
                    border: '2.5px solid rgba(90,62,0,0.2)',
                    borderTop: '2.5px solid #5A3E00',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite',
                  }} />
                ) : <span style={{ fontSize: 18 }}>📷</span>}
              </button>
              <button onClick={handleVoiceMed}
                className="shrink-0 flex items-center justify-center rounded-lg"
                style={{ width: 40, height: 40, border: '1px solid #DAA520',
                  background: isListening ? 'linear-gradient(135deg, #FF6B6B, #CC2222)' : 'linear-gradient(135deg, #FFD700, #DAA520)' }}>
                <span style={{ fontSize: 18 }}>{isListening ? '⏹' : '🎤'}</span>
              </button>
              <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
            </div>
            {isListening && (
              <p style={{ fontSize: 11, color: '#CC2222', fontWeight: 600, marginTop: 4 }}>🎤 듣는 중... 약 이름을 말해주세요</p>
            )}
            <p className="mt-1" style={{ fontSize: 11, color: '#6B4D10', fontWeight: 600 }}>
              처방전이나 약봉투를 촬영하면 자동으로 약 이름을 인식합니다
            </p>
          </div>
        </div>

        <button
          onMouseDown={() => setSubmitActive(true)}
          onMouseUp={() => setSubmitActive(false)}
          onMouseLeave={() => setSubmitActive(false)}
          onTouchStart={() => setSubmitActive(true)}
          onTouchEnd={() => setSubmitActive(false)}
          onClick={handleSubmit} disabled={saving}
          className="mt-6 w-full py-3 rounded-full font-bold"
          style={{ fontSize: 15, letterSpacing: 1, cursor: saving ? 'wait' : 'pointer', opacity: saving ? 0.6 : 1, transition: 'background 0.1s, color 0.1s',
            background: submitActive ? 'linear-gradient(135deg, #FFD700, #DAA520, #B8860B)' : '#FFF8E0',
            color: submitActive ? '#1A1206' : '#8B6914',
            border: submitActive ? '1px solid #DAA520' : '1.5px solid #E0D0A0',
          }}>
          {saving ? '저장 중...' : '등록하고 시작하기'}
        </button>
        <button
          onMouseDown={() => setSkipActive(true)}
          onMouseUp={() => setSkipActive(false)}
          onMouseLeave={() => setSkipActive(false)}
          onTouchStart={() => setSkipActive(true)}
          onTouchEnd={() => setSkipActive(false)}
          onClick={handleSkip}
          className="mt-2 w-full py-3 rounded-full font-bold"
          style={{ fontSize: 15, letterSpacing: 1, cursor: 'pointer', transition: 'background 0.1s, color 0.1s',
            background: skipActive ? 'linear-gradient(135deg, #FFD700, #DAA520, #B8860B)' : '#FFF8E0',
            color: skipActive ? '#1A1206' : '#8B6914',
            border: skipActive ? '1px solid #DAA520' : '1.5px solid #E0D0A0',
          }}>
          맞춤 정보 불필요 (일반 상담)
        </button>

      </div>
    </div>
  )
}
