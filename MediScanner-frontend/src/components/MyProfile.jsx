import { useState, useEffect, useRef } from 'react'

const COMMON_DISEASES = [
  '고혈압', '당뇨병', '관절염', '골다공증',
  '치매', '폐질환', '심장질환', '만성신장병',
]

export default function MyProfile({ apiUrl, sessionId, analysisResult, setAnalysisResult, analysisLoading, setAnalysisLoading }) {
  const [profile, setProfile] = useState(null)
  const [editing, setEditing] = useState(false)
  const [age, setAge] = useState('')
  const [selectedDiseases, setSelectedDiseases] = useState([])
  const [customDisease, setCustomDisease] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [medications, setMedications] = useState('')
  const [history, setHistory] = useState([])
  const [showHistory, setShowHistory] = useState(false)
  const [profileLoading, setProfileLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [ocrLoading, setOcrLoading] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const recognitionRef = useRef(null)

  useEffect(() => { loadProfile(); loadHistory() }, [])

  const loadProfile = async () => {
    setProfileLoading(true)
    try {
      const res = await fetch(`${apiUrl}/api/profile/${sessionId}`)
      const data = await res.json()
      if (data.status === 'ok' && data.profile) {
        setProfile(data.profile)
        setAge(data.profile.age ? String(data.profile.age) : '')
        setSelectedDiseases(data.profile.diseases ? data.profile.diseases.split(', ').filter(Boolean) : [])
        setMedications(data.profile.medications || '')
        // 나이/기저질환/복용약 모두 비어있으면 분석 안 함
        const hasInfo = data.profile.age || data.profile.diseases || data.profile.medications
        if (hasInfo && !analysisResult && !analysisLoading) {
          analyzeProfile(data.profile.age, data.profile.diseases, data.profile.medications)
        } else if (!hasInfo) {
          setAnalysisResult('no_profile')
        }
      }
    } catch (e) {}
    setProfileLoading(false)
  }

  const loadHistory = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/history/${sessionId}?limit=20`)
      const data = await res.json()
      setHistory(data.history || [])
    } catch (e) {}
  }

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
      } catch (err) {}
      setOcrLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
    reader.readAsDataURL(file)
  }

  // AI 분석 함수 (전용 엔드포인트 - RAG 없이 GPT 직접 호출, 3~5초)
  const analyzeProfile = async (ageVal, diseases, meds) => {
    setAnalysisLoading(true)
    setAnalysisResult(null)
    try {
      const res = await fetch(`${apiUrl}/api/analyze-profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          age: parseInt(ageVal) || 0,
          diseases: diseases || '',
          medications: meds || '',
        }),
      })
      const data = await res.json()
      setAnalysisResult(data.answer || '분석 결과를 받지 못했습니다.')
    } catch (e) {
      setAnalysisResult('분석 중 오류가 발생했습니다.')
    }
    setAnalysisLoading(false)
  }

  const handleSave = async () => {
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
      await loadProfile()
      setEditing(false)
      // 저장 후 자동으로 AI 분석 실행
      await analyzeProfile(age, selectedDiseases.join(', '), medications.trim())
    } catch (e) {}
    setSaving(false)
  }

  // TTS
  const handleSpeak = () => {
    if (!analysisResult || analysisResult === 'no_profile') return
    if (isSpeaking) {
      window.speechSynthesis.cancel()
      setIsSpeaking(false)
      return
    }
    const utter = new SpeechSynthesisUtterance(analysisResult)
    utter.lang = 'ko-KR'
    utter.rate = 0.9
    utter.pitch = 1.0
    utter.onend = () => setIsSpeaking(false)
    utter.onerror = () => setIsSpeaking(false)
    window.speechSynthesis.speak(utter)
    setIsSpeaking(true)
  }

  const customDiseases = selectedDiseases.filter(d => !COMMON_DISEASES.includes(d))

  return (
    <div className="flex flex-col h-full overflow-y-auto px-4 py-3" style={{ background: 'linear-gradient(180deg, #FFFDF5, #FFF9EA)' }}>

      {/* 프로필 카드 */}
      <div className="rounded-xl p-4" style={{ background: 'white', border: '1px solid #E8DCC0' }}>
        <div className="flex items-center justify-between mb-3">
          <p style={{ fontSize: 16, color: '#2A1D08', fontWeight: 700 }}>👤 건강 프로필</p>
          {!editing && (
            <button onClick={() => setEditing(true)}
              className="px-3 py-1.5 rounded-full font-medium"
              style={{ fontSize: 13, background: '#FFF8E0', border: '1px solid #E0D0A0', color: '#B8860B' }}>수정</button>
          )}
        </div>

        {!editing ? (
          profileLoading ? (
            <div className="flex justify-center items-center py-3">
              <div style={{
                width: 28, height: 28,
                border: '3px solid #E0D0A0',
                borderTop: '3px solid #DAA520',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }} />
              <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
            </div>
          ) : profile ? (
            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center">
                <span style={{ fontSize: 14, color: '#5A3E00', fontWeight: 500 }}>나이</span>
                <span style={{ fontSize: 14, color: '#2A1D08', fontWeight: 600, textAlign: 'right' }}>{profile.age ? `${profile.age}세` : '-'}</span>
              </div>
              <div className="flex justify-between items-center">
                <span style={{ fontSize: 14, color: '#5A3E00', fontWeight: 500 }}>기저질환</span>
                <span style={{ fontSize: 14, color: '#2A1D08', fontWeight: 600, textAlign: 'right', maxWidth: '60%', wordBreak: 'keep-all', overflowWrap: 'break-word' }}>{profile.diseases || '없음'}</span>
              </div>
              <div className="flex justify-between items-center">
                <span style={{ fontSize: 14, color: '#5A3E00', fontWeight: 500 }}>복용약</span>
                <span style={{ fontSize: 14, color: '#2A1D08', fontWeight: 600, textAlign: 'right', maxWidth: '65%' }}>
                  {profile.medications
                    ? profile.medications.split(',').map((m, i, arr) => (
                        <span key={i} style={{ whiteSpace: 'nowrap' }}>{m.trim()}{i < arr.length - 1 ? ', ' : ''}</span>
                      ))
                    : '없음'}
                </span>
              </div>
            </div>
          ) : analysisLoading ? (
            <div className="flex justify-center items-center py-3">
              <div style={{
                width: 28, height: 28,
                border: '3px solid #E0D0A0',
                borderTop: '3px solid #DAA520',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }} />
            </div>
          ) : (
            <p style={{ fontSize: 14, color: '#A89060', fontWeight: 500 }}>등록된 프로필이 없습니다.</p>
          )
        ) : (
          <div className="flex flex-col gap-2.5">
            <div>
              <label style={{ fontSize: 14, color: '#5A3E00', fontWeight: 600 }}>나이</label>
              <input type="number" value={age} onChange={e => setAge(e.target.value)}
                className="w-full mt-1 px-3 py-2 rounded-lg outline-none"
                style={{ fontSize: 15, fontWeight: 500, background: '#FFF8E0', border: '1px solid #E0D0A0', color: '#2A1D08' }} />
            </div>
            <div>
              <label style={{ fontSize: 14, color: '#5A3E00', fontWeight: 600 }}>기저질환</label>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {COMMON_DISEASES.map(disease => (
                  <button key={disease} onClick={() => toggleDisease(disease)}
                    className="px-3 py-1.5 rounded-full font-medium"
                    style={{
                      fontSize: 13,
                      background: selectedDiseases.includes(disease) ? 'linear-gradient(135deg, #C96010, #A04000)' : '#FFF8E0',
                      color: selectedDiseases.includes(disease) ? '#FFFFFF' : '#8B7A50',
                      border: selectedDiseases.includes(disease) ? '1px solid #A04000' : '1px solid #E0D0A0',
                    }}>
                    {selectedDiseases.includes(disease) ? '✓ ' : ''}{disease}
                  </button>
                ))}
                {customDiseases.map(disease => (
                  <button key={disease} onClick={() => toggleDisease(disease)}
                    className="px-3 py-1.5 rounded-full font-medium"
                    style={{ fontSize: 13, background: 'linear-gradient(135deg, #C96010, #A04000)', color: '#FFFFFF', border: '1px solid #A04000' }}>
                    ✓ {disease}
                  </button>
                ))}
                <button onClick={() => setShowCustomInput(true)}
                  className="px-3 py-1.5 rounded-full font-medium"
                  style={{ fontSize: 13, background: '#FFF8E0', color: '#8B7A50', border: '1px dashed #DAA520' }}>+ 기타</button>
              </div>
              {showCustomInput && (
                <div className="flex gap-1 mt-1.5">
                  <input type="text" value={customDisease} onChange={e => setCustomDisease(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && addCustomDisease()} placeholder="질환명" autoFocus
                    className="flex-1 px-3 py-1.5 rounded-lg outline-none"
                    style={{ fontSize: 13, background: '#FFF8E0', border: '1px solid #E0D0A0', color: '#2A1D08' }} />
                  <button onClick={addCustomDisease} className="px-3 py-1.5 rounded-lg font-medium"
                    style={{ fontSize: 13, background: 'linear-gradient(135deg, #FFD700, #DAA520)', color: '#1A1206' }}>추가</button>
                  <button onClick={() => { setShowCustomInput(false); setCustomDisease('') }}
                    className="px-2.5 py-1.5 rounded-lg"
                    style={{ fontSize: 13, color: '#A89060', background: '#FFF8E0', border: '1px solid #E0D0A0' }}>취소</button>
                </div>
              )}
            </div>
            <div>
              <label style={{ fontSize: 14, color: '#5A3E00', fontWeight: 600 }}>복용약</label>
              <div className="flex gap-1.5 mt-1">
                <input type="text" value={medications} onChange={e => setMedications(e.target.value)}
                  placeholder="약 이름 직접 입력"
                  className="flex-1 px-3 py-2 rounded-lg outline-none"
                  style={{ fontSize: 15, fontWeight: 500, background: '#FFF8E0', border: '1px solid #E0D0A0', color: '#2A1D08' }} />
                <input type="file" accept="image/*" capture="environment" ref={fileInputRef}
                  onChange={handleMedOCR} className="hidden" />
                <button onClick={() => fileInputRef.current?.click()} disabled={ocrLoading}
                  className="shrink-0 flex items-center justify-center rounded-lg"
                  style={{ width: 40, height: 40, background: ocrLoading ? '#E0D0A0' : 'linear-gradient(135deg, #FFD700, #DAA520)', border: '1px solid #DAA520' }}>
                  {ocrLoading ? (
                    <div style={{ width: 20, height: 20, border: '2.5px solid rgba(90,62,0,0.2)', borderTop: '2.5px solid #5A3E00', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
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
              <p className="mt-1" style={{ fontSize: 11, color: '#A89060' }}>처방전/약봉투 촬영으로 자동 인식</p>
            </div>
            <div className="flex gap-2 mt-1">
              <button onClick={() => setEditing(false)}
                className="flex-1 py-2 rounded-full font-medium"
                style={{ fontSize: 14, background: '#FFF8E0', border: '1px solid #E0D0A0', color: '#8B7A50' }}>취소</button>
              <button onClick={handleSave} disabled={saving}
                className="flex-1 py-2 rounded-full font-bold"
                style={{ fontSize: 14, background: 'linear-gradient(135deg, #FFD700, #DAA520)', color: '#1A1206', opacity: saving ? 0.6 : 1 }}>
                {saving ? '저장 중...' : '저장'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* AI 건강 분석 리포트 인라인 카드 */}
      {(analysisLoading || analysisResult) && (
        <div className="rounded-xl p-4 mt-3" style={{ background: 'white', border: '1px solid #E8DCC0' }}>
          {/* 헤더 */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span style={{ fontSize: 18 }}>🤖</span>
              <p style={{ fontSize: 15, fontWeight: 700, color: '#2A1D08' }}>AI 건강 분석 리포트</p>
            </div>
            {!analysisLoading && analysisResult !== 'no_profile' && (
              <button onClick={handleSpeak}
                className="flex items-center gap-1 px-3 py-1.5 rounded-full font-bold"
                style={{
                  fontSize: 12, border: 'none', cursor: 'pointer',
                  background: isSpeaking ? 'linear-gradient(135deg, #CC4444, #AA2222)' : 'linear-gradient(135deg, #FFD700, #DAA520)',
                  color: isSpeaking ? 'white' : '#1A1206',
                }}>
                <span style={{ fontSize: 14 }}>{isSpeaking ? '⏹' : '🔊'}</span>
                {isSpeaking ? '정지' : '음성 듣기'}
              </button>
            )}
          </div>

          {/* 로딩 */}
          {analysisLoading ? (
            <div className="flex flex-col items-center py-6 gap-3">
              <div style={{
                width: 36, height: 36,
                border: '3px solid #E0D0A0',
                borderTop: '3px solid #DAA520',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }} />
              <p style={{ fontSize: 13, color: '#8B7A50', fontWeight: 600 }}>나이 · 질환 · 복용약 분석 중...</p>
              <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
            </div>
          ) : analysisResult === 'no_profile' ? (
            <div style={{ background: '#FFF0F0', borderRadius: 8, padding: '20px 16px', textAlign: 'center' }}>
              <p style={{ fontSize: 15, color: '#C62828', fontWeight: 700 }}>
                건강 프로필을 먼저 입력해 주세요!
              </p>
            </div>
          ) : (
            <div style={{ background: '#FFF8E0', borderRadius: 10, padding: '12px 14px', border: '1px solid #E0D0A0' }}>
              {analysisResult && analysisResult.split('\n').map((line, i) => {
                const highlighted = line.replace(
                  /(병용금기|금기|복용금지|복용 금지|부작용|이상 반응|즉시 병원|즉시 내원|❌|⚠️)/g,
                  '<mark>$1</mark>'
                )
                return (
                  <p key={i} style={{ fontSize: 13, color: '#2A1D08', fontWeight: 500, lineHeight: 1.8, margin: '2px 0' }}
                    dangerouslySetInnerHTML={{ __html: highlighted.replace(/<mark>/g, '<span style="color:#B22222;font-weight:700">').replace(/<\/mark>/g, '</span>') }} />
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* 상담 히스토리 */}
      <div className="rounded-xl p-4 mt-3" style={{ background: 'white', border: '1px solid #E8DCC0' }}>
        <button onClick={() => { setShowHistory(!showHistory); if (!showHistory) loadHistory() }}
          className="flex items-center justify-between w-full">
          <p style={{ fontSize: 16, color: '#2A1D08', fontWeight: 700 }}>📋 상담 히스토리</p>
          <span style={{ fontSize: 13, color: '#A89060', fontWeight: 500 }}>{showHistory ? '접기 ▲' : '펼치기 ▼'}</span>
        </button>
        {showHistory && (
          <div className="mt-2 flex flex-col gap-2">
            {history.length === 0 ? (
              <p style={{ fontSize: 14, color: '#A89060', fontWeight: 500 }}>상담 내역이 없습니다.</p>
            ) : (
              history.map((item, i) => (
                <div key={i} className="p-2.5 rounded-lg" style={{ background: '#FFF8E0', border: '1px solid #E0D0A0' }}>
                  <div className="flex justify-between items-center">
                    <p style={{ fontSize: 13, color: '#B8860B', fontWeight: 700 }}>{item.question}</p>
                    <span style={{ fontSize: 10, color: '#A89060' }}>{item.created_at?.slice(5, 16)}</span>
                  </div>
                  <p className="mt-1" style={{ fontSize: 12, color: '#2A1D08', fontWeight: 500, lineHeight: 1.5 }}>
                    {item.answer?.length > 80 ? item.answer.slice(0, 80) + '...' : item.answer}
                  </p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
