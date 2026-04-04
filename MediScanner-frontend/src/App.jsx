import { useState } from 'react'
import SplashScreen from './components/SplashScreen'
import ProfileSetup from './components/ProfileSetup'
import ChatWindow from './components/ChatWindow'
import CameraOCR from './components/CameraOCR'
import MedicineSearch from './components/MedicineSearch'
import MyProfile from './components/MyProfile'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'

// 세션 ID 생성 (탭 닫기 전까지 유지)
function getSessionId() {
  let id = sessionStorage.getItem('mediscanner_session_id')
  if (!id) {
    id = 'user_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36)
    sessionStorage.setItem('mediscanner_session_id', id)
  }
  return id
}
const SESSION_ID = getSessionId()

// 탭/브라우저 닫힐 때 자동 삭제
window.addEventListener('beforeunload', () => {
  navigator.sendBeacon(`${API_URL}/api/cleanup/${SESSION_ID}`)
})

export default function App() {
  const [screen, setScreen] = useState('splash')
  const [activeTab, setActiveTab] = useState('chat')
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [chatMessages, setChatMessages] = useState([])
  const [chatInitialized, setChatInitialized] = useState(false)
  const [answerMode, setAnswerMode] = useState('simple')
  const [selectedModel, setSelectedModel] = useState('e5-large')

  // 카메라 탭 상태 유지
  const [cameraImage, setCameraImage] = useState(null)
  const [cameraPreview, setCameraPreview] = useState(null)
  const [cameraResult, setCameraResult] = useState(null)

  // 약검색 탭 상태 유지
  const [medicineQuery, setMedicineQuery] = useState('')
  const [medicineResult, setMedicineResult] = useState(null)
  const [medicineSearched, setMedicineSearched] = useState(false)

  // AI 건강 분석 결과 캐시
  const [analysisResult, setAnalysisResult] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)

  const clearUserData = async () => {
    try {
      await fetch(`${API_URL}/api/profile/${SESSION_ID}`, { method: 'DELETE' })
      await fetch(`${API_URL}/api/history/${SESSION_ID}`, { method: 'DELETE' })
    } catch (e) {}
    setChatMessages([])
    setChatInitialized(false)
    setAnswerMode('simple')
    setCameraImage(null)
    setCameraPreview(null)
    setCameraResult(null)
    setMedicineQuery('')
    setMedicineResult(null)
    setMedicineSearched(false)
    setAnalysisResult(null)
    setAnalysisLoading(false)
  }

  const handleSplashDone = async () => {
    try {
      const res = await fetch(`${API_URL}/api/profile/${SESSION_ID}`)
      const data = await res.json()
      if (data.status === 'ok' && data.profile) {
        setScreen('main')
        return
      }
    } catch (e) {}
    setScreen('profile')
  }

  const handleGoHome = async () => {
    await clearUserData()
    setScreen('splash')
    setActiveTab('chat')
  }

  const handleExitApp = async () => {
    await clearUserData()
    setScreen('exit')
    setShowExitConfirm(false)
  }

  const tabs = [
    { id: 'chat', icon: '💬', label: 'AI 상담' },
    { id: 'camera', icon: '📷', label: '약 스캔' },
    { id: 'medicine', icon: '💊', label: '약 검색' },
    { id: 'profile', icon: '👤', label: '내 정보' },
  ]

  const PhoneFrame = ({ children }) => (
    <div className="flex items-center justify-center min-h-screen" style={{ background: '#F5EED6' }}>
      <div style={{
        width: 375, height: 720, borderRadius: 40, border: '8px solid #1A1206',
        overflow: 'hidden', boxShadow: '0 20px 60px rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.1) inset',
        position: 'relative', background: '#FFFDF5',
      }}>
        <div style={{ position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)', width: 150, height: 28, background: '#1A1206', borderRadius: '0 0 18px 18px', zIndex: 100 }}>
          <div style={{ position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)', width: 60, height: 6, background: '#333', borderRadius: 3 }} />
        </div>
        <div style={{ position: 'absolute', bottom: 6, left: '50%', transform: 'translateX(-50%)', width: 120, height: 4, background: 'rgba(0,0,0,0.2)', borderRadius: 2, zIndex: 100 }} />
        {children}
      </div>
    </div>
  )

  if (screen === 'exit') {
    return (
      <PhoneFrame>
        <div className="flex flex-col items-center justify-center h-full" style={{
          background: 'radial-gradient(ellipse at 50% 30%, #FFF8E0 0%, #FFE9A0 25%, #F5D670 50%, #E8C44A 75%, #D4A830 100%)',
        }}>
          <div style={{ position: 'relative', width: 120, height: 120, marginBottom: 12 }}>
            <img src="/logo.png" alt="메디스캐너" style={{
              width: 120, height: 120,
              filter: 'sepia(40%) saturate(70%) brightness(1.05)',
              WebkitMaskImage: 'radial-gradient(circle, black 62%, transparent 78%)',
              maskImage: 'radial-gradient(circle, black 62%, transparent 78%)',
              opacity: 0.95,
            }} />
          </div>
          <h2 style={{ fontSize: 28, color: '#5A3E00', fontWeight: 800, letterSpacing: 2 }}>메디스캐너</h2>
          <p style={{ fontSize: 16, color: '#8B6914', fontWeight: 600, letterSpacing: 4, marginTop: 2 }}>MEDISCANNER</p>
          <div style={{ width: 100, height: 2, background: 'linear-gradient(90deg, transparent, #B8860B, transparent)', borderRadius: 2, marginTop: 10 }} />
          <p style={{ fontSize: 15, color: '#5A3E00', marginTop: 14, fontWeight: 600 }}>이용해 주셔서 감사합니다</p>
          <p style={{ fontSize: 14, color: '#7A1A1A', marginTop: 6, fontWeight: 700 }}><span style={{ fontSize: 18 }}>☑</span> 모든 개인정보가 안전하게 삭제되었습니다</p>
          <button onClick={() => setScreen('splash')} className="mt-8"
            style={{ padding: '12px 40px', background: 'linear-gradient(135deg, #5A3E00, #7A5A10, #5A3E00)', borderRadius: 28, border: '1px solid rgba(90,62,0,0.3)', color: '#FFF8E0', fontSize: 15, fontWeight: 700, cursor: 'pointer', letterSpacing: 2 }}>
            다시 시작하기
          </button>
        </div>
      </PhoneFrame>
    )
  }

  if (screen === 'splash') {
    return (<PhoneFrame><SplashScreen onStart={handleSplashDone} /></PhoneFrame>)
  }

  if (screen === 'profile') {
    return (
      <PhoneFrame>
        <ProfileSetup apiUrl={API_URL} sessionId={SESSION_ID}
          onComplete={() => { setScreen('main'); setActiveTab('profile') }}
          onSkip={() => { setScreen('main'); setActiveTab('chat') }}
          onExit={() => setShowExitConfirm(true)} />
        {showExitConfirm && (
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ background: 'white', borderRadius: 16, padding: '24px 20px', width: 280, textAlign: 'center', boxShadow: '0 10px 40px rgba(0,0,0,0.3)' }}>
              <p style={{ fontSize: 16, fontWeight: 700, color: '#2A1D08' }}>앱을 종료하시겠어요?</p>
              <p style={{ fontSize: 13, color: '#8B7A50', marginTop: 8, lineHeight: 1.6 }}>종료하면 모든 개인정보와 상담 히스토리가 삭제됩니다.</p>
              <div className="flex gap-2 mt-5">
                <button onClick={() => setShowExitConfirm(false)} className="flex-1 py-2.5 rounded-full"
                  style={{ fontSize: 14, fontWeight: 600, background: '#F5F0E6', color: '#8B7A50', border: '1px solid #E0D0A0' }}>취소</button>
                <button onClick={handleExitApp} className="flex-1 py-2.5 rounded-full"
                  style={{ fontSize: 14, fontWeight: 700, background: '#CC3333', color: 'white', border: 'none' }}>종료하기</button>
              </div>
            </div>
          </div>
        )}
      </PhoneFrame>
    )
  }

  return (
    <PhoneFrame>
      <div className="flex flex-col h-full">
        {/* 헤더 */}
        <div className="flex items-center justify-between shrink-0" style={{ background: 'linear-gradient(135deg, #FFD700, #DAA520, #B8860B)', padding: '36px 20px 10px', boxShadow: '0 4px 20px rgba(218,165,32,0.2)' }}>
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
          <button onClick={() => setShowExitConfirm(true)}
            style={{
              background: 'rgba(255,255,255,0.25)',
              border: '1.5px solid rgba(255,255,255,0.5)',
              borderRadius: 20,
              padding: '4px 14px',
              color: '#3A1A00',
              fontSize: 13,
              fontWeight: 700,
              cursor: 'pointer',
              letterSpacing: 1,
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}>
            <span style={{ fontSize: 16, fontWeight: 900 }}>⊠</span> 종료
          </button>
        </div>

        {/* 종료 확인 팝업 */}
        {showExitConfirm && (
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ background: 'white', borderRadius: 16, padding: '24px 20px', width: 280, textAlign: 'center', boxShadow: '0 10px 40px rgba(0,0,0,0.3)' }}>
              <p style={{ fontSize: 16, fontWeight: 700, color: '#2A1D08' }}>앱을 종료하시겠어요?</p>
              <p style={{ fontSize: 13, color: '#8B7A50', marginTop: 8, lineHeight: 1.6 }}>종료하면 모든 개인정보와 상담 히스토리가 삭제됩니다.</p>
              <div className="flex gap-2 mt-5">
                <button onClick={() => setShowExitConfirm(false)} className="flex-1 py-2.5 rounded-full"
                  style={{ fontSize: 14, fontWeight: 600, background: '#F5F0E6', color: '#8B7A50', border: '1px solid #E0D0A0' }}>취소</button>
                <button onClick={handleExitApp} className="flex-1 py-2.5 rounded-full"
                  style={{ fontSize: 14, fontWeight: 700, background: '#CC3333', color: 'white', border: 'none' }}>종료하기</button>
              </div>
            </div>
          </div>
        )}

        {/* 4탭 */}
        <div className="flex shrink-0" style={{ background: '#FFF8E0', borderBottom: '1.5px solid #D4B860' }}>
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} className="flex-1 text-center"
              style={{
                fontSize: 12, fontWeight: activeTab === tab.id ? 800 : 500,
                color: activeTab === tab.id ? '#5A3E00' : '#B0A080',
                background: activeTab === tab.id ? 'linear-gradient(180deg, #FFE566, #FFD700)' : 'transparent',
                borderBottom: activeTab === tab.id ? '3px solid #B8860B' : '3px solid transparent',
                borderRight: '1px solid #EDE0B0',
                transition: 'all 0.15s',
                padding: '2px 0',
              }}>
              <div style={{ fontSize: 20 }}>{tab.icon}</div>
              <div style={{ marginTop: 1 }}>{tab.label}</div>
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-hidden">
          {activeTab === 'chat' && <ChatWindow apiUrl={API_URL} sessionId={SESSION_ID} messages={chatMessages} setMessages={setChatMessages} initialized={chatInitialized} setInitialized={setChatInitialized} answerMode={answerMode} setAnswerMode={setAnswerMode} selectedModel={selectedModel} setSelectedModel={setSelectedModel} />}
          {activeTab === 'camera' && <CameraOCR apiUrl={API_URL} image={cameraImage} setImage={setCameraImage} preview={cameraPreview} setPreview={setCameraPreview} result={cameraResult} setResult={setCameraResult} />}
          {activeTab === 'medicine' && <MedicineSearch apiUrl={API_URL} query={medicineQuery} setQuery={setMedicineQuery} result={medicineResult} setResult={setMedicineResult} searched={medicineSearched} setSearched={setMedicineSearched} />}
          {activeTab === 'profile' && <MyProfile apiUrl={API_URL} sessionId={SESSION_ID} analysisResult={analysisResult} setAnalysisResult={setAnalysisResult} analysisLoading={analysisLoading} setAnalysisLoading={setAnalysisLoading} />}
        </div>
      </div>
    </PhoneFrame>
  )
}
