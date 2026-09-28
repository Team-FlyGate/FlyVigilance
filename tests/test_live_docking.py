import json
import pathlib
import sys
import httpx
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'api'))
from _fv import docking

@pytest.fixture
def inputs(tmp_path):
    p = tmp_path / 'protein.pdb'; p.write_text('ATOM      1  N   ALA A   1      0.0 0.0 0.0\n')
    return dict(api_key='test-secret', protein_path=p, smiles='CCO', output_root=tmp_path/'runs', poll_interval=0)

def response():
    return {'status':'success','ligand_positions':['pose\nM  END\n$$$$'], 'position_confidence':[0.8]}

def test_live_and_resume_without_resubmission(inputs):
    methods=[]
    def handle(req):
        methods.append(req.method)
        if req.method=='POST': return httpx.Response(202, headers={'nvcf-reqid':'job-1'})
        return httpx.Response(200,json=response())
    with httpx.Client(transport=httpx.MockTransport(handle)) as c:
        r=docking.execute(**inputs,client=c)
        assert r['status']=='completed' and methods==['POST','GET']
        assert pathlib.Path(r['run_dir'],'pose_01.sdf').exists()
        again=docking.execute(api_key='test-secret',resume=r['run_dir'],client=c)
        assert again['status']=='completed' and methods==['POST','GET']
        for p in pathlib.Path(r['run_dir']).iterdir(): assert 'test-secret' not in p.read_text()

def test_timeout_never_resubmits(inputs):
    methods=[]
    def handle(req):
        methods.append(req.method); raise httpx.ReadTimeout('test-secret',request=req)
    with httpx.Client(transport=httpx.MockTransport(handle)) as c:r=docking.execute(**inputs,client=c)
    assert r['status']=='unknown' and methods==['POST']
    assert 'test-secret' not in json.dumps(r)

def test_pending_resume_only_polls(inputs):
    calls=[]
    def initial(req):
        calls.append(req.method)
        if req.method=='POST':return httpx.Response(202,headers={'nvcf-reqid':'job-2'})
        raise httpx.ReadTimeout('timeout',request=req)
    with httpx.Client(transport=httpx.MockTransport(initial)) as c:r=docking.execute(**inputs,client=c)
    assert r['status']=='pending'
    def finish(req):
        assert req.method=='GET';return httpx.Response(200,json=response())
    with httpx.Client(transport=httpx.MockTransport(finish)) as c:
        r=docking.execute(api_key='test-secret',resume=r['run_dir'],client=c)
    assert r['status']=='completed'

@pytest.mark.parametrize('code',[401,422,429,503])
def test_http_failure(inputs,code):
    calls=[]
    def handle(req):calls.append(req.method);return httpx.Response(code,text='test-secret')
    with httpx.Client(transport=httpx.MockTransport(handle)) as c:r=docking.execute(**inputs,client=c)
    assert r['status']=='failed' and calls==['POST'] and 'test-secret' not in json.dumps(r)

def test_bad_success_is_not_a_result(inputs):
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'status':'success'}))) as c:
        r=docking.execute(**inputs,client=c)
    assert r['status']=='failed' and r['evidence_ids']==[]

def test_inputs_before_network(inputs):
    inputs['smiles']=''
    with pytest.raises(ValueError):docking.execute(**inputs)
    assert not pathlib.Path(inputs['output_root']).exists()
