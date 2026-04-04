import { useState, useEffect } from 'react'

export default function SplashScreen({ onStart }) {
  const [fadeOut, setFadeOut] = useState(false)
  const [weather, setWeather] = useState(null)
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const loadWeather = async () => {
      try {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001'
        const res = await fetch(`${apiUrl}/api/weather`)
        const data = await res.json()
        if (data.weather) setWeather(data.weather)
      } catch (e) {}
    }
    loadWeather()
  }, [])

  const handleStart = () => {
    setFadeOut(true)
    setTimeout(() => onStart(), 500)
  }

  const dayNames = ['일', '월', '화', '수', '목', '금', '토']
  const timeStr = now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: true })
  const dateShort = `${now.getMonth() + 1}/${now.getDate()}(${dayNames[now.getDay()]})`
  const removeEmoji = (text) => text.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '').trim()

  const isDustBad = weather && ['나쁨', '매우나쁨'].includes(weather.dust_grade)

  const features = [
    { icon: '💬', title: 'AI 의료 상담', desc: '사용자 기저질환 맞춤 답변' },
    { icon: '📷', title: '약 스캔', desc: '처방전·약봉투 AI 분석' },
    { icon: '💊', title: '약 검색', desc: '식약처 API 실시간 의약품 정보' },
    { icon: '🔊', title: '음성 서비스', desc: '음성 입력 · 답변 읽어주기' },
  ]

  return (
    <div
      className={`flex flex-col items-center justify-center h-full transition-opacity duration-500 ${fadeOut ? 'opacity-0' : 'opacity-100'}`}
      style={{
        background: 'radial-gradient(ellipse at 50% 30%, #FFF8E0 0%, #FFE9A0 25%, #F5D670 50%, #E8C44A 75%, #D4A830 100%)',
        position: 'relative',
      }}
    >
      {/* 광택 오버레이 */}
      <div className="absolute inset-0 pointer-events-none" style={{
        background: 'radial-gradient(circle at 50% 25%, rgba(255,255,255,0.5) 0%, rgba(255,248,224,0.3) 30%, transparent 60%)',
      }} />

      {/* 좌상단 날짜+시간 */}
      <div style={{
        position: 'absolute', top: 12, left: 18, zIndex: 10,
        textAlign: 'left',
      }}>
        <div style={{ fontSize: 13, color: '#5A3E00', fontWeight: 700, marginLeft: 8 }}>
          {dateShort}
        </div>
        <div style={{ fontSize: 15, color: '#5A3E00', fontWeight: 800, marginTop: 1, marginLeft: 4 }}>
          {timeStr}
        </div>
      </div>

      {/* 우상단 날씨+대기질 */}
      <div style={{
        position: 'absolute', top: 12, right: 22, zIndex: 10,
        textAlign: 'right',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 3 }}>
          <span style={{ fontSize: 16 }}>{weather?.icon || '🌤️'}</span>
          <span style={{ fontSize: 17, color: '#5A3E00', fontWeight: 800 }}>
            {weather?.temp ? `${weather.temp}°C` : '--°C'}
          </span>
        </div>
        {weather?.dust_grade && (
          <div style={{ fontSize: 12, color: isDustBad ? '#CC0000' : '#5A3E00', fontWeight: 600, marginTop: 0 }}>
            대기질 {removeEmoji(weather.dust_grade)}{isDustBad ? <span style={{ fontSize: 13 }}>⚠️</span> : ''}
          </div>
        )}
      </div>

      {/* 메인 콘텐츠 */}
      <div className="relative z-10 flex flex-col items-center px-6" style={{ marginTop: -20 }}>

        {/* 로고 */}
        <img src="/logo.png" alt="메디스캐너" style={{
          width: 160, height: 160,
          filter: 'sepia(40%) saturate(70%) brightness(1.05)',
          position: 'absolute', top: 40, zIndex: 1, opacity: 0.95,
          WebkitMaskImage: 'radial-gradient(circle, black 48%, transparent 72%)',
          maskImage: 'radial-gradient(circle, black 48%, transparent 72%)',
        }} />

        {/* 슬로건 */}
        <p style={{
          fontSize: 20, color: '#8B4513', fontWeight: 600, letterSpacing: 1.5,
          fontStyle: 'italic', position: 'relative', zIndex: 2, marginTop: 195,
        }}>
          개인 맞춤 AI 헬스케어
        </p>

        {/* 타이틀 */}
        <h1 style={{ fontSize: 36, color: '#5A3E00', letterSpacing: 3, fontWeight: 800, marginTop: 6, position: 'relative', zIndex: 2 }}>
          메디스캐너
        </h1>
        <p style={{ fontSize: 22, color: '#8B6914', letterSpacing: 5, fontWeight: 600, marginTop: 0, position: 'relative', zIndex: 2 }}>
          MEDISCANNER
        </p>

        {/* 구분선 */}
        <div style={{ width: 120, height: 2.5, background: 'linear-gradient(90deg, transparent, #B8860B, transparent)', borderRadius: 2, marginTop: 16 }} />

        {/* 기능 소개 카드 */}
        <div style={{
          marginTop: 16,
          width: '100%',
          maxWidth: 335,
          padding: '8px 16px',
          background: 'rgba(255,255,255,0.55)',
          borderRadius: 14,
          border: '1px solid rgba(255,255,255,0.7)',
          boxShadow: '0 4px 20px rgba(180,140,20,0.12)',
        }}>
          {features.map((f, i) => (
            <div key={i} className="flex items-center gap-2.5" style={{ marginTop: i > 0 ? 5 : 0 }}>
              <span style={{ fontSize: 20, width: 24, textAlign: 'center' }}>{f.icon}</span>
              <div>
                <span style={{ fontSize: 14, color: '#3A2800', fontWeight: 900 }}>{f.title}</span>
                <span style={{ fontSize: 12, color: '#5A3E00', fontWeight: 700, marginLeft: 6 }}>{f.desc}</span>
              </div>
            </div>
          ))}
        </div>

        {/* 데이터 기반 문구 */}
        <p style={{ fontSize: 12, color: '#5A3E00', fontWeight: 500, marginTop: 8, opacity: 0.85, textAlign: 'center' }}>
          AI Hub 의료데이터 120,774건 · 식약처 공공데이터 기반
        </p>

        {/* 시작하기 버튼 */}
        <button
          onClick={handleStart}
          style={{
            marginTop: 18,
            width: 200,
            padding: '10px 0',
            background: 'linear-gradient(135deg, #5A3E00, #7A5A10, #5A3E00)',
            borderRadius: 28,
            border: '1px solid rgba(90,62,0,0.3)',
            boxShadow: '0 4px 20px rgba(90,62,0,0.25)',
            color: '#FFF8E0',
            fontSize: 17,
            fontWeight: 700,
            letterSpacing: 3,
            cursor: 'pointer',
          }}
        >
          시 작 하 기
        </button>

      </div>
    </div>
  )
}
