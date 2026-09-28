import importlib.util
import pathlib
import sys
import json
import pytest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'api'))
sys.path.insert(0,str(ROOT/'agent'))
spec=importlib.util.spec_from_file_location('flygate_chat',ROOT/'agent/chat.py')
chat=importlib.util.module_from_spec(spec);spec.loader.exec_module(chat)
from _fv import config


def session(monkeypatch, lines, responder=None):
    monkeypatch.setattr(config,'NVIDIA_API_KEY','test-key' if responder else '')
    it=iter(lines); output=[]; calls=[]
    def reader(prompt):
        try:return next(it)
        except StopIteration:raise EOFError
    def runner(cmd):calls.append(cmd);return {'exit_code':0,'stdout':'{"cmd":"discover","evidence_ids":["test:id"]}','stderr':''}
    kwargs=dict(plain=True,reader=reader,writer=output.append,runner=runner)
    if responder:kwargs['responder']=responder
    chat.run(**kwargs)
    return '\n'.join(output),calls


def test_declined_tool_never_runs(monkeypatch):
    out,calls=session(monkeypatch,['/run discover parp1','n','/exit'])
    assert not calls and '실행하지 않았습니다' in out and 'FlyDiscovery + FlyVigilance' in out


def test_approved_and_last_and_clear(monkeypatch):
    out,calls=session(monkeypatch,['/run discover parp1','y','/last','/clear','/last','/exit'])
    assert calls==[['discover','parp1']] and 'test:id' in out and '아직 실행한 결과' in out


def test_natural_language_proposal_and_context(monkeypatch):
    histories=[]
    async def respond(messages,model):
        histories.append(json.loads(json.dumps(messages)))
        return {'reply':'PARP1을 조회하겠습니다.','command':['discover','parp1']} if len(histories)==1 else {'reply':'근거 ID입니다.','command':None}
    out,calls=session(monkeypatch,['PARP1을 보여줘','y','결과 설명해줘','/exit'],respond)
    assert calls==[['discover','parp1']] and '근거 ID입니다' in out
    assert any('TOOL RESULT' in m['content'] for m in histories[1])


def test_secrets_not_sent(monkeypatch):
    async def respond(*args):raise AssertionError('must not send')
    out,calls=session(monkeypatch,['nvapi-'+'a'*25,'/exit'],respond)
    assert not calls and '전송하지 않았습니다' in out


@pytest.mark.parametrize('cmd',[['bash','-c','echo bad'],['chat'],['discover','nvapi-'+'a'*25],['discover','parp1\nexit']])
def test_restricted_invocations(cmd):
    with pytest.raises(ValueError):chat.validate_command(cmd)


def test_no_ansi_in_model_text():
    assert chat.safe_text('\x1b[31mhello\x1b[0m')=='hello'


def test_offline_question_no_faked_answer(monkeypatch):
    out,calls=session(monkeypatch,['약물 찾아줘','/exit'])
    assert not calls and 'NVIDIA_API_KEY가 필요' in out


def test_banner_sizes_and_dashboard():
    from banner import render,dashboard
    for width in (35,60,80,110):
        text=render(width,False)
        assert 'FlyGate CLI' in text
        assert max(map(len,text.splitlines())) <= width
        box=dashboard(ROOT,'nvidia/nemotron-3-super-120b-a12b',True,False,width,False,'test')
        assert 'discover' in box and '7 tools' in box
        assert max(map(len,box.splitlines())) <= width


@pytest.mark.parametrize('tool', sorted(chat.ALLOWED))
def test_direct_slash_tools(monkeypatch, tool):
    out, calls = session(monkeypatch, ['/'+tool+' --help', 'y', '/exit'])
    assert calls == [[tool, '--help']]


def test_direct_slash_quoted_args_and_decline(monkeypatch):
    out, calls = session(monkeypatch, ['/signals "drug name"', 'y', '/discover parp1', 'n', '/exit'])
    assert calls == [['signals', 'drug name']]
    assert '실행하지 않았습니다' in out
