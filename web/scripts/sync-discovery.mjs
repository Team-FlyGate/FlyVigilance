// STEP 1 FlyDiscovery 화면(fly_discovery/web)과 측정 요약(fly_discovery/measurements)을 web/public/discovery/ 로 복사합니다.
// package.json 의 predev·prebuild 에서 자동으로 돌기 때문에 Vercel 빌드(npm run build)에서도 실행됩니다.
// 복사본은 생성물이라 저장소에 올리지 않습니다. 그래서 복사한 폴더 안에 모든 파일을 무시하는 .gitignore 를 함께 둡니다.
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const WEB = join(dirname(fileURLToPath(import.meta.url)), '..')
const SRC = join(WEB, '..', 'fly_discovery')
const OUT = join(WEB, 'public', 'discovery')

// 화면 파일은 그대로, 측정 요약은 /discovery/data/ 아래로 둡니다
const PAGE = ['index.html', 'dc-shim.js', 'fgscene.json']
const DATA = {
  'measurements.json': 'measurements/measurements.json',
  'critic_summary.json': 'measurements/nim/critic_summary.json',
  'dd_eval_all.json': 'measurements/nim/dd_eval_all.json',
  'boltz2_all.json': 'measurements/nim/boltz2_all.json',
  // 도킹 애니메이션 · 재도킹 스트림 · 약물 패널 · 크리틱 스트림 (Discovery.tsx)
  'redock_scenes.json': 'measurements/redock_scenes.json',
  'hero_scene.json': 'measurements/hero_scene.json',
  'dock_library.json': 'measurements/dock_library.json',
  'dock_matrix.json': 'measurements/dock_matrix.json',
  'redock.json': 'measurements/redock.json',
  'validation.json': 'measurements/validation.json',
  'selectivity_evidence.json': 'measurements/selectivity_evidence.json',
  'evidence_cards.json': 'measurements/evidence_cards.json',
  'drug_panel.json': 'measurements/drug_panel.json',
  'critic_v2.json': 'measurements/nim/critic_v2.json',
}

if (!existsSync(join(SRC, 'web', 'index.html'))) {
  // 원본이 없어도 대시보드 나머지는 빌드되어야 하므로 경고만 남깁니다. Discovery 화면이 빈 상태를 안내합니다.
  console.warn(`[sync-discovery] ${relative(WEB, SRC)}/web 이 없어 건너뜁니다`)
  process.exit(0)
}

rmSync(OUT, { recursive: true, force: true })
mkdirSync(join(OUT, 'data'), { recursive: true })

for (const f of PAGE) cpSync(join(SRC, 'web', f), join(OUT, f))
// iframe 안의 링크는 대시보드 창 전체를 이동시키고(_top), STEP 2 링크는 같은 배포의 라이브 트리아지로 보냅니다
const page = join(OUT, 'index.html')
writeFileSync(page, readFileSync(page, 'utf8')
  .replace('<head>', '<head>\n<base target="_top">')
  .replaceAll('https://flyvigilance.vercel.app/#/', '/#/'))

let copied = PAGE.length
for (const [to, from] of Object.entries(DATA)) {
  if (existsSync(join(SRC, from))) { cpSync(join(SRC, from), join(OUT, 'data', to)); copied++ }
  else console.warn(`[sync-discovery] ${from} 이 없어 건너뜁니다`)
}
writeFileSync(join(OUT, '.gitignore'), '# scripts/sync-discovery.mjs 가 만든 복사본입니다. 원본은 fly_discovery/ 에 있습니다\n*\n')
console.log(`[sync-discovery] ${copied}개 파일을 ${relative(WEB, OUT)}/ 에 복사했습니다`)
