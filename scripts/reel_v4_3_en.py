"""쇼릴 v4.3.0 영어판(build_reel_v4_3_final.py --en)에 쓰는 영어 문구와 변환 함수입니다.

한국어판과 같은 템플릿 · 같은 장면 시간표를 쓰고, 화면 글자와 자막만 영어로 바꿉니다.
  - VO_EN      : 내레이션 박자마다 영어 자막 문장. (장면 id, 박자 번호) → (한국어 원문, 영어)
                 한국어 원문이 빌더의 narration() 결과와 다르면(데이터가 바뀌어 숫자가 달라지면) 빌드를 멈춥니다.
  - LABEL_EN   : 장면 이름(HUD · 챕터 · 대본). 한국어 원문이 다르면 멈춥니다.
  - GLOSS_EN   : 장면별 용어 풀이(빌더 GLOSS 와 같은 키여야 합니다).
  - DATA_EN · DATA_RX : 빌더 데이터(부분 함수가 만든 한국어 문자열)를 영어로 바꾸는 표. 표에 없는 한국어가 남으면 멈춥니다.
영어 자막은 박자마다 하나, 최대 두 줄 · 줄당 SUB_LINE_EN 자 이하이고, 띄우는 때(앞당김 · 남김)는 한국어판과 같습니다.
"""
import re

HANGUL = re.compile("[가-힣]")
SUB_LINE_EN = 42

TITLE_EN = "FlyGate Showreel v4.3 (English)"
DESCRIPTION_EN = ("Project-FlyGate motion showreel v4.3: STEP 1 FlyDiscovery (pre-market candidates) through STEP 2 FlyVigilance "
                  "(approved, marketed drugs), NVIDIA Agent Skills, the NemoClaw · OpenShell agent, and the FlyGate Agent CLI in real terminal captures")

# 마무리 구호(v4.2 SLOGAN_PARTS 와 같은 색 조각 구조)
SLOGAN_PARTS_EN = [["From molecule to patient,", "white"], ["\n", None], ["evidence ", "accent"], ["before inference. ", "muted"], ["FlyGate.", "brand"]]

