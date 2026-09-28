import importlib.util
import pathlib
import sys
import getpass
import warnings
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'api'))
spec=importlib.util.spec_from_file_location('fg_auth',ROOT/'agent/auth.py')
auth=importlib.util.module_from_spec(spec);spec.loader.exec_module(auth)
from _fv import config

@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(sys.stdin,'isatty',lambda:True)
    for k in ('NVIDIA_API_KEY','TYPESAFE_API_KEY'):
        monkeypatch.setattr(config,k,'');monkeypatch.delenv(k,raising=False)
    return monkeypatch

def test_nvidia_and_optional_jev(setup):
    values=iter(['nvapi-test-secret','jev-test-secret']);output=[];saved=[]
    class Store:
        def set_password(self,service,account,key):saved.append(account)
    assert auth.login(secret_reader=lambda p:next(values),validator=lambda k:True,jev_validator=lambda k:True,
                      opener=lambda u:True,reader=lambda p:'y',writer=output.append,store_getter=lambda:Store())
    assert saved==['NVIDIA_API_KEY','TYPESAFE_API_KEY']
    assert 'nvapi-test-secret' not in '\n'.join(output) and 'jev-test-secret' not in '\n'.join(output)

def test_skip_jev(setup):
    values=iter(['nvapi-test-secret',''])
    assert auth.login(secret_reader=lambda p:next(values),validator=lambda k:True,
                      opener=lambda u:True,writer=lambda s:None,store_getter=lambda:None)
    assert not config.TYPESAFE_API_KEY

def test_skip_preserves_existing(setup):
    setup.setattr(config,'NVIDIA_API_KEY','existing')
    assert auth.login(secret_reader=lambda p:'',writer=lambda s:None,opener=lambda u:None)
    assert config.NVIDIA_API_KEY=='existing'

def test_no_echo_fallback(setup):
    def unsafe(p):warnings.warn('no tty',getpass.GetPassWarning)
    assert not auth.login(secret_reader=unsafe,writer=lambda s:None,opener=lambda u:None)
    assert not config.NVIDIA_API_KEY

def test_invalid_key_not_saved(setup):
    values=iter(['nvapi-bad-key',''])
    assert not auth.login(secret_reader=lambda p:next(values),validator=lambda k:False,
                          writer=lambda s:None,opener=lambda u:None)
    assert not config.NVIDIA_API_KEY
