// 국내 보고 데모 입력입니다. 공개 사례는 원문을 옮기지 않고 요지만 다시 썼으며, 출처를 함께 둡니다.
// text 는 한국어 보고서 그대로가 입력 데이터이므로 언어와 상관없이 한국어로 둡니다.
// 영어 화면에서는 labelEn · sourceEn 을 보여 드리고, textEn(참고용 영어 번역)을 입력란 아래에 함께 보여 드립니다.

export interface KrSample {
  id: string; label: string; labelEn: string; form: 'professional' | 'consumer' | 'narrative'
  source: string; sourceEn: string; sourceUrl?: string; text: string; textEn: string
}

export const KR_SAMPLES: KrSample[] = [
  {
    id: 'niraparib', label: '니라파립 · 혈소판감소증 (의약전문가용 서식, 가상)', form: 'professional',
    labelEn: 'Niraparib · thrombocytopenia (healthcare-professional form, fictional)',
    source: '팀 문서 「국내 PV 흐름 설명」의 가상 환자 A', sourceEn: 'Fictional patient A from the team document "Korean PV workflow explained"',
    textEn: `A. Patient: initials A, 64 years, female, underlying disease ovarian cancer
B. Adverse event: thrombocytopenia, onset 2026-08-03 (platelets 45,000/µL on routine blood test). No hospitalization. Outcome: recovered (platelets 150,000/µL on 2026-08-17)
C. Medicines: suspect drug niraparib 200 mg once daily orally, 2026-07-10 to 2026-08-03, ovarian cancer maintenance; action: stopped, not re-administered
   Concomitant: iron supplement, zolpidem
D. Reporter: pharmacist (community pharmacy)
E. Report: spontaneous report, follow-up to an initial report
F. Overall comment: platelets fell about 3 weeks after starting, recovered 2 weeks after stopping. Bone-marrow metastasis not confirmed. Thrombocytopenia is listed in the approved label`,
    text: `가. 환자정보: 이니셜 A, 64세, 여성, 원질환 난소암
나. 이상사례정보: 혈소판감소증, 발현일 2026-08-03 (정기 혈액검사에서 혈소판 45,000/µL). 입원 없음. 결과: 회복(2026-08-17 혈소판 150,000/µL)
다. 의약품정보: 의심약물 니라파립 200mg 1일 1회 경구, 2026-07-10 ~ 2026-08-03, 난소암 유지요법, 조치: 투여 중단, 재투여 안 함
   병용약물: 철분제, 졸피뎀
라. 보고자정보: 약사 (지역 약국)
마. 보고서정보: 자발보고, 최초 보고 후 추가 보고
바. 종합의견: 복용 약 3주 후 혈소판 감소, 중단 2주 후 회복. 골수 전이 여부는 확인되지 않음. 혈소판감소증은 허가사항에 기재된 반응임`,
  },
  {
    id: 'metformin', label: '메트포르민 · 젖산산증 입원 (의약전문가용, 가상 · 규정 차이 예시)', form: 'professional',
    labelEn: 'Metformin · lactic acidosis with hospitalization (professional form, fictional · regulatory-difference example)',
    source: '규정 모드 비교용 가상 사례 (실제 보고 아님)', sourceEn: 'Fictional case for comparing regulatory modes (not a real report)',
    textEn: `A. Patient: initials K, 78 years, male, 61 kg, type 2 diabetes, chronic kidney disease (eGFR 28)
B. Adverse event: lactic acidosis, onset 2026-09-02, emergency visit for vomiting and shortness of breath, arterial pH 7.08, lactate 9.6 mmol/L. Admitted to ICU. Outcome: recovering
C. Medicines: suspect drug metformin 1000 mg twice daily orally, 2024-03 to 2026-09-02, diabetes; action: stopped
   Concomitant: amlodipine 5 mg, atorvastatin 10 mg
D. Reporter: physician (university hospital, endocrinology)
E. Report: spontaneous report, initial
F. Overall comment: took metformin without dose reduction despite reduced kidney function. Lactic acidosis is listed in the warnings section of the label`,
    text: `가. 환자정보: 이니셜 K, 78세, 남성, 체중 61kg, 원질환 제2형 당뇨병, 만성 신장병(eGFR 28)
나. 이상사례정보: 젖산산증, 발현일 2026-09-02, 구토와 호흡곤란으로 응급실 내원, 동맥혈 pH 7.08, 젖산 9.6 mmol/L. 중환자실 입원. 결과: 회복 중
다. 의약품정보: 의심약물 메트포르민 1000mg 1일 2회 경구, 2024-03 ~ 2026-09-02, 당뇨병, 조치: 투여 중단
   병용약물: 암로디핀 5mg, 아토르바스타틴 10mg
라. 보고자정보: 의사 (대학병원 내분비내과)
마. 보고서정보: 자발보고, 최초 보고
바. 종합의견: 신기능 저하 상태에서 메트포르민을 감량 없이 복용. 젖산산증은 허가사항 경고 항에 기재된 반응임`,
  },
  {
    id: 'tegoprazan', label: '테고프라잔 · 두드러기 (병원 사례, 자유 서술)', form: 'narrative',
    labelEn: 'Tegoprazan · urticaria (hospital case, free narrative)',
    source: '서울대학교병원 약물안전센터 사례 게시물 요약', sourceEn: 'Summary of a case post by the Seoul National University Hospital Drug Safety Center',
    textEn: `A 59-year-old man was prescribed tegoprazan, a P-CAB acid suppressant, for reflux esophagitis. At an outpatient follow-up on day 28 he reported whole-body itching and facial hives. Tegoprazan was stopped, an antihistamine (chlorpheniramine) was injected, and the acid suppressant was switched to esomeprazole. Recurrence is being monitored. The hospital's drug safety center accepted a causal relationship between tegoprazan and the reaction and also reviewed possible cross-hypersensitivity with benzimidazole drugs.`,
    sourceUrl: 'https://dept.snuh.org/dept/DMC/bbs/bbsView.do?menuId=008042&cid=14082&pageIndex=1',
    text: `59세 남성이 역류성 식도염으로 P-CAB 계열 위산분비억제제인 테고프라잔을 처방받아 복용하였다. 복용 시작 28일째 외래 추적관찰에서 온몸 가려움과 얼굴 두드러기를 호소하였다. 의료진은 테고프라잔을 중단하고 항히스타민제(클로르페니라민) 주사를 투여하였으며, 위산분비억제제는 에소메프라졸로 변경하였다. 이후 증상 재발 여부를 관찰 중이다. 병원 약물안전센터는 테고프라잔과 이상반응 사이의 인과관계를 인정하였고, 벤즈이미다졸 계열 약물과의 교차 과민반응 가능성을 함께 검토하였다.`,
  },
  {
    id: 'mirtazapine', label: '미르타자핀 · 야간 요실금 (약사 보고, 자유 서술)', form: 'narrative',
    labelEn: 'Mirtazapine · nocturnal enuresis (pharmacist report, free narrative)',
    source: '약사공론 지역의약품안전센터 사례 기사 요약', sourceEn: 'Summary of a regional pharmacovigilance center case article (Korean pharmacists\' newspaper)',
    textEn: `A 56-year-old woman with diabetes and diabetic neuropathy started mirtazapine 7.5 mg at bedtime for insomnia and told the pharmacy she had nighttime urinary incontinence two nights in a row. Concomitant drugs: metformin/sitagliptin combination, eszopiclone, escitalopram. Symptoms stopped when mirtazapine was discontinued. The pharmacist reported it to the Korean Pharmaceutical Association regional drug safety center. No hospitalization.`,
    sourceUrl: 'https://www.kpanews.co.kr/news/articleView.html?idxno=542594',
    text: `56세 여성 환자로 당뇨병과 당뇨병성 신경병증 병력이 있다. 불면증으로 미르타자핀 7.5mg을 처방받아 취침 전 복용을 시작하였고, 복용 후 이틀 연속 자는 도중 소변을 지리는 야간 요실금이 발생하였다고 약국에 알렸다. 병용약물은 메트포르민·시타글립틴 복합제, 에스조피클론, 에스시탈로프람이다. 미르타자핀 복용을 중단하자 증상이 사라졌다. 약사가 대한약사회 지역의약품안전센터에 보고하였다. 입원은 없었다.`,
  },
  {
    id: 'consumer', label: '아목시실린 · 발진 (일반인 보고, 가상)', form: 'consumer',
    labelEn: 'Amoxicillin · rash (consumer report, fictional)',
    source: '흐름 설명용 가상 사례 (실제 보고 아님)', sourceEn: 'Fictional case to explain the workflow (not a real report)',
    textEn: `Reporter: the patient (consumer)
Age/sex: 34-year-old woman
Drugs: amoxicillin 500 mg prescribed by a dentist, three times a day, on day 3. Also took ibuprofen
Symptoms: red rash and itching on arms and trunk from the evening of day 3. No difficulty breathing
Action: stopped the drug, saw a doctor the next day and got an antihistamine. Rash mostly resolved two days later
History: was told she had hives from a penicillin-class antibiotic as a child
Hospitalization: none`,
    text: `보고자: 환자 본인 (일반인)
나이/성별: 34세 여성
복용한 약: 치과에서 처방받은 아목시실린 500mg, 하루 3번, 3일째 복용 중이었음. 같이 먹은 약: 이부프로펜
증상: 3일째 저녁부터 팔과 몸통에 붉은 발진과 가려움. 숨쉬기 불편하지는 않았음
조치: 약을 끊고 다음 날 병원에 가서 항히스타민제를 처방받음. 이틀 뒤 발진이 대부분 가라앉음
예전 경험: 어릴 때 페니실린 계열 항생제로 두드러기가 난 적이 있다고 들었음
입원 여부: 입원하지 않음`,
  },
]