# (장면 id, 박자 번호) → (한국어 원문, 영어 자막)
VO_EN = {
    ("intro", 0): ("프로젝트 플라이게이트입니다.", "This is Project-FlyGate."),
    ("intro", 1): ("NVIDIA 스킬로 구성한 약물 안전성 에이전트 워크플로입니다.", "An agentic drug-safety workflow built on NVIDIA Skills."),
    ("problem", 0): ("도킹 점수도 보고 통계도 모두 실측입니다.", "Docking scores and report stats are all measured."),
    ("problem", 1): ("그런데 결론이 근거를 넘으면 반려해야 합니다.", "But conclusions beyond the evidence get rejected."),
    ("problem", 2): ("한 분기에만 42만 건이 넘습니다.", "Over 420,000 reports arrive in a single quarter."),
    ("disc", 0): ("STEP 1 플라이디스커버리. MSA-Search가 PARP1 상동 서열 101개를 모읍니다.", "STEP 1, FlyDiscovery. MSA-Search gathers 101 PARP1 homologous sequences."),
    ("disc", 1): ("OpenFold3 복합체 예측은 결정 구조와 1.0 옹스트롬 차이입니다.", "OpenFold3's complex prediction is 1.0 Å from the crystal structure."),
    ("disc", 2): ("DiffDock은 결합 자리를 0.71 옹스트롬 안으로 재현했습니다.", "DiffDock reproduced the binding site within 0.71 Å."),
    ("disc", 3): ("Boltz-2 친화도 예측은 ChEMBL 실측과 순위 상관 0.767입니다.", "Boltz-2 affinity predictions rank-correlate 0.767 with ChEMBL data."),
    ("disc", 4): ("결론이 근거를 넘으면 Nemotron 크리틱이 반려합니다.", "Conclusions beyond the evidence: the Nemotron critic rejects them."),
    ("panel", 0): ("실제 사례의 의심약물 29종으로 패널을 넓힙니다.", "We widen the panel to 29 suspect drugs from real cases."),
    ("panel", 1): ("소분자는 DiffDock 재도킹으로 16개 중 10개가 2옹스트롬 기준을 통과했습니다.", "In DiffDock redocking, 10 of 16 small molecules passed the 2 Å bar."),
    ("bridge", 0): ("데모는 같은 약으로 시판 후를 잇습니다.", "The demo follows the same drug to market."),
    ("bridge", 1): ("이제 질문은, 누가 얼마나 빨리 봐야 하는가입니다.", "Now the question is: who needs to see it, and how fast?"),
    ("warehouse", 0): ("STEP 2, 플라이비질런스입니다.", "STEP 2, FlyVigilance."),
    ("warehouse", 1): ("미국 FDA 이상사례 보고, 즉 FAERS 55개 분기 1,759만 건을 집계합니다.", "We aggregate 17.59 million FDA adverse event reports (FAERS) from 55 quarters."),
    ("flow", 0): ("규칙으로 되는 일은 규칙으로, 판단은 모델로 나눕니다.", "Rules handle what rules can; judgment goes to models."),
    ("flow", 1): ("라벨 원문, 보고 통계, 문헌을 모아 약물감시, 즉 PV 분류를 매깁니다.", "Label text, report stats and literature set the pharmacovigilance (PV) class."),
    ("flow", 2): ("글은 Nemotron이, 확률은 비자기회귀 모델이 맡아 7문항을 0.3초에 답합니다.", "Nemotron writes; a non-autoregressive model answers 7 questions in 0.3 s."),
    ("triage", 0): ("실제 사례 한 건, 7문항 판단이 0.4초에 끝납니다.", "One real case: 7 judgments done in 0.4 seconds."),
    ("triage", 1): ("중대하고 예상하지 못해 15일 신속보고 후보입니다.", "Serious and unexpected: a 15-day expedited report candidate."),
    ("triage", 2): ("Nemotron 메모는 크리틱이 한 번 되돌렸고, 고친 뒤 통과했습니다.", "The critic sent Nemotron's memo back once; the revision passed."),
    ("korean", 0): ("국내 보고는 Nemotron이 식약처 서식 여섯 절로 구조화합니다.", "Nemotron structures Korean reports into the six sections of the MFDS form."),
    ("korean", 1): ("한국형 인과성 평가 8개 항목을 채점해 11점, 가능성 높음입니다.", "Korea's 8-item causality algorithm scores it 11 points: probable."),
    ("korean", 2): ("국내 규정은 예상 여부와 무관하게 중대하면 15일 보고입니다.", "In Korea, serious reactions must be reported in 15 days, expected or not."),
    ("signals", 0): ("불균형 보고 신호, 즉 SDR은 인과가 아니라 검토의 출발점입니다.", "An SDR (disproportionate reporting signal) starts a review, not a causal claim."),
    ("signals", 1): ("특별 주의 이상사례 62개는 점수와 관계없이 사람이 봅니다.", "62 designated medical events always go to a human, whatever the score."),
    ("signals", 2): ("변호사 보고가 몰린 쌍에는 편향 표시를 붙입니다.", "Pairs dominated by lawyer reports get a bias flag."),
    ("timemachine", 0): ("타임머신은 분기마다 그 시점 데이터로 신호를 다시 계산합니다.", "The time machine recomputes signals each quarter from data of that time."),
    ("timemachine", 1): ("카나글리플로진 케톤산증은 FDA 조치보다 592일 먼저 신호가 섰습니다.", "The canagliflozin–ketoacidosis signal came 592 days before FDA action."),
    ("measure", 0): ("결과 코드를 가린 440건에서 모델 단독 질문 하나와 비교했습니다.", "On 440 outcome-blinded cases, we compared with one question to the model alone."),
    ("measure", 1): ("중대 사례 247건이 검토에 닿았고, 사람이 먼저 볼 양은 302건에서 138건으로 줄었습니다.", "247 serious cases reached review; human-first workload fell from 302 to 138."),
    ("measure", 2): ("모두 유의한 차이입니다.", "All differences are significant."),
    ("validated", 0): ("지식 기반 방식은 판별 정확도, 즉 AUC 0.96, 0.98로 통계 지표를 앞섰습니다.", "Knowledge-based scoring beat the statistics, with AUCs of 0.96 and 0.98."),
    ("validated", 1): ("2013년 이전 보고만으로 라벨 변경 21건을 미리 잡았고, 오경보는 1건입니다.", "Pre-2013 reports alone caught 21 label changes early, with 1 false alarm."),
    ("nvskills", 0): ("NVIDIA 공식 Agent Skills 네 개를 적용했습니다.", "We applied four official NVIDIA Agent Skills."),
    ("nvskills", 1): ("정책 생성 스킬로 만든 약물감시 가드는 인과 단정과 없는 발생률을 잡습니다.", "Our policy-generator PV guard catches causal claims and made-up incidence rates."),
    ("nvskills", 2): ("Nemotron 리랭커는 관련 문헌 비율을 0.65에서 0.85로 올렸습니다.", "The Nemotron reranker raised the relevant-paper rate from 0.65 to 0.85."),
    ("reviewed", 0): ("현업 약사 검토 의견 15개를 코드와 데이터에 반영했습니다.", "15 comments from a practicing pharmacist went into our code and data."),
    ("reviewed", 1): ("신호 용어, 약물감시 분류, 결과 코드를 가린 평가가 그 결과입니다.", "Signal terms, PV classes and outcome-blinded evaluation came out of it."),
    ("arch", 0): ("에이전트 경로는 초파리 커넥톰의 아홉 기능 층에 대응시켰습니다.", "Agent routes map onto nine functional layers of the fruit-fly connectome."),
    ("arch", 1): ("반사는 싸게, 숙고는 드물게, 억제는 늘 켜 둡니다.", "Reflexes stay cheap, deliberation rare, inhibition always on."),
    ("agent", 0): ("에이전트는 NemoClaw로 OpenShell 샌드박스 안에서 늘 켜져 있습니다.", "With NemoClaw, the agent stays on inside an OpenShell sandbox."),
    ("agent", 1): ("허용한 호스트만 나가고, 샌드박스 점검 20개를 모두 통과했습니다.", "Only allowed hosts get out, and all 20 sandbox checks passed."),
    ("cli_open", 0): ("플라이게이트 에이전트 CLI, 명령줄 도구입니다.", "The FlyGate Agent CLI, a command-line tool."),
    ("cli_install", 0): ("설치는 한 줄이면 되고, 명령 9개가 바로 생깁니다.", "One line installs it, and 9 commands are ready."),
    ("cli_triage", 0): ("triage는 실제 사례 한 건을 0.6초 만에 분류합니다.", "triage classifies one real case in 0.6 seconds."),
    ("cli_grade", 0): ("grade는 라벨, 신호, 문헌을 함께 읽고 등급을 매깁니다.", "grade reads label, signal and literature, then grades."),
    ("cli_critic", 0): ("critic은 근거를 넘는 주장 3개를 반려합니다.", "critic rejects 3 claims that outrun the evidence."),
    ("cli_dock", 0): ("discover는 DiffDock NIM에 실시간으로 도킹을 맡깁니다.", "discover hands docking to the DiffDock NIM, live."),
    ("cli_kr", 0): ("kr-causality는 국내 보고를 15일 보고 후보로 보냅니다.", "kr-causality routes Korean reports as 15-day candidates."),
    ("cli_watch", 0): ("watch는 매일 아침 검토 대기열을 만들고, 아무것도 제출하지 않습니다.", "watch builds a review queue every morning and submits nothing."),
    ("cli_same", 0): ("사람도 에이전트도 같은 명령을 씁니다.", "Humans and agents use the same commands."),
    ("cli_same", 1): ("OpenClaw도 샌드박스 안에서 같은 CLI를 부릅니다.", "OpenClaw calls the same CLI inside the sandbox, too."),
    ("cli_line", 0): ("저장소에서 한 줄로 설치해 바로 쓰실 수 있습니다.", "Install from the repository in one line and start right away."),
    ("close", 0): ("분자에서 환자까지, 추론보다 근거가 먼저.", "From molecule to patient, evidence before inference."),
    ("close", 1): ("플라이게이트였습니다. 감사합니다.", "This was FlyGate. Thank you."),
}

