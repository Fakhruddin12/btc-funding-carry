"""Package the research snapshot; exclude render caches and copyrighted papers."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib,json
ROOT=Path(__file__).parent;OUT=ROOT/'deliverables'
path=OUT/'Relative_Value_Research_Code_Data.zip'
allowed={'data','crypto_data','inverse_data','reports','tests','deliverables'}
records=[]
with ZipFile(path,'w',ZIP_DEFLATED,compresslevel=6) as z:
    for f in sorted(ROOT.rglob('*')):
        if not f.is_file():continue
        rel=f.relative_to(ROOT)
        if len(rel.parts)>1 and rel.parts[0] not in allowed:continue
        if any(a in rel.parts for a in ['__pycache__','.pytest_cache']):continue
        if 'building' in f.name or f.suffix=='.zip' and rel.parts[0]=='deliverables':continue
        if f.name.endswith('.pyc'):continue
        arc=Path('relative_value_research')/rel
        if rel.parts[0]=='reports' and f.suffix=='.log' and not ('final' in f.name or f.name in ['robustness.log','inverse_1M_capacity_failure.log']):
            arc=Path('relative_value_research/reports/superseded_run_logs')/f.name
        z.write(f,str(arc));records.append(dict(path=str(arc),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
    legacy=ROOT.parent/'pairs_research'
    for f in sorted(legacy.rglob('*')):
        if not f.is_file() or '__pycache__' in f.parts or '.pytest_cache' in f.parts:continue
        if f.suffix in ['.pyc','.png','.pdf']:continue
        arc=Path('relative_value_research/legacy_equity')/f.relative_to(legacy)
        z.write(f,str(arc));records.append(dict(path=str(arc),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
    z.writestr('relative_value_research/RELEASE_CONTENTS.json',json.dumps(records,indent=2))
with ZipFile(path) as z:
    assert z.testzip() is None
    required=['README.md','carry.py','inverse.py','requirements.txt','reports/test_results.txt','deliverables/Quant_Relative_Value_Research.pdf']
    for f in required:assert 'relative_value_research/'+f in z.namelist()
print(json.dumps(dict(file=str(path),bytes=path.stat().st_size,files=len(records),sha256=hashlib.sha256(path.read_bytes()).hexdigest())))
