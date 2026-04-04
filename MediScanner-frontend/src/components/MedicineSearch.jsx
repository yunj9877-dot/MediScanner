import { useState, useRef } from 'react'

export default function MedicineSearch({ apiUrl, query, setQuery, result, setResult, searched, setSearched }) {
  const [localQuery, setLocalQuery] = useState(query || '')
  const [loading, setLoading] = useState(false)
  const [searchCompleted, setSearchCompleted] = useState(false)
  const [expandedSections, setExpandedSections] = useState({})
  const [speakingKey, setSpeakingKey] = useState(null)
  const synthRef = useRef(window.speechSynthesis)

  const handleSearch = async () => {
    if (!localQuery.trim() || loading) return
    setQuery(localQuery)
    setLoading(true)
    setSearched(true)
    setSearchCompleted(false)
    setExpandedSections({})
    synthRef.current.cancel()
    setSpeakingKey(null)
    try {
      const res = await fetch(`${apiUrl}/api/medicine/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ drug_name: localQuery.trim() }),
      })
      if (!res.ok) throw new Error('검색 실패')
      const data = await res.json()
      setResult(data)
    } catch (err) { setResult(null) }
    finally { setLoading(false); setSearchCompleted(true) }
  }

  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const handleSpeak = (text, key) => {
    const synth = synthRef.current
    if (!synth) return

    if (speakingKey === key) {
      synth.cancel()
      setSpeakingKey(null)
      return
    }

    synth.cancel()
    setSpeakingKey(null)

    setTimeout(() => {
      const cleanText = text.replace(/⚠️|❌|💊|🔊|🧪|✅|📋|😊|※/g, '').replace(/[#*_]/g, '').trim()
      const utter = new SpeechSynthesisUtterance(cleanText)
      utter.lang = 'ko-KR'
      utter.rate = 1.0
      utter.onend = () => setSpeakingKey(null)
      utter.onerror = () => setSpeakingKey(null)
      setSpeakingKey(key)
      synth.speak(utter)
    }, 100)
  }

  const sections = [
    { key: 'efcy', icon: '✅', label: '효능', color: '#333' },
    { key: 'use_method', icon: '📋', label: '사용법', color: '#333' },
    { key: 'atpn', icon: '⚠️', label: '주의사항', color: '#B8860B' },
    { key: 'se', icon: '❌', label: '부작용', color: '#CC3333' },
    { key: 'ingredient', icon: '🧪', label: '성분/함량', color: '#333' },
  ]

  const hasResult = result && result.found

  return (
    <div className="h-full overflow-y-auto" style={{ background: 'linear-gradient(180deg, #FFFDF5, #FFF9EA)' }}>
      <div className="p-4">
        <div className="flex gap-2 mb-4">
          <input type="text" value={localQuery} onChange={(e) => setLocalQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()} placeholder="약 이름 또는 성분명..."
            className="flex-1 outline-none" style={{ border: '1.5px solid #E0D0A0', borderRadius: 12, padding: '12px 14px', fontSize: 15, fontWeight: 500, background: 'white' }} />
          <button onClick={handleSearch} disabled={loading}
            style={{ padding: '12px 22px', background: 'linear-gradient(135deg, #FFD700, #DAA520, #B8860B)', color: 'white', borderRadius: 12, fontSize: 15, fontWeight: 700, opacity: loading ? 0.6 : 1 }}>
            {loading ? '...' : '검색'}
          </button>
        </div>

        <div className="text-center mb-4" style={{ padding: '10px 14px', background: 'linear-gradient(135deg, #FFF8E0, #FFF3D0)', border: '1px solid #E0D0A0', borderRadius: 12, fontSize: 13, fontWeight: 500, color: '#8B6914' }}>
          약 이름(타이레놀) 또는 성분명(아세트아미노펜) 검색 가능 | 무료
        </div>

        {/* 로딩 애니메이션 */}
        {loading && (
          <div className="flex flex-col items-center py-8">
            <div className="flex gap-1.5">
              <div className="w-3 h-3 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '0ms' }} />
              <div className="w-3 h-3 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '150ms' }} />
              <div className="w-3 h-3 rounded-full animate-bounce" style={{ background: '#DAA520', animationDelay: '300ms' }} />
            </div>
            <p className="mt-3" style={{ fontSize: 14, color: '#8B6914', fontWeight: 600 }}>식약처 API에서 검색 중...</p>
          </div>
        )}

        {/* 검색 결과 */}
        {hasResult ? (
          <div className="mb-4" style={{ background: 'white', border: '1px solid #E8DCC0', borderRadius: 16, overflow: 'hidden' }}>
            {/* 약 이름 헤더 */}
            <div style={{ padding: '14px 16px', background: 'linear-gradient(135deg, #FFF8EC, #FFF3D6)', borderBottom: '1px solid #E8DCC0' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#2A1D08' }}>
                {result.item_name || '이름 없음'}
              </div>
              <div style={{ fontSize: 13, color: '#8B6914', marginTop: 2, fontWeight: 500 }}>
                {result.entp_name || ''}
              </div>
              <div className="mt-1 px-2 py-0.5 rounded-full inline-block" style={{ fontSize: 14, fontWeight: 700, background: result.source === '허가정보' ? '#E3F2FD' : '#FFF8E0', color: result.source === '허가정보' ? '#1565C0' : '#8B6914', border: result.source === '허가정보' ? '1px solid #90CAF9' : '1px solid #E0D0A0' }}>
                {result.source}
              </div>
            </div>

            {/* 아코디언 섹션 */}
            {sections.map(({ key, icon, label, color }) => {
              const content = result[key]
              if (!content || content === '관련 정보 없음') return null
              const isOpen = expandedSections[key]

              return (
                <div key={key} style={{ borderBottom: '1px solid #F0E6D2' }}>
                  <div className="flex items-center justify-between px-4 py-3">
                    <button onClick={() => toggleSection(key)} className="flex items-center gap-2 flex-1">
                      <span style={{ fontSize: 14 }}>{icon}</span>
                      <span style={{ fontSize: 15, fontWeight: 600, color }}>{label}</span>
                      <span style={{ fontSize: 14, color: '#CCC', transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', marginLeft: 'auto' }}>▼</span>
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); handleSpeak(content, key) }}
                      className="ml-2 px-3 py-1.5 rounded-full shrink-0"
                      style={{
                        fontSize: 14, fontWeight: 700,
                        background: speakingKey === key ? 'linear-gradient(135deg, #FFD700, #DAA520)' : '#FFF8E0',
                        color: speakingKey === key ? '#1A1206' : '#B8860B',
                        border: speakingKey === key ? '1px solid #DAA520' : '1px solid #E0D0A0',
                      }}>
                      {speakingKey === key ? '⏹' : '🔊'}
                    </button>
                  </div>
                  {isOpen && (
                    <div className="px-4 pb-3">
                      <p style={{ fontSize: 14, color: '#2A1D08', fontWeight: 500, lineHeight: 1.7 }}>{content}</p>
                      {speakingKey === key && (
                        <button onClick={() => handleSpeak(content, key)}
                          className="mt-2 px-4 py-2 rounded-full"
                          style={{ fontSize: 14, fontWeight: 700, background: 'linear-gradient(135deg, #FFD700, #DAA520)', color: '#1A1206', border: '1px solid #DAA520' }}>
                          ⏹ 멈춤
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : searchCompleted && !hasResult ? (
          <div className="flex flex-col items-center py-8 px-4">
            <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#FFF8E0', border: '1px solid #E0D0A0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, marginBottom: 12 }}>🔍</div>
            <p style={{ fontSize: 16, color: '#5A3E00', fontWeight: 700, marginBottom: 6 }}>검색 결과를 찾지 못했습니다</p>
            <p style={{ fontSize: 14, color: '#8B7A50', fontWeight: 500, textAlign: 'center', lineHeight: 1.6 }}>다른 약 이름이나 성분명으로 검색해보세요</p>
            <div style={{ marginTop: 12, padding: '12px 16px', background: '#FFF8E0', border: '1px solid #E0D0A0', borderRadius: 12, width: '100%' }}>
              <p style={{ fontSize: 14, color: '#5A3E00', fontWeight: 700, marginBottom: 6 }}>이렇게 검색해보세요</p>
              <p style={{ fontSize: 13, color: '#8B7A50', fontWeight: 500, lineHeight: 1.8 }}>· 정확한 약 이름으로 검색: "<b style={{ color: '#B8860B' }}>타이레놀</b>"</p>
              <p style={{ fontSize: 13, color: '#8B7A50', fontWeight: 500, lineHeight: 1.8 }}>· 성분명으로 검색: "<b style={{ color: '#B8860B' }}>아세트아미노펜</b>"</p>
              <p style={{ fontSize: 13, color: '#8B7A50', fontWeight: 500, lineHeight: 1.8 }}>· 전문의약품도 검색 가능: "<b style={{ color: '#B8860B' }}>텔미정</b>"</p>
              <p style={{ fontSize: 13, color: '#8B7A50', fontWeight: 500, lineHeight: 1.8 }}>· 📷 카메라 탭에서 약 사진을 찍으면 자동 분석이 가능해요</p>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