# 장면 id → (한국어 원문 label, 영어 label). 한국어 원문이 영문이면 그대로 둡니다
LABEL_EN = {
    "problem": ("문제 · 근거를 넘는 결론", "Problem · conclusions beyond evidence"),
    "disc": ("STEP 1 · FlyDiscovery · 시판 전 후보", "STEP 1 · FlyDiscovery · pre-market candidates"),
    "panel": ("STEP 1 · 약물 패널 · 재도킹", "STEP 1 · Drug panel · redocking"),
    "bridge": ("데모 · 같은 약물을 시판 후로", "Demo · the same drug, post-market"),
    "warehouse": ("STEP 2 · FAERS 웨어하우스", "STEP 2 · FAERS warehouse"),
    "flow": ("STEP 2 · FlyVigilance 워크플로", "STEP 2 · FlyVigilance workflow"),
    "triage": ("STEP 2 · 실제 사례 한 건", "STEP 2 · One real case"),
    "korean": ("국내 규정 모드 · 한국형 인과성", "Korean PV mode · Korean causality"),
    "signals": ("SDR · PV 분류 · 안전망", "SDR · PV classes · safety net"),
    "timemachine": ("신호 타임머신 · 분기별 재계산", "Signal time machine · quarterly recompute"),
    "measure": ("결과 코드를 가린 실측", "Outcome-blinded measurement"),
    "validated": ("공개 참조 세트 검증", "Public reference-set validation"),
    "nvskills": ("NVIDIA 공식 Agent Skills 적용", "Official NVIDIA Agent Skills, applied"),
    "reviewed": ("면허 약사 검토 반영", "Licensed pharmacist review, applied"),
    "arch": ("커넥톰 라우팅 구조", "Connectome-routed architecture"),
    "cli_install": ("CLI · INSTALL · 한 줄 설치", "CLI · INSTALL · one-line install"),
    "cli_triage": ("CLI · TRIAGE · 사례 분류", "CLI · TRIAGE · case triage"),
    "cli_grade": ("CLI · GRADE · 라벨 · 신호 · 문헌", "CLI · GRADE · label · signal · literature"),
    "cli_critic": ("CLI · CRITIC · 근거를 넘으면 반려", "CLI · CRITIC · beyond evidence, rejected"),
    "cli_dock": ("CLI · DOCK · DiffDock NIM 실시간", "CLI · DOCK · DiffDock NIM, live"),
    "cli_kr": ("CLI · KR · 국내 15일 규칙", "CLI · KR · Korea's 15-day rule"),
    "cli_watch": ("CLI · WATCH · 상시 실행 · 제출 0건", "CLI · WATCH · always on · 0 submitted"),
    "cli_same": ("CLI · 사람도 에이전트도 같은 명령", "CLI · same commands for humans and agents"),
    "cli_line": ("CLI · 설치 한 줄", "CLI · one install line"),
    "close": ("분자에서 환자까지 · 근거가 먼저", "From molecule to patient · evidence first"),
}
NAME_EN = {"같은 명령": "Same command", "한 줄": "One line"}

