"""
MediScanner 검색 정확도 평가 질문 200개 (v3)
=========================================
Hit 판정 기준:
  - must 키워드 1개 이상 AND context 키워드 1개 이상 (동시 충족)
  - context: 한국어 2개 + 영어 2개 = 총 3~4개

구성:
  BASIC_QA_100 : 기본 질문 100개 (직접적 의학 용어)
  HARD_QA_100  : 추론 질문 100개 (고령자 구어체)
  EVAL_QA_200  : 전체 200개
"""

# ============================================================
# 기본 질문 100개
# ============================================================
BASIC_QA_100 = [
    # === 증상-질병 기본 (20개) ===
    {"question": '고혈압 증상은 무엇인가요?',
     "must": ['고혈압', 'hypertension'],
     "context": ['증상', '두통', 'symptoms', 'headache'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '당뇨병의 초기 증상이 뭐예요?',
     "must": ['당뇨', 'diabetes'],
     "context": ['증상', '갈증', 'symptoms', 'thirst'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '뇌졸중 증상을 알려주세요',
     "must": ['뇌졸중', 'stroke'],
     "context": ['증상', '마비', 'symptoms', 'paralysis'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '심근경색 증상은?',
     "must": ['심근경색', 'myocardial infarction', 'heart attack'],
     "context": ['증상', '흉통', 'symptoms', 'chest pain'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '폐렴 증상이 어떻게 되나요?',
     "must": ['폐렴', 'pneumonia'],
     "context": ['증상', '기침', 'symptoms', 'cough'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '갑상선기능저하증 증상은?',
     "must": ['갑상선', 'hypothyroidism'],
     "context": ['저하', '증상', 'symptoms', 'fatigue'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '빈혈 증상을 알려주세요',
     "must": ['빈혈', 'anemia'],
     "context": ['증상', '피로', 'symptoms', 'fatigue'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '골다공증이란 무엇인가요?',
     "must": ['골다공증', 'osteoporosis'],
     "context": ['뼈', '골밀도', 'bone', 'density'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '협심증 증상은 무엇인가요?',
     "must": ['협심증', 'angina'],
     "context": ['증상', '흉통', 'symptoms', 'chest pain'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '위염 증상이 뭐예요?',
     "must": ['위염', 'gastritis'],
     "context": ['증상', '복통', 'symptoms', 'abdominal'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '대장암 초기 증상은?',
     "must": ['대장암', 'colon cancer'],
     "context": ['증상', '혈변', 'symptoms', 'blood stool'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '관절염 증상 알려주세요',
     "must": ['관절염', 'arthritis'],
     "context": ['증상', '통증', 'symptoms', 'pain'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '천식 증상은?',
     "must": ['천식', 'asthma'],
     "context": ['증상', '호흡곤란', 'symptoms', 'breathing'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '치매 초기 증상이 뭔가요?',
     "must": ['치매', 'dementia'],
     "context": ['증상', '기억', 'symptoms', 'memory'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '파킨슨병 증상은 무엇인가요?',
     "must": ['파킨슨', 'Parkinson'],
     "context": ['증상', '떨림', 'symptoms', 'tremor'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '통풍 증상을 알려주세요',
     "must": ['통풍', 'gout'],
     "context": ['증상', '관절', 'symptoms', 'joint'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '신부전 증상은?',
     "must": ['신부전', 'renal failure', 'kidney failure'],
     "context": ['증상', '부종', 'symptoms', 'edema'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '간경화 증상이 뭐예요?',
     "must": ['간경화', 'cirrhosis'],
     "context": ['증상', '황달', 'symptoms', 'jaundice'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '우울증 증상은 무엇인가요?',
     "must": ['우울증', 'depression'],
     "context": ['증상', '무기력', 'symptoms', 'fatigue'],
     "category": '증상-질병', "difficulty": 'basic'},

    {"question": '불안장애 증상 알려주세요',
     "must": ['불안장애', 'anxiety disorder'],
     "context": ['증상', '불안', 'symptoms', 'anxiety'],
     "category": '증상-질병', "difficulty": 'basic'},

    # === 생활습관-영향 기본 (15개) ===
    {"question": '흡연이 건강에 미치는 영향은?',
     "must": ['흡연', 'smoking'],
     "context": ['담배', '건강', 'health', 'lung cancer'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '음주가 간에 미치는 영향',
     "must": ['음주', 'alcohol'],
     "context": ['알코올', '간', 'liver', 'liver disease'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '운동의 건강 효과는?',
     "must": ['운동', 'exercise'],
     "context": ['건강', '심혈관', 'health', 'cardiovascular'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '수면 부족이 건강에 미치는 영향',
     "must": ['수면', 'sleep'],
     "context": ['부족', '건강', 'deprivation', 'health'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '스트레스가 몸에 미치는 영향은?',
     "must": ['스트레스', 'stress'],
     "context": ['건강', '코르티솔', 'health', 'cortisol'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '비만이 건강에 미치는 영향',
     "must": ['비만', 'obesity'],
     "context": ['건강', '당뇨', 'health', 'diabetes'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '카페인이 몸에 미치는 영향은?',
     "must": ['카페인', 'caffeine'],
     "context": ['커피', '건강', 'coffee', 'health'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '나트륨 과다 섭취의 위험은?',
     "must": ['나트륨', 'sodium'],
     "context": ['소금', '고혈압', 'salt', 'hypertension'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '좌식 생활의 건강 위험',
     "must": ['좌식', 'sedentary'],
     "context": ['앉아있기', '혈전', 'sitting', 'health risk'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '당분 과다 섭취의 영향은?',
     "must": ['당분', 'sugar'],
     "context": ['설탕', '비만', 'obesity', 'diabetes'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '규칙적인 식사의 중요성',
     "must": ['식사', 'meal'],
     "context": ['규칙적', '소화', 'digestion', 'metabolism'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '수분 섭취의 중요성은?',
     "must": ['수분', 'hydration'],
     "context": ['물', '탈수', 'water', 'dehydration'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '과식이 건강에 미치는 영향',
     "must": ['과식', 'overeating'],
     "context": ['비만', '소화', 'obesity', 'digestion'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '불규칙한 수면의 영향은?',
     "must": ['수면', 'sleep'],
     "context": ['불규칙', '생체리듬', 'irregular', 'circadian rhythm'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    {"question": '적절한 운동량은 얼마인가요?',
     "must": ['운동', 'exercise'],
     "context": ['운동량', '권장', 'recommended', 'weekly'],
     "category": '생활습관-영향', "difficulty": 'basic'},

    # === 음식-약물 기본 (15개) ===
    {"question": '자몽과 약물 상호작용은?',
     "must": ['자몽', 'grapefruit'],
     "context": ['약물', '상호작용', 'drug', 'interaction'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '와파린과 비타민K 상호작용',
     "must": ['와파린', 'warfarin'],
     "context": ['비타민K', '상호작용', 'vitamin K', 'interaction'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '칼슘과 항생제 상호작용은?',
     "must": ['항생제', 'antibiotic'],
     "context": ['칼슘', '상호작용', 'calcium', 'absorption'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '철분제와 차의 상호작용',
     "must": ['철분', 'iron'],
     "context": ['차', '탄닌', 'tea', 'tannin'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '알코올과 약물 상호작용은?',
     "must": ['알코올', 'alcohol'],
     "context": ['약물', '상호작용', 'drug', 'interaction'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '우유와 항생제 상호작용',
     "must": ['항생제', 'antibiotic'],
     "context": ['우유', '칼슘', 'milk', 'calcium'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '칼륨과 고혈압약 상호작용은?',
     "must": ['칼륨', 'potassium'],
     "context": ['고혈압약', '상호작용', 'antihypertensive', 'interaction'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '비타민C와 철분 상호작용',
     "must": ['철분', 'iron'],
     "context": ['비타민C', '흡수', 'vitamin C', 'absorption'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '감초와 고혈압약 상호작용은?',
     "must": ['감초', 'licorice'],
     "context": ['고혈압', '상호작용', 'blood pressure', 'interaction'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '세인트존스워트 약물 상호작용',
     "must": ['세인트존스워트', "St. John's wort"],
     "context": ['약물', '상호작용', 'drug', 'interaction'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '오메가3와 항응고제 상호작용은?',
     "must": ['오메가3', 'omega-3'],
     "context": ['항응고제', '상호작용', 'anticoagulant', 'bleeding'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '콩과 갑상선약 상호작용',
     "must": ['갑상선', 'thyroid'],
     "context": ['콩', '상호작용', 'soy', 'interaction'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '마그네슘과 약물 상호작용은?',
     "must": ['마그네슘', 'magnesium'],
     "context": ['약물', '상호작용', 'drug', 'interaction'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '은행잎과 항혈소판제 상호작용',
     "must": ['은행잎', 'ginkgo'],
     "context": ['항혈소판', '상호작용', 'antiplatelet', 'bleeding'],
     "category": '음식-약물', "difficulty": 'basic'},

    {"question": '고섬유질 식품과 약물 흡수',
     "must": ['섬유질', 'fiber'],
     "context": ['약물', '흡수', 'drug', 'absorption'],
     "category": '음식-약물', "difficulty": 'basic'},

    # === 음식-질병 기본 (10개) ===
    {"question": '당뇨병 환자 식단 추천',
     "must": ['당뇨', 'diabetes'],
     "context": ['식단', '음식', 'diet', 'food'],
     "category": '음식-질병', "difficulty": 'basic'},

    {"question": '고혈압 환자가 피해야 할 음식은?',
     "must": ['고혈압', 'hypertension'],
     "context": ['음식', '나트륨', 'food', 'sodium'],
     "category": '음식-질병', "difficulty": 'basic'},

    {"question": '통풍 환자 식이요법',
     "must": ['통풍', 'gout'],
     "context": ['식이', '퓨린', 'diet', 'purine'],
     "category": '음식-질병', "difficulty": 'basic'},

    {"question": '신장병 환자가 주의할 음식',
     "must": ['신장', 'kidney'],
     "context": ['음식', '단백질', 'food', 'protein'],
     "category": '음식-질병', "difficulty": 'basic'},

    {"question": '위염에 좋은 음식은?',
     "must": ['위염', 'gastritis'],
     "context": ['음식', '소화', 'food', 'digestion'],
     "category": '음식-질병', "difficulty": 'basic'},

    {"question": '빈혈에 좋은 음식',
     "must": ['빈혈', 'anemia'],
     "context": ['음식', '철분', 'food', 'iron'],
     "category": '음식-질병', "difficulty": 'basic'},

    {"question": '골다공증에 좋은 음식은?',
     "must": ['골다공증', 'osteoporosis'],
     "context": ['음식', '칼슘', 'food', 'calcium'],
     "category": '음식-질병', "difficulty": 'basic'},

    {"question": '변비에 좋은 음식',
     "must": ['변비', 'constipation'],
     "context": ['음식', '섬유질', 'food', 'fiber'],
     "category": '음식-질병', "difficulty": 'basic'},

    {"question": '간 건강에 좋은 음식은?',
     "must": ['간', 'liver'],
     "context": ['건강', '음식', 'health', 'food'],
     "category": '음식-질병', "difficulty": 'basic'},

    {"question": '심장 건강에 좋은 음식',
     "must": ['심장', 'heart'],
     "context": ['건강', '음식', 'health', 'food'],
     "category": '음식-질병', "difficulty": 'basic'},

    # === 복합질환 기본 (15개) ===
    {"question": '당뇨병 합병증에는 무엇이 있나요?',
     "must": ['당뇨', 'diabetes'],
     "context": ['합병증', '신경병증', 'complications', 'neuropathy'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '고혈압 합병증은?',
     "must": ['고혈압', 'hypertension'],
     "context": ['합병증', '뇌졸중', 'complications', 'stroke'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '비만과 당뇨병의 관계',
     "must": ['비만', 'obesity'],
     "context": ['당뇨', '인슐린', 'diabetes', 'insulin'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '당뇨와 심혈관질환 연관성',
     "must": ['당뇨', 'diabetes'],
     "context": ['심혈관', '관계', 'cardiovascular', 'relationship'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '고혈압과 신장질환 관계는?',
     "must": ['고혈압', 'hypertension'],
     "context": ['신장', '관계', 'kidney', 'relationship'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '갑상선과 심장 관련성',
     "must": ['갑상선', 'thyroid'],
     "context": ['심장', '관계', 'heart', 'relationship'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '폐경과 골다공증 관계',
     "must": ['폐경', 'menopause'],
     "context": ['골다공증', '에스트로겐', 'osteoporosis', 'estrogen'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '우울증과 신체 증상 관계는?',
     "must": ['우울증', 'depression'],
     "context": ['신체', '증상', 'physical', 'symptoms'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '수면무호흡과 고혈압 연관',
     "must": ['수면무호흡', 'sleep apnea'],
     "context": ['고혈압', '관계', 'hypertension', 'relationship'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '비만과 관절염 관계',
     "must": ['비만', 'obesity'],
     "context": ['관절염', '무릎', 'arthritis', 'knee'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '당뇨병성 신경병증이란?',
     "must": ['당뇨', 'diabetic neuropathy'],
     "context": ['신경병증', '저림', 'neuropathy', 'numbness'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '당뇨병성 망막병증 설명',
     "must": ['당뇨', 'diabetic retinopathy'],
     "context": ['망막병증', '실명', 'retinopathy', 'blindness'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '대사증후군이란 무엇인가요?',
     "must": ['대사증후군', 'metabolic syndrome'],
     "context": ['비만', '혈압', 'obesity'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '류마티스 관절염 합병증은?',
     "must": ['류마티스', 'rheumatoid arthritis'],
     "context": ['합병증', '심혈관', 'complications'],
     "category": '복합질환', "difficulty": 'basic'},

    {"question": '만성신장질환 합병증',
     "must": ['신장', 'chronic kidney disease'],
     "context": ['만성', '합병증', 'complications', 'anemia'],
     "category": '복합질환', "difficulty": 'basic'},

    # === 약물부작용 기본 (15개) ===
    {"question": '아스피린 부작용은?',
     "must": ['아스피린', 'aspirin'],
     "context": ['부작용', '위출혈', 'side effects', 'gastric bleeding'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '이부프로펜 부작용',
     "must": ['이부프로펜', 'ibuprofen'],
     "context": ['부작용', '위장', 'side effects', 'gastric'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '스타틴 부작용은 무엇인가요?',
     "must": ['스타틴', 'statin'],
     "context": ['부작용', '근육통', 'side effects', 'muscle pain'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '메트포르민 부작용',
     "must": ['메트포르민', 'metformin'],
     "context": ['부작용', '소화', 'side effects', 'gastrointestinal'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '혈압약 부작용은?',
     "must": ['혈압약', 'antihypertensive'],
     "context": ['부작용', '어지러움', 'side effects', 'dizziness'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '항생제 부작용',
     "must": ['항생제', 'antibiotic'],
     "context": ['부작용', '설사', 'side effects', 'diarrhea'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '수면제 부작용은 무엇인가요?',
     "must": ['수면제', 'sleeping pill'],
     "context": ['부작용', '졸음', 'side effects', 'drowsiness'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '진통제 부작용',
     "must": ['진통제', 'painkiller'],
     "context": ['부작용', '위장', 'side effects', 'gastrointestinal'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '항우울제 부작용은?',
     "must": ['항우울제', 'antidepressant'],
     "context": ['부작용', '졸음', 'side effects', 'drowsiness'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '스테로이드 부작용',
     "must": ['스테로이드', 'steroid'],
     "context": ['부작용', '골다공증', 'side effects', 'osteoporosis'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '이뇨제 부작용은 무엇인가요?',
     "must": ['이뇨제', 'diuretic'],
     "context": ['부작용', '전해질', 'side effects', 'electrolyte'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '베타차단제 부작용',
     "must": ['베타차단제', 'beta blocker'],
     "context": ['부작용', '피로', 'side effects', 'fatigue'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": 'ACE억제제 부작용은?',
     "must": ['ACE억제제', 'ACE inhibitor'],
     "context": ['부작용', '기침', 'side effects', 'cough'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '오피오이드 부작용',
     "must": ['오피오이드', 'opioid'],
     "context": ['부작용', '변비', 'side effects', 'constipation'],
     "category": '약물부작용', "difficulty": 'basic'},

    {"question": '항히스타민제 부작용은 무엇인가요?',
     "must": ['항히스타민제', 'antihistamine'],
     "context": ['부작용', '졸음', 'side effects', 'drowsiness'],
     "category": '약물부작용', "difficulty": 'basic'},

    # === 예방관리 기본 (10개) ===
    {"question": '고혈압 예방법은?',
     "must": ['고혈압', 'hypertension'],
     "context": ['예방', '생활습관', 'prevention', 'lifestyle'],
     "category": '예방관리', "difficulty": 'basic'},

    {"question": '당뇨병 예방법',
     "must": ['당뇨', 'diabetes'],
     "context": ['예방', '식단', 'prevention', 'diet'],
     "category": '예방관리', "difficulty": 'basic'},

    {"question": '심장병 예방하는 방법은?',
     "must": ['심장병', 'heart disease'],
     "context": ['예방', '운동', 'prevention'],
     "category": '예방관리', "difficulty": 'basic'},

    {"question": '뇌졸중 예방법',
     "must": ['뇌졸중', 'stroke'],
     "context": ['예방', '혈압관리', 'prevention', 'blood pressure'],
     "category": '예방관리', "difficulty": 'basic'},

    {"question": '암 예방하는 생활습관은?',
     "must": ['암', 'cancer'],
     "context": ['예방', '생활습관', 'prevention', 'lifestyle'],
     "category": '예방관리', "difficulty": 'basic'},

    {"question": '골다공증 예방법',
     "must": ['골다공증', 'osteoporosis'],
     "context": ['예방', '칼슘', 'prevention', 'calcium'],
     "category": '예방관리', "difficulty": 'basic'},

    {"question": '치매 예방하는 방법은?',
     "must": ['치매', 'dementia'],
     "context": ['예방', '인지', 'prevention', 'cognitive'],
     "category": '예방관리', "difficulty": 'basic'},

    {"question": '감기 예방법',
     "must": ['감기', 'cold'],
     "context": ['예방', '면역', 'prevention', 'immunity'],
     "category": '예방관리', "difficulty": 'basic'},

    {"question": '건강검진 주기는 얼마인가요?',
     "must": ['건강검진', 'health checkup'],
     "context": ['주기', '검사', 'frequency', 'screening'],
     "category": '예방관리', "difficulty": 'basic'},

    {"question": '예방접종 종류와 시기',
     "must": ['예방접종', 'vaccination'],
     "context": ['백신', '시기', 'vaccine', 'schedule'],
     "category": '예방관리', "difficulty": 'basic'},

]


# ============================================================
# 추론 질문 100개 (고령자 구어체)
# ============================================================
HARD_QA_100 = [
    # === 증상-질병 추론 (20개) ===
    {"question": '머리가 어지러운데 이러면 고혈압에 안좋아?',
     "must": ['고혈압', 'hypertension'],
     "context": ['어지러움', '현기증', 'dizziness', 'vertigo'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '요즘 자꾸 목이 마르고 화장실을 자주 가는데 무슨 병이야?',
     "must": ['당뇨', 'diabetes'],
     "context": ['갈증', '다뇨', 'thirst', 'polyuria'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '밤에 다리가 저리고 쥐가 나는데 이거 뭐가 문제야?',
     "must": ['신경', 'neuropathy'],
     "context": ['저림', '경련', 'cramp', 'numbness'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '가슴이 답답하고 숨이 차는데 심장이 안좋은 거야?',
     "must": ['심장', 'heart'],
     "context": ['흉부', '호흡곤란', 'dyspnea', 'chest'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '소변볼 때 찔끔찔끔 나오고 시원하지 않은데 왜 그래?',
     "must": ['전립선', 'prostate'],
     "context": ['배뇨', '비대', 'BPH', 'urination'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '갑자기 한쪽 팔다리에 힘이 없어지면 뭐야?',
     "must": ['뇌졸중', 'stroke'],
     "context": ['마비', '편마비', 'paralysis', 'hemiplegia'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '밥 먹고 나면 자꾸 졸린데 이거 정상이야?',
     "must": ['혈당', 'glucose'],
     "context": ['식후', '졸음', 'postprandial', 'drowsiness'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '눈앞에 벌레 같은 게 떠다니는데 뭐야?',
     "must": ['망막', 'retina'],
     "context": ['비문증', '유리체', 'floaters', 'vitreous'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '자꾸 깜빡깜빡하고 기억이 안 나는데 치매야?',
     "must": ['치매', 'dementia'],
     "context": ['건망증', '인지', 'memory', 'cognitive'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '손발이 자꾸 떨리는데 파킨슨병이야?',
     "must": ['파킨슨', 'Parkinson'],
     "context": ['떨림', '진전', 'tremor', 'shaking'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '밤에 자다가 숨이 막혀서 깨는데 왜 그래?',
     "must": ['수면무호흡', 'sleep apnea'],
     "context": ['코골이', '호흡', 'snoring', 'breathing'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '음식 맛을 잘 못 느끼겠어. 왜 그럴까?',
     "must": ['미각', 'taste'],
     "context": ['후각', '아연', 'smell', 'zinc'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '귀에서 삐- 소리가 계속 나는데 뭐야?',
     "must": ['이명', 'tinnitus'],
     "context": ['귀', '청력', 'ear', 'hearing'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '발바닥이 아침에 일어나면 너무 아파',
     "must": ['족저근막염', 'plantar fasciitis'],
     "context": ['발', '통증', 'heel', 'foot pain'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '눈이 뻑뻑하고 자꾸 충혈돼',
     "must": ['안구건조', 'dry eye'],
     "context": ['눈물', '충혈', 'tears', 'redness'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '입안이 자꾸 헐고 염증이 생겨',
     "must": ['구내염', 'stomatitis'],
     "context": ['점막', '궤양', 'mouth ulcer', 'oral'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '밤에 잠을 못 자고 자꾸 깨',
     "must": ['불면증', 'insomnia'],
     "context": ['수면', '각성', 'sleep', 'wakefulness'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '배가 자꾸 더부룩하고 가스가 차',
     "must": ['소화불량', 'indigestion'],
     "context": ['복부팽만', '가스', 'bloating', 'gas'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '온몸이 가렵고 피부가 건조해',
     "must": ['소양증', 'pruritus'],
     "context": ['건조', '피부', 'itching', 'dry skin'],
     "category": '증상-질병', "difficulty": 'hard'},

    {"question": '걸을 때 종아리가 아프다가 쉬면 괜찮아져',
     "must": ['간헐적파행', 'claudication'],
     "context": ['혈관', '동맥', 'peripheral arterial', 'vascular'],
     "category": '증상-질병', "difficulty": 'hard'},

    # === 생활습관-영향 추론 (15개) ===
    {"question": '술을 많이 먹으면 골다공증에는 어떤 영향이 있어?',
     "must": ['골다공증', 'osteoporosis'],
     "context": ['알코올', '음주', 'alcohol', 'bone'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '매일 술을 마시면 치매 환자는 몇년 더 살 수 있어?',
     "must": ['치매', 'dementia'],
     "context": ['음주', '알코올', 'alcohol', 'prognosis'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '담배 피우면 당뇨병이 더 나빠져?',
     "must": ['흡연', 'smoking'],
     "context": ['당뇨', '혈당', 'diabetes', 'complication'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '커피를 많이 마시면 고혈압 약이 안 듣는다던데 진짜야?',
     "must": ['카페인', 'caffeine'],
     "context": ['고혈압', '약물', 'hypertension', 'interaction'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '운동을 안 하면 심장병 걸리기 쉬워?',
     "must": ['심장', 'cardiovascular'],
     "context": ['운동부족', '좌식', 'sedentary', 'heart disease'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '잠을 못 자면 혈압이 올라가?',
     "must": ['혈압', 'blood pressure'],
     "context": ['수면부족', '불면', 'sleep deprivation', 'insomnia'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '스트레스 많이 받으면 당뇨 조절이 안 돼?',
     "must": ['스트레스', 'stress'],
     "context": ['혈당', '코르티솔', 'glucose', 'cortisol'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '하루 종일 앉아있으면 뭐가 안 좋아?',
     "must": ['좌식생활', 'sedentary'],
     "context": ['혈전', '대사', 'thrombosis', 'metabolism'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '물을 적게 마시면 신장에 안 좋아?',
     "must": ['신장', 'kidney'],
     "context": ['수분', '탈수', 'dehydration', 'water'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '잠을 너무 많이 자도 안 좋아?',
     "must": ['수면', 'sleep'],
     "context": ['과수면', '우울', 'oversleeping', 'depression'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": 'TV를 오래 보면 눈이 나빠져?',
     "must": ['눈', 'vision'],
     "context": ['시력', '피로', 'eye strain', 'myopia'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '늦게까지 핸드폰 보면 왜 잠이 안 와?',
     "must": ['멜라토닌', 'melatonin'],
     "context": ['블루라이트', '수면', 'blue light', 'sleep'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '급하게 밥 먹으면 소화에 안 좋아?',
     "must": ['소화', 'digestion'],
     "context": ['급식', '위', 'eating fast', 'chewing'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '짜게 먹으면 혈압 말고 또 뭐가 안 좋아?',
     "must": ['나트륨', 'sodium'],
     "context": ['소금', '신장', 'salt', 'kidney'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    {"question": '외로우면 진짜 몸도 안 좋아져?',
     "must": ['사회적고립', 'loneliness'],
     "context": ['외로움', '면역', 'isolation', 'immune'],
     "category": '생활습관-영향', "difficulty": 'hard'},

    # === 음식-약물 추론 (15개) ===
    {"question": '혈압약 먹는데 자몽 먹으면 안 된다던데 왜야?',
     "must": ['자몽', 'grapefruit'],
     "context": ['혈압약', '상호작용', 'antihypertensive', 'CYP3A4'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '피 묽게 하는 약 먹는데 시금치 많이 먹어도 돼?',
     "must": ['와파린', 'warfarin'],
     "context": ['비타민K', '시금치', 'vitamin K', 'spinach'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '항생제 먹을 때 우유 마시면 안 돼?',
     "must": ['항생제', 'antibiotic'],
     "context": ['우유', '칼슘', 'milk', 'calcium'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '고혈압약이랑 바나나 같이 먹으면 안 돼?',
     "must": ['칼륨', 'potassium'],
     "context": ['바나나', 'ACE', 'ARB'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '철분제 먹을 때 차 마시면 안 좋아?',
     "must": ['철분', 'iron'],
     "context": ['차', '탄닌', 'tea', 'tannin'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '당뇨약 먹는데 술 마시면 위험해?',
     "must": ['저혈당', 'hypoglycemia'],
     "context": ['당뇨약', '알코올', 'diabetes medication', 'alcohol'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '갑상선약 먹을 때 콩 먹으면 안 돼?',
     "must": ['갑상선', 'thyroid'],
     "context": ['콩', '레보티록신', 'soy', 'levothyroxine'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '골다공증약 먹고 바로 눕으면 안 된다던데?',
     "must": ['비스포스포네이트', 'bisphosphonate'],
     "context": ['식도', '자세', 'esophagus', 'upright'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '진통제랑 술 같이 먹으면 왜 위험해?',
     "must": ['NSAIDs', 'NSAID'],
     "context": ['알코올', '위출혈', 'alcohol', 'gastric bleeding'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '수면제 먹는데 자몽주스 마셔도 돼?',
     "must": ['자몽', 'grapefruit'],
     "context": ['수면제', '벤조디아제핀', 'sleeping pill', 'benzodiazepine'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '혈압약 먹는데 감초 먹어도 돼?',
     "must": ['감초', 'licorice'],
     "context": ['혈압', '저칼륨', 'blood pressure', 'hypokalemia'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '아스피린 먹는데 생강차 많이 마셔도 돼?',
     "must": ['아스피린', 'aspirin'],
     "context": ['생강', '출혈', 'ginger', 'bleeding'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '면역억제제 먹는데 에키네시아 먹어도 돼?',
     "must": ['면역억제제', 'immunosuppressant'],
     "context": ['에키네시아', '상호작용', 'echinacea', 'interaction'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '항우울제 먹는데 세인트존스워트 먹으면 안 돼?',
     "must": ['항우울제', 'antidepressant'],
     "context": ['세인트존스워트', '세로토닌', "St. John's wort", 'serotonin'],
     "category": '음식-약물', "difficulty": 'hard'},

    {"question": '혈전약 먹는데 오메가3 먹어도 돼?',
     "must": ['항응고제', 'anticoagulant'],
     "context": ['오메가3', '출혈', 'omega-3', 'fish oil'],
     "category": '음식-약물', "difficulty": 'hard'},

    # === 음식-질병 추론 (10개) ===
    {"question": '당뇨 있는데 과일 많이 먹어도 괜찮아?',
     "must": ['당뇨', 'diabetes'],
     "context": ['과일', '당분', 'fruit', 'sugar'],
     "category": '음식-질병', "difficulty": 'hard'},

    {"question": '간이 안 좋으면 술 말고 또 뭘 조심해야 해?',
     "must": ['간', 'liver'],
     "context": ['간질환', '해독', 'hepatotoxic', 'protein'],
     "category": '음식-질병', "difficulty": 'hard'},

    {"question": '신장 안 좋은 사람은 바나나 왜 조심해야 해?',
     "must": ['신장', 'kidney'],
     "context": ['칼륨', '바나나', 'potassium', 'banana'],
     "category": '음식-질병', "difficulty": 'hard'},

    {"question": '통풍 있으면 맥주 말고 소주는 괜찮아?',
     "must": ['통풍', 'gout'],
     "context": ['알코올', '요산', 'alcohol', 'uric acid'],
     "category": '음식-질병', "difficulty": 'hard'},

    {"question": '위염 있으면 커피 마시면 안 돼?',
     "must": ['위염', 'gastritis'],
     "context": ['커피', '위산', 'coffee', 'gastric acid'],
     "category": '음식-질병', "difficulty": 'hard'},

    {"question": '변비에 바나나가 좋아 안 좋아?',
     "must": ['변비', 'constipation'],
     "context": ['바나나', '식이섬유', 'banana', 'fiber'],
     "category": '음식-질병', "difficulty": 'hard'},

    {"question": '빈혈인데 철분 말고 뭘 먹어야 해?',
     "must": ['빈혈', 'anemia'],
     "context": ['철분', '비타민C', 'iron', 'vitamin C'],
     "category": '음식-질병', "difficulty": 'hard'},

    {"question": '골다공증에 칼슘만 먹으면 돼?',
     "must": ['골다공증', 'osteoporosis'],
     "context": ['칼슘', '비타민D', 'calcium', 'vitamin D'],
     "category": '음식-질병', "difficulty": 'hard'},

    {"question": '고혈압인데 라면 가끔 먹어도 돼?',
     "must": ['고혈압', 'hypertension'],
     "context": ['나트륨', '라면', 'sodium', 'ramen'],
     "category": '음식-질병', "difficulty": 'hard'},

    {"question": '당뇨인데 꿀은 설탕보다 나아?',
     "must": ['당뇨', 'diabetes'],
     "context": ['꿀', '설탕', 'honey', 'sugar'],
     "category": '음식-질병', "difficulty": 'hard'},

    # === 복합질환 추론 (15개) ===
    {"question": '당뇨 있으면 왜 발 관리를 잘 해야 해?',
     "must": ['당뇨발', 'diabetic foot'],
     "context": ['신경병증', '궤양', 'neuropathy', 'ulcer'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '고혈압이랑 당뇨 같이 있으면 더 위험해?',
     "must": ['고혈압', 'hypertension'],
     "context": ['당뇨', '합병증', 'diabetes', 'complication'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '뚱뚱하면 무릎이 왜 아파?',
     "must": ['비만', 'obesity'],
     "context": ['관절', '무릎', 'knee', 'osteoarthritis'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '우울하면 진짜 몸도 아플 수 있어?',
     "must": ['우울증', 'depression'],
     "context": ['신체증상', '두통', 'somatic', 'fatigue'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '스트레스 받으면 위가 왜 아파?',
     "must": ['스트레스', 'stress'],
     "context": ['위', '위염', 'stomach', 'gastritis'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '당뇨 있으면 눈이 왜 나빠져?',
     "must": ['당뇨망막병증', 'diabetic retinopathy'],
     "context": ['실명', '눈', 'blindness', 'eye'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '고혈압 오래되면 신장이 왜 망가져?',
     "must": ['고혈압', 'hypertension'],
     "context": ['신장', '신부전', 'kidney', 'renal failure'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '심장병 있으면 왜 부종이 생겨?',
     "must": ['심부전', 'heart failure'],
     "context": ['부종', '다리', 'edema', 'leg'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '갑상선 안 좋으면 살이 왜 쪄?',
     "must": ['갑상선저하증', 'hypothyroidism'],
     "context": ['체중', '대사', 'weight gain', 'metabolism'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '폐경되면 뼈가 왜 약해져?',
     "must": ['폐경', 'menopause'],
     "context": ['에스트로겐', '골다공증', 'estrogen', 'osteoporosis'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '수면무호흡 있으면 심장에도 안 좋아?',
     "must": ['수면무호흡', 'sleep apnea'],
     "context": ['심장', '고혈압', 'heart', 'hypertension'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '류마티스 있으면 심장도 안 좋아져?',
     "must": ['류마티스', 'rheumatoid'],
     "context": ['심혈관', '염증', 'cardiovascular', 'inflammation'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '만성 스트레스가 면역에 영향 줘?',
     "must": ['스트레스', 'stress'],
     "context": ['면역', '코르티솔', 'immune', 'cortisol'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '비만하면 암에도 잘 걸려?',
     "must": ['비만', 'obesity'],
     "context": ['암', '위험', 'cancer', 'risk'],
     "category": '복합질환', "difficulty": 'hard'},

    {"question": '불면증이랑 우울증은 무슨 관계야?',
     "must": ['불면증', 'insomnia'],
     "context": ['우울증', '수면', 'depression', 'sleep'],
     "category": '복합질환', "difficulty": 'hard'},

    # === 약물부작용 추론 (15개) ===
    {"question": '혈압약 먹으면 왜 마른 기침이 나와?',
     "must": ['ACE억제제', 'ACE inhibitor'],
     "context": ['기침', '브라디키닌', 'cough', 'bradykinin'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '당뇨약 먹으면 왜 살이 빠져?',
     "must": ['메트포르민', 'metformin'],
     "context": ['체중감소', '식욕', 'weight loss', 'appetite'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '콜레스테롤약 먹으면 근육이 왜 아파?',
     "must": ['스타틴', 'statin'],
     "context": ['근육통', '횡문근융해', 'myalgia', 'rhabdomyolysis'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '수면제 오래 먹으면 어떻게 돼?',
     "must": ['수면제', 'sleeping pill'],
     "context": ['의존성', '내성', 'dependence', 'tolerance'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '진통제 많이 먹으면 위가 상해?',
     "must": ['NSAIDs', 'NSAID'],
     "context": ['위궤양', '출혈', 'gastric ulcer', 'bleeding'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '항생제 먹으면 왜 설사가 나와?',
     "must": ['항생제', 'antibiotic'],
     "context": ['설사', '장내균', 'diarrhea', 'gut flora'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '이뇨제 먹으면 왜 다리에 쥐가 나?',
     "must": ['이뇨제', 'diuretic'],
     "context": ['전해질', '칼륨', 'electrolyte', 'potassium'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '스테로이드 오래 먹으면 뭐가 문제야?',
     "must": ['스테로이드', 'steroid'],
     "context": ['골다공증', '쿠싱', 'osteoporosis', 'Cushing'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '혈압약 먹으면 왜 어지러워?',
     "must": ['혈압약', 'antihypertensive'],
     "context": ['저혈압', '어지러움', 'hypotension', 'dizziness'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '항우울제 먹으면 살이 찌는 거 맞아?',
     "must": ['항우울제', 'antidepressant'],
     "context": ['체중증가', '대사', 'weight gain', 'metabolism'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '아스피린 오래 먹으면 위에 안 좋아?',
     "must": ['아스피린', 'aspirin'],
     "context": ['위출혈', '궤양', 'gastric bleeding', 'ulcer'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '베타차단제 먹으면 왜 피곤해?',
     "must": ['베타차단제', 'beta blocker'],
     "context": ['피로', '서맥', 'fatigue', 'bradycardia'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '당뇨약이 왜 저혈당을 일으켜?',
     "must": ['저혈당', 'hypoglycemia'],
     "context": ['인슐린', '설폰요소제', 'insulin', 'sulfonylurea'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '항히스타민제 먹으면 왜 졸려?',
     "must": ['항히스타민', 'antihistamine'],
     "context": ['졸음', '진정', 'drowsiness', 'sedation'],
     "category": '약물부작용', "difficulty": 'hard'},

    {"question": '프로톤펌프억제제 오래 먹으면?',
     "must": ['PPI', 'proton pump inhibitor'],
     "context": ['골다공증', '마그네슘', 'osteoporosis', 'magnesium'],
     "category": '약물부작용', "difficulty": 'hard'},

    # === 예방관리 추론 (10개) ===
    {"question": '혈압은 얼마나 자주 재야 해?',
     "must": ['혈압', 'blood pressure'],
     "context": ['측정', '주기', 'monitoring', 'frequency'],
     "category": '예방관리', "difficulty": 'hard'},

    {"question": '당뇨 검사는 얼마나 자주 받아야 해?',
     "must": ['당뇨', 'diabetes'],
     "context": ['검사', '혈당', 'screening', 'HbA1c'],
     "category": '예방관리', "difficulty": 'hard'},

    {"question": '대장내시경은 몇 살부터 받아야 해?',
     "must": ['대장내시경', 'colonoscopy'],
     "context": ['나이', '검진', 'age', 'screening'],
     "category": '예방관리', "difficulty": 'hard'},

    {"question": '뼈 검사는 언제 받아야 해?',
     "must": ['골밀도', 'bone density'],
     "context": ['검사', '골다공증', 'screening', 'osteoporosis'],
     "category": '예방관리', "difficulty": 'hard'},

    {"question": '유방암 검진은 몇 살부터야?',
     "must": ['유방암', 'breast cancer'],
     "context": ['검진', '유방촬영', 'screening', 'mammography'],
     "category": '예방관리', "difficulty": 'hard'},

    {"question": '매년 맞아야 하는 예방접종은?',
     "must": ['예방접종', 'vaccination'],
     "context": ['독감', '폐렴구균', 'flu', 'pneumococcal'],
     "category": '예방관리', "difficulty": 'hard'},

    {"question": '노인에게 필요한 영양제는?',
     "must": ['노인', 'elderly'],
     "context": ['영양제', '비타민D', 'supplement', 'vitamin D'],
     "category": '예방관리', "difficulty": 'hard'},

    {"question": '고령자가 피해야 할 운동은?',
     "must": ['노인', 'elderly'],
     "context": ['운동', '낙상', 'exercise', 'fall'],
     "category": '예방관리', "difficulty": 'hard'},

    {"question": '복용약이 많으면 어떻게 관리해?',
     "must": ['다약제', 'polypharmacy'],
     "context": ['약관리', '부작용', 'medication management', 'interaction'],
     "category": '예방관리', "difficulty": 'hard'},

    {"question": '치매 예방을 위한 생활습관은?',
     "must": ['치매', 'dementia'],
     "context": ['예방', '인지', 'prevention', 'cognitive'],
     "category": '예방관리', "difficulty": 'hard'},

]


# ============================================================
# 전체 200개
# ============================================================
EVAL_QA_200 = BASIC_QA_100 + HARD_QA_100
