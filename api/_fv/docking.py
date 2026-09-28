"""Fresh DiffDock NIM execution for the CLI, with persistent request provenance.

No automatic POST retries: a timeout may mean the provider already accepted work.
Only a known request ID can be resumed without creating another inference job.
"""
from __future__ import annotations
import hashlib
import json
import math
import pathlib
import re
import time
import uuid
from datetime import datetime, timezone

import httpx

try:  # api/_fv 패키지 안에서 불릴 때만 호출 기록기를 씁니다(단독 실행에서는 건너뜁니다)
    from . import calllog
except ImportError:  # pragma: no cover
    calllog = None

ENDPOINT = 'https://health.api.nvidia.com/v1/biology/mit/diffdock'
STATUS = 'https://health.api.nvidia.com/v1/status/'


def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temp.replace(path)


def request_id(value):
    if not value or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', value):
        raise ValueError('NIM 응답의 request ID가 없거나 올바르지 않습니다.')
    return value


def summarize(folder, manifest):
    return {'cmd': 'discover', 'mode': 'live', **manifest,
            'run_dir': str(folder),
            'note': 'DiffDock 포즈 신뢰도는 결합 친화도나 약효의 측정값이 아닙니다.'}


def build_body(protein, ligand, kind='txt', num_poses=5):
    """DiffDock NIM 요청 본문입니다. 수용체는 ATOM 줄만 남기고, SMILES 는 ligand_file_type='txt' 입니다
    (NVIDIA BioNeMo Agent Toolkit `diffdock-nim` 규격). 웹 경로(api/_fv/discovery.py)도 같은 본문을 씁니다."""
    protein = '\n'.join(x for x in protein.splitlines() if x.startswith(('ATOM  ', 'ATOM', 'TER', 'END'))) + '\n'
    return {'protein': protein, 'ligand': ligand.strip(), 'ligand_file_type': kind,
            'num_poses': num_poses, 'time_divisions': 20, 'steps': 18,
            'save_trajectory': False, 'is_staged': False}


def validate_result(data):
    """NIM 응답에서 포즈와 신뢰도를 꺼냅니다. 형태가 어긋나면 ValueError 를 냅니다(성공으로 치지 않습니다)."""
    if not isinstance(data, dict):
        raise ValueError('object expected')
    poses, confidence = data.get('ligand_positions'), data.get('position_confidence')
    if data.get('status') not in (None, 'success', 'completed'):
        raise ValueError('provider reported failure')
    if not isinstance(poses, list) or not poses or not isinstance(confidence, list) or len(poses) != len(confidence):
        raise ValueError('missing poses or scores')
    if any(not isinstance(p, str) or 'M  END' not in p for p in poses):
        raise ValueError('invalid SDF poses')
    if any(not isinstance(c, (int, float)) or not math.isfinite(c) for c in confidence):
        raise ValueError('invalid scores')
    return poses, confidence


def finish(response, folder, manifest):
    try:
        data = response.json()
        poses, confidence = validate_result(data)
    except (ValueError, TypeError):
        manifest.update(status='failed', error='NIM이 유효한 포즈·신뢰도 결과를 반환하지 않았습니다.')
        save(folder / 'manifest.json', manifest)
        return summarize(folder, manifest)
    manifest.pop('error', None)
    manifest.pop('http_status', None)
    save(folder / 'response.json', data)
    manifest['poses'] = []
    for i, (pose, score) in enumerate(zip(poses, confidence), 1):
        name = f'pose_{i:02d}.sdf'
        (folder / name).write_text(pose)
        manifest['poses'].append({'rank': i, 'confidence': score, 'file': name})
    manifest.update(status='completed', finished_at=datetime.now(timezone.utc).isoformat(),
                    response_sha256=hashlib.sha256((folder / 'response.json').read_bytes()).hexdigest(),
                    evidence_ids=[f"diffdock:live:{manifest['run_id']}:pose:{i}" for i in range(1, len(poses)+1)])
    save(folder / 'manifest.json', manifest)
    return summarize(folder, manifest)