GLOSS_EN = {
    "problem": "Pharmacovigilance (PV) = collecting side-effect reports on marketed drugs to find new risk signals",
    "disc": "NIM = NVIDIA AI models served by API · RMSD = distance between predicted and real binding pose (≤ 2 Å = reproduced)",
    "panel": "Redocking = checking that a model re-finds a known binding site · Å (ångström) = one ten-billionth of a meter",
    "bridge": "Pre-market = candidates before approval · post-market = drugs patients actually take",
    "warehouse": "FAERS = FDA Adverse Event Reporting System · SDR = drug–event pair reported unusually often vs other drugs",
    "flow": "System-1 = fast rules + judgment model · System-2 = Nemotron deliberation · critic = sends back claims beyond the evidence",
    "triage": "Triage = sorting cases by urgency · expedited report = serious, unexpected case reported to regulators within 15 days",
    "korean": "MFDS = Korea's Ministry of Food and Drug Safety · WHO-UMC = WHO causality criteria · 15-day rule = serious-case deadline",
    "signals": "SDR = statistically unusual drug–event pair · PRR = proportional reporting ratio · DME = designated medical event (EMA)",
    "timemachine": "IC = information component: how much more than expected · FDA action = when the label added the reaction",
    "measure": "McNemar test = compares two methods on the same cases · the smaller the p value, the less likely it is chance",
    "validated": "AUC = how well real signals are told from fakes (0.5 random · 1 perfect) · OMOP · EU-ADR · Harpaz = public answer sets",
    "nvskills": "Agent Skills = task playbooks NVIDIA publishes for agents · reranker = re-sorts search results by relevance",
    "reviewed": "Licensed pharmacist review = a practicing pharmacist checked agent output, and the fixes became rules",
    "arch": "Connectome = wiring map of the fruit-fly brain · routing = choosing which judgment path each case takes",
    "agent": "NemoClaw · OpenShell = NVIDIA sandboxed runtime · OpenClaw = the agent that runs commands inside it",
    "cli_open": "CLI = a tool you use by typing commands in a terminal · every output is JSON with evidence IDs",
    "cli_install": "Install script = creates a virtual environment and puts the flygate command on PATH",
    "cli_triage": "triage = case classification · evidence_ids = IDs of the source records behind a conclusion",
    "cli_grade": "grade = one grade from label, signal and literature · PRR = proportional reporting ratio",
    "cli_critic": "safe / flagged = claims Nemotron Safety Guard passed / sent back",
    "cli_dock": "DiffDock = NVIDIA NIM model that predicts how a drug sits on a protein",
    "cli_kr": "WHO-UMC = WHO causality criteria · 15-day rule = reporting deadline for serious, unexpected events",
    "cli_watch": "watch = recomputes signals each quarter and queues them for review · people submit to regulators",
    "cli_same": "OpenShell sandbox = isolated environment where the agent runs the same commands",
}

EMPHASIS_EN = {
    "재도킹 3/3 기준 통과(RMSD 2 Å 이하)": "Redocking 3/3 pass (RMSD ≤ 2 Å)",
    "크리틱이 근거를 넘는 주장을 되돌림": "Critic sends back claims beyond the evidence",
    "결정 · 사람 우선 신속보고 후보": "Decision · human-first expedited candidate",
    "크리틱 1단이 주장 하나를 되돌림": "Critic tier 1 sends one claim back",
    "국내 식약처 15일 보고 규칙": "Korea MFDS 15-day reporting rule",
    "FDA 조치보다 SDR이 먼저 선 기간(+592일)": "SDR lead over FDA action (+592 days)",
    "검토에 닿은 중대 사례 247/250": "Serious cases reaching review 247/250",
    "사람 우선 검토 업무량 302 → 138": "Human-first workload 302 → 138",
    "공개 참조 세트 AUC": "Public reference-set AUC",
    "2013년 라벨 변경 21/57을 미리 포착": "2013 label changes caught early, 21/57",
    "평가 문장 정확도 향상(Nemotron Content Safety custom_policy)": "Eval-sentence accuracy gain (Nemotron Content Safety custom_policy)",
    "grade 출력 확대 줄": "Zoomed grade output lines",
    "critic 의 safe / flagged 줄": "critic safe / flagged lines",
    "DiffDock status · run 줄": "DiffDock status · run lines",
}

