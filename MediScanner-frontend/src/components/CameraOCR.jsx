import { useState, useRef } from 'react'

export default function CameraOCR({ apiUrl, image, setImage, preview, setPreview, result, setResult }) {
  const [loading, setLoading] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const fileInputRef = useRef(null)
  const synthRef = useRef(window.speechSynthesis)

  const handleCapture = (e) => {
    const file = e.target.files[0]
    if (!file) return
    setImage(file)
    setResult(null)
    const reader = new FileReader()
    reader.onload = (ev) => setPreview(ev.target.result)
    reader.readAsDataURL(file)
  }

  const handleAnalyze = async () => {
    if (!image) return
    setLoading(true)
    setResult(null)
    try {
      const reader = new FileReader()
      reader.onload = async (ev) => {
        const base64 = ev.target.result.split(',')[1]
        const res = await fetch(`${apiUrl}/api/camera/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image_base64: base64, user_id: 'default' }),
        })
        if (!res.ok) throw new Error('분석 실패')
        const data = await res.json()
        setResult(data)
        setLoading(false)
      }
      reader.readAsDataURL(image)
    } catch (err) {
      setResult({ error: '분석 중 오류가 발생했습니다. 다시 시도해주세요.' })
      setLoading(false)
    }
  }

  const handleReset = () => {
    setImage(null)
    setPreview(null)
    setResult(null)
    synthRef.current.cancel()
    setSpeaking(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleSpeak = (text) => {
    const synth = synthRef.current
    if (!synth) return
    if (speaking) { synth.cancel(); setSpeaking(false); return }
    synth.cancel()
    const cleanText = text.replace(/⚠️|❌|💊|🔊|📷|😊|※/g, '').replace(/[#*_]/g, '').trim()
    const utter = new SpeechSynthesisUtterance(cleanText)
    utter.lang = 'ko-KR'
    utter.rate = 1.0
    utter.onend = () => setSpeaking(false)
    utter.onerror = () => setSpeaking(false)
    setSpeaking(true)
    synth.speak(utter)
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto px-4 py-4" style={{ background: 'linear-gradient(180deg, #FFFDF5, #FFF9EA)' }}>
      <div className="text-center mb-3">
        <p style={{ fontSize: 16, color: '#2A1D08', fontWeight: 700 }}>약 성분표 / 처방전 스캔</p>
        <p style={{ fontSize: 13, color: '#A89060', marginTop: 4, fontWeight: 500 }}>약봉투, 처방전, 성분표를 촬영하면 어떤 약인지 분석해드려요</p>
      </div>

      <input type="file" accept="image/*" capture="environment" ref={fileInputRef} onChange={handleCapture} className="hidden" />

      {!preview ? (
        <button onClick={() => fileInputRef.current?.click()} className="w-full py-10 rounded-xl flex flex-col items-center gap-2"
          style={{ background: '#FFF8E0', border: '2px dashed #DAA520', cursor: 'pointer' }}>
          <span style={{ fontSize: 36 }}>📷</span>
          <span style={{ fontSize: 14, color: '#8B7A50', fontWeight: 600 }}>사진 촬영 또는 갤러리에서 선택</span>
          <span style={{ fontSize: 12, color: '#A89060' }}>약봉투, 처방전, 성분표</span>
        </button>
      ) : (
        <>
          {!result && (
            <div className="relative rounded-xl overflow-hidden mb-3" style={{ border: '1px solid #E0D0A0' }}>
              <img src={preview} alt="촬영 이미지" className="w-full" style={{ maxHeight: 250, objectFit: 'contain', background: '#F5F0E6' }} />
            </div>
          )}
          <div className="flex gap-2 mb-3">
            <button onClick={handleReset} className="flex-1 py-2.5 rounded-full font-medium"
              style={{ fontSize: 13, background: '#FFF8E0', border: '1px solid #E0D0A0', color: '#8B7A50' }}>다시 촬영</button>
            <button onClick={handleAnalyze} disabled={loading} className="flex-1 py-2.5 rounded-full font-bold"
              style={{ fontSize: 13, background: 'linear-gradient(135deg, #FFD700, #DAA520)', color: '#1A1206', opacity: loading ? 0.6 : 1 }}>
              {loading ? '분석 중...' : '분석하기'}
            </button>
          </div>
        </>
      )}

      {loading && (
        <div className="flex flex-col items-center py-6">
          <div className="flex gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '0ms' }} />
            <div className="w-2.5 h-2.5 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '150ms' }} />
            <div className="w-2.5 h-2.5 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '300ms' }} />
          </div>
          <p className="mt-2" style={{ fontSize: 13, color: '#A89060', fontWeight: 500 }}>GPT-4 Vision으로 분석 중...</p>
        </div>
      )}

      {result && !result.error && (
        <div className="rounded-xl p-4" style={{ background: 'white', border: '1px solid #E8DCC0' }}>
          {preview && (
            <div className="relative rounded-lg overflow-hidden mb-3" style={{ border: '1px solid #E0D0A0' }}>
              <img src={preview} alt="촬영 이미지" className="w-full" style={{ maxHeight: 150, objectFit: 'contain', background: '#F5F0E6' }} />
            </div>
          )}

          {result.drug_names && result.drug_names.length > 0 && (
            <div className="mb-3">
              <p style={{ fontSize: 14, color: '#5A3E00', fontWeight: 700 }}>복용중인 약</p>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {result.drug_names.map((name, i) => (
                  <span key={i} className="px-3 py-1.5 rounded-full font-bold"
                    style={{ fontSize: 13, background: 'linear-gradient(135deg, #FFD700, #DAA520)', color: '#1A1206' }}>{name}</span>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center justify-between mb-1.5">
            <p style={{ fontSize: 14, color: '#5A3E00', fontWeight: 700 }}>분석 결과</p>
            <button onClick={() => handleSpeak(result.analysis)} className="px-3 py-1 rounded-full"
              style={{
                fontSize: 12, fontWeight: 600,
                background: speaking ? 'linear-gradient(135deg, #FFD700, #DAA520)' : '#FFF8E0',
                color: speaking ? '#1A1206' : '#B8860B',
                border: speaking ? '1px solid #DAA520' : '1px solid #E0D0A0',
              }}>
              {speaking ? '⏹ 멈춤' : '🔊 읽기'}
            </button>
          </div>
          <div style={{ fontSize: 15, fontWeight: 500, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
            {result.analysis && result.analysis.split('\n').map((line, i) => {
              const isDanger = /주의|경고|위험|금지|복용금지|병용금기|즉시\s*병원|즉시\s*내원|부작용|알레르기|중단|과다|심각|⚠️|❌|상호작용/.test(line)
              const isHeader = /^###|^\*\*\*|^##/.test(line.trim())
              const cleanLine = line.replace(/\*\*/g, '')
              return (
                <p key={i} style={{
                  color: isDanger ? '#CC2200' : isHeader ? '#5A3E00' : '#2A1D08',
                  fontWeight: isDanger ? 700 : isHeader ? 700 : 500,
                  margin: '2px 0',
                  background: isDanger ? 'rgba(204,34,0,0.06)' : 'transparent',
                  borderLeft: isDanger ? '3px solid #CC2200' : 'none',
                  paddingLeft: isDanger ? 8 : 0,
                  borderRadius: isDanger ? 4 : 0,
                }}>
                  {cleanLine}
                </p>
              )
            })}
          </div>

          {result.profile_warning && (
            <div className="mt-3 p-3 rounded-lg" style={{ background: '#FFF3E0', border: '1px solid #FFB74D' }}>
              <p style={{ fontSize: 14, color: '#E65100', fontWeight: 700 }}>건강 프로필 기반 주의사항</p>
              <p className="mt-1" style={{ fontSize: 14, color: '#BF360C', fontWeight: 500, lineHeight: 1.6 }}>{result.profile_warning}</p>
            </div>
          )}

          <p className="mt-3" style={{ fontSize: 11, color: '#C4A860' }}>※ 참고용 정보이며, 정확한 진단은 의료 전문가와 상담하세요.</p>
        </div>
      )}

      {result && result.error && (
        <div className="rounded-xl p-3.5" style={{ background: '#FFF3E0', border: '1px solid #FFB74D' }}>
          <p style={{ fontSize: 14, color: '#E65100', fontWeight: 500 }}>{result.error}</p>
        </div>
      )}
    </div>
  )
}