def execute(*, api_key, protein_path=None, ligand_path=None, smiles=None, num_poses=5,
            output_root='data/discovery-runs', resume=None, timeout=300, client=None, poll_interval=2):
    if not api_key or api_key.startswith('<'):
        raise ValueError('NVIDIA_API_KEY를 저장소 .env 또는 환경변수에 설정하세요.')
    if not 1 <= num_poses <= 20 or not 1 <= timeout <= 1800:
        raise ValueError('num_poses는 1~20, timeout은 1~1800초여야 합니다.')
    if resume:
        folder = pathlib.Path(resume).resolve()
        manifest = json.loads((folder / 'manifest.json').read_text())
        if manifest.get('endpoint') != ENDPOINT:
            raise ValueError('지원하는 DiffDock 실행 기록이 아닙니다.')
        if manifest.get('status') == 'completed':
            return summarize(folder, manifest)
        rid = request_id(manifest.get('request_id'))
    else:
        if not protein_path or bool(ligand_path) == bool(smiles):
            raise ValueError('--protein과 --smiles 또는 --ligand-file 중 하나를 지정하세요.')
        protein = pathlib.Path(protein_path).read_text()
        if len(protein.encode()) > 5_000_000 or not any(x.startswith('ATOM  ') for x in protein.splitlines()):
            raise ValueError('5MB 이하의 ATOM 레코드가 있는 단백질 PDB 파일을 지정하세요.')
        # Supply only protein atoms; exclude co-crystallized ligand and solvent.
        protein = '\n'.join(x for x in protein.splitlines() if x.startswith(('ATOM  ', 'TER', 'END'))) + '\n'
        ligand = pathlib.Path(ligand_path).read_text() if ligand_path else smiles.strip()
        kind = 'sdf' if ligand_path and pathlib.Path(ligand_path).suffix.lower() == '.sdf' else 'txt'
        if not ligand.strip() or len(ligand.encode()) > 1_000_000:
            raise ValueError('비어 있지 않은 1MB 이하의 리간드 입력이 필요합니다.')
        if kind == 'sdf' and 'M  END' not in ligand:
            raise ValueError('올바른 SDF 파일이 아닙니다.')
        if kind == 'txt' and ('\n' in ligand.strip() or len(ligand.strip().split()) != 1):
            raise ValueError('SMILES는 이름 없이 한 줄의 분자 문자열로 입력하세요.')
        body = build_body(protein, ligand, kind, num_poses)
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:10]
        folder = pathlib.Path(output_root).resolve() / run_id
        folder.mkdir(parents=True, exist_ok=False, mode=0o700)
        save(folder / 'input.json', body)
        manifest = {'run_id': run_id, 'status': 'submitting', 'endpoint': ENDPOINT,
                    'created_at': datetime.now(timezone.utc).isoformat(), 'num_poses': num_poses,
                    'input_sha256': hashlib.sha256((folder / 'input.json').read_bytes()).hexdigest(), 'evidence_ids': []}
        save(folder / 'manifest.json', manifest)
        rid = None
    owned = client is None
    client = client or httpx.Client(follow_redirects=False)
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json', 'NVCF-POLL-SECONDS': '5'}
    deadline = time.monotonic() + timeout
    t0, polls, last = time.perf_counter(), 0, {'status': None, 'error': None, 'bytes_in': None, 'bytes_out': None}

    def log_call():
        if calllog is not None:
            calllog.record(url=ENDPOINT, model='mit/diffdock', purpose='CLI discover: fresh DiffDock run', reqid=rid,
                           http_status=last['status'], latency_ms=(time.perf_counter() - t0) * 1000,
                           bytes_in=last['bytes_in'], bytes_out=last['bytes_out'], error=last['error'],
                           extra={'polls': polls, 'run_id': manifest.get('run_id')}, code_path='api/_fv/docking.py:execute')
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                manifest.update(status='pending', error='대기 시간이 끝났습니다. --resume으로 같은 요청을 조회하세요.')
                break
            if rid:
                polls += 1
                response = client.get(STATUS + rid, headers=headers, timeout=min(30, remaining))
            else:
                response = client.post(ENDPOINT, headers=headers, json=body, timeout=min(60, remaining))
                try:
                    last['bytes_out'] = len(response.request.content)
                except Exception:  # noqa: BLE001
                    pass
            last['status'] = response.status_code
            try:
                last['bytes_in'] = len(response.content)
            except Exception:  # noqa: BLE001
                pass
            if response.headers.get('nvcf-reqid'):
                rid = request_id(response.headers['nvcf-reqid'])
                manifest['request_id'] = rid
                save(folder / 'manifest.json', manifest)
            if response.status_code == 200:
                out = finish(response, folder, manifest)
                last['error'] = None if manifest.get('status') == 'completed' else 'InvalidResult'
                log_call()
                return out
            if response.status_code == 202:
                rid = request_id(rid)
                manifest['status'] = 'pending'
                save(folder / 'manifest.json', manifest)
                time.sleep(min(poll_interval, max(0, deadline-time.monotonic())))
                continue
            manifest.update(status='failed', http_status=response.status_code,
                            error='NIM 요청 실패. 인증·권한·입력·할당량을 확인하세요. 자동 재제출하지 않았습니다.')
            break
    except httpx.TransportError as e:
        last['error'] = type(e).__name__
        manifest.update(status='pending' if rid else 'unknown',
                        error='통신이 중단되었습니다. 요청 ID가 있으면 --resume으로 조회하세요. 새 요청을 자동 제출하지 않았습니다.')
    except ValueError:
        last['error'] = 'InvalidRequestId'
        manifest.update(status='unknown', error='응답의 요청 ID를 확인할 수 없습니다. 자동 재제출하지 않았습니다.')
    finally:
        if owned:
            client.close()
    if last['error'] is None and manifest.get('status') != 'completed':
        last['error'] = manifest.get('status') or 'failed'
    log_call()
    save(folder / 'manifest.json', manifest)
    return summarize(folder, manifest)