# 빌더 데이터의 한국어 문자열 → 영어(정확히 같은 문자열만 바꿉니다)
DATA_EN = {
    # 약물 이름(재도킹 · Vina 순위)
    "니라파립 @ PARP1": "Niraparib @ PARP1", "아픽사반 @ Factor Xa": "Apixaban @ Factor Xa", "셀레콕시브 @ COX-2": "Celecoxib @ COX-2",
    "니라파립": "Niraparib", "파미파립": "Pamiparib", "루카파립": "Rucaparib", "아픽사반": "Apixaban", "셀레콕시브": "Celecoxib",
    "레날리도마이드": "Lenalidomide", "룩솔리티닙": "Ruxolitinib", "니르마트렐비르": "Nirmatrelvir", "덱사메타손": "Dexamethasone", "리스페리돈": "Risperidone",
    # FlyDiscovery 크리틱 평가 문항(화면에는 판정만 씁니다)
    "PARP1 Vina 순위는 15R > pamiparib > niraparib > rucaparib이다.": "The PARP1 Vina ranking is 15R > pamiparib > niraparib > rucaparib.",
    "DiffDock이 니라파립을 4R6E 공결정 위치에 RMSD 0.71A로 재현했다.": "DiffDock reproduced niraparib at the 4R6E co-crystal position with RMSD 0.71 Å.",
    "ChEMBL 실측 중앙값은 pamiparib 8.89 > rucaparib 8.70 > niraparib 7.79이다.": "ChEMBL measured medians are pamiparib 8.89 > rucaparib 8.70 > niraparib 7.79.",
    "Boltz-2는 니라파립@PARP1 pIC50 8.909를 예측했고 ChEMBL 실측 중앙값은 7.79이다.": "Boltz-2 predicted niraparib@PARP1 pIC50 8.909; the ChEMBL measured median is 7.79.",
    "니라파립은 PARP1 -10.178, Xa -7.967이므로 PARP1에 선택적이다.": "Niraparib scores PARP1 -10.178 and Xa -7.967, so it is PARP1-selective.",
    "DiffDock 신뢰도 1.10인 pamiparib이 rucaparib보다 친화도가 높다.": "Pamiparib, at DiffDock confidence 1.10, has higher affinity than rucaparib.",
    "Boltz-2 예측 pIC50 8.909는 니라파립의 측정된 PARP1 친화도이다.": "Boltz-2's predicted pIC50 8.909 is niraparib's measured PARP1 affinity.",
    "PARP1 3종의 Boltz-2와 실측 Spearman이 -1.0이므로 Boltz-2는 실측과 역상관한다.": "With Spearman -1.0 across 3 PARP1 compounds, Boltz-2 is anti-correlated with measurement.",
    # 근거 등급 · PV 분류
    "규명된 위해성 후보": "Identified risk candidate",
    "라벨에 있고 SDR 도 섰습니다. 알려진 위험이 보고와 일치합니다": "On the label, and an SDR too. The known risk matches the reports",
    "경고·주의사항": "Warnings and Precautions", "3중 기준 SDR": "Triple-criteria SDR",
    "검토가 필요한 SDR (새 신호 후보)": "SDR needing review (new signal candidate)",
    "라벨 미기재(또는 라벨 확인 불가) + SDR": "Not on label (or label unavailable) + SDR",
    "잠재적 위해성 후보": "Potential risk candidate", "라벨 기재 + 그 반응에 인과 미확립 단서": "On label + ‘causality not established’ note",
    "판정 불가": "Indeterminate", "라벨이나 FAERS 통계를 확인하지 못함": "Label or FAERS statistics unavailable",
    "라벨 기재 + SDR": "On label + SDR", "알려진 위험 · SDR 없음": "Known risk · no SDR", "라벨 기재 + SDR 없음": "On label + no SDR",
    "해당 없음": "Not applicable", "라벨 미기재 + SDR 없음": "Not on label + no SDR",
    # 에이전트
    "역할 · 경계 · 어조": "role · limits · tone", "작업 규칙 · 근거 ID 인용": "work rules · cite evidence IDs", "이름 · 성격": "name · persona",
    "주 사용자 · PV 평가자": "main user · PV assessor", "flygate CLI 사용법": "flygate CLI usage", "주기 점검 목록": "periodic checklist",
    "오래 남길 기억": "long-term memory", "seccomp 필터 · no_new_privs · capability 0": "seccomp filter · no_new_privs · capability 0",
    "하트비트": "heartbeat", "메인 세션 · 게이트웨이 타이머(기본 약 30분)": "main session · gateway timer (~30 min)",
    "허용 호스트 연결": "Allowed hosts reachable", "목록 밖 호스트 차단": "Unlisted hosts blocked",
    "묶이지 않은 실행 파일 · 경로 · 메서드 차단": "Unbound binaries · paths · methods blocked",
    "파일 쓰기 경계 (Landlock)": "File-write boundary (Landlock)", "비루트 · seccomp · 권한 상승 차단": "Non-root · seccomp · no privilege escalation",
    "OpenClaw 워크스페이스 · 스킬 배치": "OpenClaw workspace · skills in place", "샌드박스 안에서 flygate 실행": "flygate runs inside the sandbox",
    # 실제 사례 트리아지 확률
    "중대성": "Seriousness", "예측성 (라벨 기재)": "Expectedness (on label)", "인과성 · WHO-UMC(세계보건기구 기준)": "Causality · WHO-UMC (WHO criteria)",
    "특수 상황": "Special situation", "우선순위": "Priority", "다음 경로": "Next route", "숙고 필요": "Needs deliberation",
    # 국내 보고 서술(시연용 가상 사례, 영어판은 번역해 보여 줍니다)
    "보고자: 병원 약사(서울 소재 상급종합병원 약제부)": "Reporter: hospital pharmacist (pharmacy department, tertiary hospital in Seoul)",
    "환자: 62세 여성, 체중 52 kg, 난소암(BRCA 변이 없음) 1차 백금 기반 항암 후 유지요법 중입니다. 약물 알레르기 과거력은 없습니다.":
        "Patient: 62-year-old woman, 52 kg, ovarian cancer (no BRCA mutation), on maintenance after first-line platinum chemotherapy. No drug allergy history.",
    "의심약물: 니라파립(제줄라캡슐) 200 mg 1일 1회 경구, 2026년 8월 3일 투여 시작, 투여 목적은 난소암 유지요법입니다.":
        "Suspect drug: niraparib (Zejula capsules) 200 mg orally once daily from August 3, 2026, as ovarian cancer maintenance.",
    "병용약물: 온단세트론 8 mg 필요 시 경구(구역), 판토프라졸 40 mg 1일 1회 경구.":
        "Concomitant drugs: ondansetron 8 mg orally as needed (nausea), pantoprazole 40 mg orally once daily.",
    "경과: 투여 23일째 정기 혈액검사에서 혈소판 수치가 21,000/μL(기저치 210,000/μL)로 떨어졌고 잇몸 출혈이 있어 입원했습니다.":
        "Course: on day 23 a routine blood test showed platelets at 21,000/μL (baseline 210,000/μL); she was admitted with gum bleeding.",
    "니라파립을 중단하고 혈소판 1단위를 수혈했습니다. 중단 12일 뒤 혈소판이 148,000/μL로 회복되어 퇴원했습니다.":
        "Niraparib was stopped and 1 unit of platelets transfused. 12 days later platelets recovered to 148,000/μL and she was discharged.",
    "재투여는 아직 하지 않았습니다. 같은 계열 약 복용 경험은 없습니다. 골수 억제를 설명할 다른 약물이나 질환(감염, 출혈성 질환)은 확인되지 않았습니다.":
        "No rechallenge yet. No prior use of the same drug class. No other drug or condition (infection, bleeding disorder) explains the marrow suppression.",
    # 식약처 서식 가~바 → A–F
    "가": "A", "나": "B", "다": "C", "라": "D", "마": "E", "바": "F",
    "환자": "Patient", "이상사례": "Event", "의약품": "Drug", "보고자": "Reporter", "보고서": "Report", "종합의견": "Summary",
    "62세 · 여 · 52 kg": "62 y · F · 52 kg", "혈소판감소증 · 잇몸 출혈 · 입원 연장": "Thrombocytopenia · gum bleeding · longer stay",
    "니라파립 200 mg 1일 1회 경구 · 중단": "Niraparib 200 mg PO daily · stopped", "약사": "Pharmacist", "자발보고 · 최초": "Spontaneous · initial",
    "원문 요지 보존": "Original gist kept",
    # 한국형 인과성 평가 알고리즘 항목
    "시간적 선후관계": "Temporal sequence", "선후관계 합당": "Plausible sequence",
    "감량 또는 중단": "Dechallenge", "감량 또는 중단 후 임상적 호전이 관찰됨": "Improved after dose reduction or withdrawal",
    "이상사례의 과거력": "Prior history", "아니오": "No",
    "병용약물": "Concomitant drugs", "병용약물 단독으로 유해사례를 설명할 수 없는 경우": "Concomitant drugs alone cannot explain it",
    "비약물요인": "Non-drug factors", "비약물요인으로 유해사례가 설명되지 않음": "Not explained by non-drug factors",
    "약물에 대해 알려진 정보": "Known drug info", "허가사항(label, insert 등)에 반영되어 있음": "In the approved label (label, insert, etc.)",
    "재투약": "Rechallenge", "재투약하지 않음": "Not rechallenged", "특이적인 검사": "Specific tests", "정보없음": "No information",
    "가능성 높음": "Probable",
    # NVIDIA 스킬 · 정책 가드 평가 행
    "PRR 인과 단정": "PRR as causation", "없는 발생률": "Invented incidence",
}
# 숫자 · 시각이 들어 있는 문자열(정규식 → 바꿀 문자열)
DATA_RX = [
    (r"^격리 세션 · (.+)$", r"isolated session · \1"),
    (r"^평가 불가 (\S+)$", r"Unassessable \1"),
    (r"^소아 (\S+)$", r"Pediatric \1"),
    (r"^사람 우선 (\S+)$", r"Human first \1"),
    (r"^(-?\d+)~(-?\d+)점$", r"\1–\2 pts"),
    (r"^15일 이내 \(의약품 등의 안전에 관한 규칙 별표 4의3 제7호 나목: 중대한 약물이상반응, '예상하지 못한' 요건 없음\)$",
     "Within 15 days (Rules on the Safety of Medicinal Products, Annex 4-3, item 7(b): serious adverse drug reaction; no ‘unexpected’ requirement)"),
]
# 화면에 그리지 않거나(캡처 자리 정보) 캡처가 없을 때만 쓰는 터미널 출력 원문(cli2)은 바꾸지 않습니다. 영어판은 캡처 줄 원문을 뺍니다
SKIP_KEYS = {"cli2", "caps", "subs", "gloss", "slogan", "tl", "mainui"}


