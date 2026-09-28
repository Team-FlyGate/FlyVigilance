"""NVIDIA browser-assisted key setup; no password collection or token scraping."""
from __future__ import annotations
import getpass
import os
import sys
import warnings
import webbrowser

URL = 'https://build.nvidia.com/settings/api-keys'
SERVICE = 'FlyGate CLI'
ACCOUNT = 'NVIDIA_API_KEY'


def secure_store():
    try:
        import keyring
        backend = keyring.get_keyring()
        module = type(backend).__module__
        if module.startswith(('keyring.backends.macOS', 'keyring.backends.Windows',
                              'keyring.backends.SecretService', 'keyring.backends.kwallet')):
            return backend
    except Exception:
        pass
    return None


def load_key():
    from _fv import config
    backend = secure_store()
    for account in ('NVIDIA_API_KEY', 'TYPESAFE_API_KEY'):
        key = getattr(config, account)
        if not key and backend:
            try: key = backend.get_password(SERVICE, account)
            except Exception: key = None
        if key:
            setattr(config, account, key); os.environ[account] = key
    return bool(config.NVIDIA_API_KEY)


def validate_key(key):
    import httpx
    from _fv import config
    try:
        r = httpx.post(config.NIM_URL + '/chat/completions',
                       headers={'Authorization': 'Bearer ' + key},
                       json={'model':config.MODEL_DELIBERATE[0],
                             'messages':[{'role':'user','content':'Reply OK.'}],
                             'max_tokens':8, 'temperature':0,
                             'chat_template_kwargs':{'enable_thinking':False}}, timeout=30)
        return r.status_code == 200 and bool(r.json().get('choices'))
    except (httpx.HTTPError, ValueError):
        return False


def validate_jev(key):
    import httpx
    from _fv import config
    try:
        r = httpx.post(config.JEV_URL, headers={'Authorization': 'Bearer ' + key},
                       json={'model':config.JEV_MODEL, 'state':'This is a connection test.',
                             'questions':{'connection':{'type':'noul', 'instructions':'Is this a connection test?'}}}, timeout=30)
        return r.status_code == 200 and isinstance(r.json().get('answers'), dict)
    except (httpx.HTTPError, ValueError): return False


def login(*, reader=input, writer=print, secret_reader=getpass.getpass, opener=webbrowser.open,
          validator=validate_key, jev_validator=validate_jev, store_getter=secure_store):
    if not sys.stdin.isatty():
        writer('  키 등록은 입력을 숨길 수 있는 대화형 터미널에서 flygate login으로 실행하세요.')
        return False
    from _fv import config
    writer('\n  서비스 연결 · 입력은 숨겨집니다. Enter로 건너뛰면 기존 설정을 유지합니다.')
    writer('  연결 확인에는 각 서비스에 짧은 요청을 보내며 소량의 API 사용량이 발생할 수 있습니다.')
    providers = [('NVIDIA_API_KEY', 'NVIDIA', validator), ('TYPESAFE_API_KEY', 'TypeSafe AI / Jev (선택)', jev_validator)]
    for account, label, check in providers:
        writer('\n  ' + label + (' · 기존 키 있음' if getattr(config, account) else ' · 미연결'))
        if account == 'NVIDIA_API_KEY':
            writer('  공식 페이지에서 로그인 → Generate API Key → Copy: ' + URL)
            if not config.NVIDIA_API_KEY:
                try: opener(URL)
                except Exception: writer('  브라우저가 열리지 않으면 위 주소를 직접 여세요.')
        else:
            writer('  Jev 판단용 키입니다. 키가 없어도 NVIDIA 대화와 DiffDock은 사용할 수 있습니다.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                key = secret_reader('  ' + label + ' API key (Enter: 건너뛰기): ').strip()
        except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
            writer('\n  안전한 키 입력을 취소했습니다.'); break
        if not key:
            writer('  건너뛰었습니다.'); continue
        if any(c.isspace() for c in key) or (account == 'NVIDIA_API_KEY' and not key.startswith('nvapi-')):
            writer('  키 형식을 확인하세요. 저장하지 않았습니다.'); continue
        if not check(key):
            writer('  연결을 확인하지 못했습니다. 키·권한·할당량·네트워크를 확인하세요. 저장하지 않았습니다.'); continue
        setattr(config, account, key); os.environ[account] = key
        writer('  연결을 확인했습니다. 현재 세션에서 사용할 수 있습니다.')
        backend = store_getter()
        if backend:
            try: answer = reader('  OS 보안 저장소에 저장해 다음 실행부터 연결할까요? [y/N] ').strip().lower()
            except (EOFError, KeyboardInterrupt): answer = ''
            if answer in ('y','yes','네','예'):
                try:
                    backend.set_password(SERVICE, account, key)
                    writer('  OS 보안 저장소에 저장했습니다. 소스 코드나 .env에는 쓰지 않았습니다.')
                except Exception: writer('  보안 저장소 저장에 실패했습니다. 현재 세션에서만 사용합니다.')
        else: writer('  사용 가능한 OS 보안 저장소가 없어 현재 세션에서만 사용합니다.')
    writer('\n  NVIDIA: ' + ('연결됨' if config.NVIDIA_API_KEY else '미연결') +
           ' / Jev: ' + ('연결됨' if config.TYPESAFE_API_KEY else '건너뜀'))
    return bool(config.NVIDIA_API_KEY or config.TYPESAFE_API_KEY)
