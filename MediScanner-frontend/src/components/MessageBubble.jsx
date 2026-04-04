export function SourceBadge({ source }) {
  return (
    <span
      className="font-medium"
      style={{
        background: 'linear-gradient(135deg, #FFF3D0, #FFECB3)',
        color: '#8B6914',
        padding: '3px 10px',
        borderRadius: 10,
        border: '1px solid rgba(218,165,32,0.2)',
        fontSize: 11,
      }}
    >
      {source}
    </span>
  )
}

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div
          className="max-w-[240px]"
          style={{
            background: 'linear-gradient(135deg, #FFD700, #DAA520)',
            borderRadius: '18px 18px 4px 18px',
            padding: '13px 15px',
            boxShadow: '0 2px 10px rgba(255,215,0,0.25)',
          }}
        >
          <p style={{ fontSize: 15, color: '#1A1206', fontWeight: 600, lineHeight: 1.5 }}>
            {message.text}
          </p>
        </div>
      </div>
    )
  }

  // AI 답변
  const sources = message.sources || []
  const drugs = message.detected_drugs || []
  const hasDrugApi = message.has_drug_api || false
  const tokens = message.tokens || {}

  // 출처 이름 추출
  const sourceNames = sources
    .map(s => s.source || s.source_spec || '')
    .filter(s => s)
    .filter((v, i, a) => a.indexOf(v) === i)

  return (
    <div className="flex gap-2 mb-4">
      {/* AI 아바타 */}
      <div
        className="shrink-0 flex items-center justify-center"
        style={{
          width: 36,
          height: 36,
          borderRadius: '50%',
          background: 'linear-gradient(145deg, #FFD700, #B8860B)',
          overflow: 'hidden',
          flexShrink: 0,
          marginLeft: -6,
        }}
      >
        <img src="/logo.png" alt="메디스캐너" style={{ width: 36, height: 36, objectFit: 'contain' }} />
      </div>

      {/* 답변 말풍선 */}
      <div
        className="max-w-[280px]"
        style={{
          background: 'white',
          border: '1px solid #E8DCC0',
          borderRadius: '18px 18px 18px 4px',
          padding: '13px 15px',
          boxShadow: '0 1px 4px rgba(218,165,32,0.06)',
        }}
      >
        {/* 답변 텍스트 */}
        <div style={{ fontSize: 15, color: '#2A1D08', fontWeight: 500, lineHeight: 1.7 }}>
          {message.text
            ? message.text
                .replace(/\n*([①②③④⑤⑥⑦⑧])/g, '\n$1')
                .replace(/\n*(💊)/g, '\n\n$1')
                .replace(/\n*(●\s)/g, '\n● ')
                .replace(/\n{3,}/g, '\n\n')
                .replace(/^\n+/, '')
                .split('\n')
                .map((line, i) => {
                  const DANGER_KEYWORDS = /병용금기|복용금지|즉시 병원|즉시 내원|혈당 상승|혈압 상승|⚠️|❌/
                  const isDanger = DANGER_KEYWORDS.test(line)
                  // **텍스트** 파란색 처리
                  const parts = line.split(/(\*\*[^*]+\*\*)/)
                  return (
                    <p key={i} style={{
                      margin: '2px 0',
                      color: isDanger ? '#CC2200' : '#2A1D08',
                      fontWeight: isDanger ? 700 : 500,
                      background: isDanger ? 'rgba(204,34,0,0.05)' : 'transparent',
                      borderLeft: isDanger ? '3px solid #CC2200' : 'none',
                      paddingLeft: isDanger ? 8 : 0,
                      borderRadius: isDanger ? 4 : 0,
                      whiteSpace: 'pre-wrap',
                    }}>
                      {parts.map((part, j) =>
                        part.startsWith('**') && part.endsWith('**')
                          ? <span key={j} style={{ color: '#CC0000', fontWeight: 700 }}>{part.slice(2, -2)}</span>
                          : part
                      )}
                    </p>
                  )
                })
            : ''}
        </div>

        {/* 등록된 기저질환 */}
        {message.profileDiseases && (
          <div className="mt-2" style={{ paddingTop: 2, paddingBottom: 2, paddingLeft: 10, paddingRight: 10, background: '#F0F7FF', borderRadius: 8, border: '1px solid #B8D4F0', lineHeight: 1.6 }}>
            <span style={{ fontSize: 13, color: '#5B8DB8', fontWeight: 700 }}>기저질환 정보 : </span>
            <span style={{ fontSize: 13, color: '#1A4F80', fontWeight: 800 }}>{message.profileDiseases}</span>
          </div>
        )}

        {/* 약 감지 표시 */}
        {drugs.length > 0 && (
          <div
            className="mt-2.5"
            style={{
              padding: '9px 12px',
              background: 'linear-gradient(135deg, #FFF8E0, #FFF3D0)',
              borderLeft: '3px solid #FFD700',
              borderRadius: '0 10px 10px 0',
            }}
          >
            <div style={{ fontSize: 13, color: '#8B6914', fontWeight: 700 }}>
              감지된 의약품: {drugs.join(', ')}
            </div>
            {hasDrugApi && (
              <div style={{ fontSize: 11, color: '#999', marginTop: 3 }}>
                식약처 API 직접 조회
              </div>
            )}
          </div>
        )}

        {/* 출처 뱃지 */}
        {sourceNames.length > 0 && (
          <div className="mt-2.5">
            <span style={{ fontSize: 11, color: '#A89060', fontWeight: 600 }}>출처 </span>
            <div className="flex gap-1 flex-wrap mt-1">
              {sourceNames.slice(0, 3).map((src, i) => (
                <SourceBadge key={i} source={src} />
              ))}
            </div>
          </div>
        )}

        {/* 토큰 정보 */}
        {tokens.input && (
          <div className="mt-1.5" style={{ fontSize: 10, color: '#BBB' }}>
            입력: {tokens.input}t / 출력: {tokens.output}t
          </div>
        )}
      </div>
    </div>
  )
}