def en_str(s: str, path: str, missing: list) -> str:
    if not HANGUL.search(s):
        return s
    if s in DATA_EN:
        return DATA_EN[s]
    for rx, rep in DATA_RX:
        if re.match(rx, s):
            return re.sub(rx, rep, s)
    missing.append(f"{path} = {s!r}")
    return s


def en_data(o, path: str = "", missing: list | None = None):
    """빌더 데이터의 한국어 문자열을 영어로 바꿉니다. 표에 없는 한국어가 있으면 missing 에 모읍니다."""
    if isinstance(o, dict):
        return {k: (v if (not path and k in SKIP_KEYS) else en_data(v, f"{path}.{k}", missing)) for k, v in o.items()}
    if isinstance(o, list):
        return [en_data(v, f"{path}[{i}]", missing) for i, v in enumerate(o)]
    if isinstance(o, str):
        return en_str(o, path, missing)
    return o


def check_vo(tl: list[dict]):
    """모든 박자에 영어 문장이 있고, 한국어 원문이 표와 같은지 확인합니다. 다르면 빌드를 멈춥니다."""
    errs = []
    seen = set()
    for s in tl:
        for i, bt in enumerate(s["beats"]):
            key = (s["id"], i)
            seen.add(key)
            if key not in VO_EN:
                errs.append(f"{key}: 영어 문장이 없습니다 · 한국어 {bt['vo']!r}")
            elif VO_EN[key][0] != bt["vo"]:
                errs.append(f"{key}: 한국어 원문이 바뀌었습니다 · 표 {VO_EN[key][0]!r} · 지금 {bt['vo']!r}")
    errs += [f"{k}: 표에만 있는 박자" for k in VO_EN if k not in seen]
    for s in tl:
        if s["id"] in LABEL_EN and LABEL_EN[s["id"]][0] != s["label"]:
            errs.append(f"label {s['id']}: 한국어 원문이 바뀌었습니다 · 표 {LABEL_EN[s['id']][0]!r} · 지금 {s['label']!r}")
        elif s["id"] not in LABEL_EN and HANGUL.search(s["label"]):
            errs.append(f"label {s['id']}: 영어 label 이 없습니다 · {s['label']!r}")
        if HANGUL.search(s["name"]) and s["name"] not in NAME_EN:
            errs.append(f"name {s['id']}: 영어 이름이 없습니다 · {s['name']!r}")
    if errs:
        raise SystemExit("영어판 문구 확인 실패:\n  " + "\n  ".join(errs))


def label_en(s: dict) -> str:
    return LABEL_EN[s["id"]][1] if s["id"] in LABEL_EN else s["label"]


def sub_lines_en(s: str) -> list[str]:
    """SUB_LINE_EN 자를 넘으면 두 줄로 나눕니다. 두 줄 모두 한도 안이어야 하고, 문장 부호 뒤를 먼저, 없으면 가운데에 가까운 띄어쓰기에서 자릅니다"""
    s = s.strip()
    if len(s) <= SUB_LINE_EN:
        return [s]
    cuts = [m.start() for m in re.finditer(r" ", s) if m.start() <= SUB_LINE_EN and len(s) - m.start() - 1 <= SUB_LINE_EN]
    if not cuts:
        raise SystemExit(f"영어 자막이 두 줄({SUB_LINE_EN}자 × 2)에 들어가지 않습니다: {s!r}")
    mid = len(s) / 2
    # 문장 부호 바로 뒤, 짧은 기능어 앞에서 자르는 것을 선호합니다(숫자와 단위는 한 줄에 둡니다)
    def cost(c):
        prev, nxt = s[:c].split()[-1], s[c + 1:].split()[0]
        pen = 0 if re.search(r"[,;:.]$", prev) else 8
        if re.fullmatch(r"[\d.,]+", prev) or nxt in ("Å", "s", "%"):
            pen += 20
        if prev.lower() in ("a", "an", "the", "of", "to", "in", "on", "and", "with", "from"):
            pen += 10
        return abs(c - mid) + pen
    best = min(cuts, key=cost)
    return [s[:best], s[best + 1:]]


def subtitles_en(tl: list[dict], lead: float, hold: float) -> list[list]:
    """한국어판 subtitles() 와 같은 규칙(앞당김 lead · 최대 남김 hold)으로 박자마다 영어 자막 하나를 만듭니다"""
    beats = [(sc["t0"] + bt["a"], sc["t0"] + bt["b"], VO_EN[(sc["id"], i)][1]) for sc in tl for i, bt in enumerate(sc["beats"])]
    dur = tl[-1]["t1"]
    out = []
    for i, (a, b, t) in enumerate(beats):
        nxt = beats[i + 1][0] - lead if i + 1 < len(beats) else dur
        start = max(a - lead, out[-1][1] if out else 0.0)
        end = max(b, min(nxt, b + hold))
        out.append([round(start, 2), round(end, 2), "\n".join(sub_lines_en(t))])
    return out


def sub_stats(subs: list[list]) -> dict:
    cps = [len(x[2].replace("\n", " ")) / (x[1] - x[0]) for x in subs]
    return {"n": len(subs), "min_dur": min(x[1] - x[0] for x in subs), "avg_cps": sum(cps) / len(cps), "max_cps": max(cps),
            "over17": sum(1 for c in cps if c > 17), "max_line": max(len(ln) for x in subs for ln in x[2].split("\n")),
            "two_line": sum(1 for x in subs if "\n" in x[2])}


def write_script_en(path, tl: list[dict], dur: float, built: str, subs: list[list], version: str, gloss: dict, emphasis: list, mmss):
    st = sub_stats(subs)
    cli = [s for s in tl if s["id"].startswith("cli_")]
    L = [f"# Project-FlyGate showreel v{version} — English narration script", "",
         f"- Video: `web/public/showreel/FlyGate_showreel_v{version}-en.html` (1920×1080, 30 fps; `?fmt=square` 1080×1080 and `?fmt=vertical` 1080×1920 also work)",
         f"- **Total {int(dur // 60)} min {dur % 60:.0f} s ({dur:.1f} s)** · {len(tl)} scenes · CLI section {len(cli)} scenes",
         "- Same template, scene timeline and numbers as the Korean final (`docs/SHOWREEL_SCRIPT_v4.3.0.md`); on-screen text and subtitles are English.",
         f"- Generated by `scripts/build_reel_v4_3_final.py --en` (English strings in `scripts/reel_v4_3_en.py`). Numbers are the repository JSON and measurement files at build time ({built}).",
         "- Scene timing follows the Korean narration (the audio track is the Korean one). Each English line is a faithful translation of its Korean beat with identical numbers; the builder stops if a Korean beat changes without its English line.",
         "- Terms: FAERS = FDA Adverse Event Reporting System · SDR = signal of disproportionate reporting · PRR = proportional reporting ratio · RMSD = root-mean-square deviation · pLDDT = per-residue confidence · NIM = NVIDIA inference microservice · WHO-UMC = WHO causality criteria · MFDS = Korea's Ministry of Food and Drug Safety.",
         "", "## Scenes at a glance", "", "| # | Scene | Start | End | Length |", "| --- | --- | --- | --- | --- |"]
    for i, s in enumerate(tl, 1):
        L.append(f"| {i:02d} | {label_en(s)} | {mmss(s['t0'])} | {mmss(s['t1'])} | {s['t1'] - s['t0']:.1f} s |")
    L.append(f"| | **Total** | 00:00.0 | {mmss(dur)} | **{dur:.1f} s** |")
    for i, s in enumerate(tl, 1):
        L += ["", f"## {i:02d} · {label_en(s)} ({mmss(s['t0'])}–{mmss(s['t1'])})", "", "| Time | Narration (English) | Words |", "| --- | --- | --- |"]
        for j, bt in enumerate(s["beats"]):
            en = VO_EN[(s["id"], j)][1]
            L.append(f"| {mmss(s['t0'] + bt['a'])}–{mmss(s['t0'] + bt['b'])} | {en} | {len(en.split())} |")
    L += ["", "## Per-scene glossary", "", "Shown in a fixed spot at the lower right (wide) or below the stage (square · vertical); it changes only with the scene.", "",
          "| Scene | Glossary |", "| --- | --- |"]
    for s in tl:
        if s["id"] in gloss:
            L.append(f"| {label_en(s)} | {gloss[s['id']]} |")
    lab = {s["id"]: label_en(s) for s in tl}
    L += ["", "## Where emphasis frames appear", "", "| Scene | What is emphasized |", "| --- | --- |"]
    L += [f"| {lab.get(sid, sid)} | {EMPHASIS_EN.get(what, what)} |" for sid, what in emphasis]
    L += ["", "## On-screen subtitles", "",
          f"One subtitle per narration beat, at most two lines of ≤ {SUB_LINE_EN} characters. Each appears 0.3 s before its beat and stays until the next one "
          f"(up to 1.6 s after the beat ends), the same rule as the Korean version.", "",
          f"- Subtitles: {st['n']} · two-line: {st['two_line']} · longest line {st['max_line']} characters · shortest on screen {st['min_dur']:.1f} s",
          f"- Reading speed (characters incl. spaces per second): mean {st['avg_cps']:.1f} cps, max {st['max_cps']:.1f} cps · above 17 cps: {st['over17']}", "",
          "| Time | Subtitle | cps |", "| --- | --- | --- |"]
    L += [f"| {mmss(x[0])}–{mmss(x[1])} | {x[2].replace(chr(10), ' / ')} | {len(x[2].replace(chr(10), ' ')) / (x[1] - x[0]):.1f} |" for x in subs]
    L += ["", "## Notes", "",
          "- The CLI section shows real terminal captures (bitmaps). The FlyGate CLI prints some Korean text (for example the Korean-regulation `kr-causality` output); those pixels are part of the capture and are not translated.",
          "- The Korean report narrative in the Korean PV mode scene is a fictional demo case; the English version shows it in translation.",
          "- Jev (TypeSafe AI) is named only in the tech-stack credits; elsewhere it is called the non-autoregressive judgment model. The comparison baseline is ‘model alone, one question’.", ""]
    path.write_text("\n".join(L))
    return st
