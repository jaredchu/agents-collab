"""Post-freeze corroborations; no actor edits, no replacement of frozen checks."""
from pathlib import Path
import importlib.util,sys,os,json,time,fcntl
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binaries',type=Path,required=True,help='JSON: task -> artifact ID -> executable path; optional base ID')
parser.add_argument('--fixture-root',type=Path,required=True,help='New, short, private owned fixture directory')
parser.add_argument('--cleanup-binary',type=Path,required=True,help='Trusted pinned-base ProcLease executable')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();args.fixture_root.mkdir(mode=0o700,parents=True,exist_ok=False)
W=Path(__file__).parent;sys.path.insert(0,str(W))
spec=importlib.util.spec_from_file_location('oracle',W/'revealed-grader.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
os.environ['STUDY_CLEANUP_BINARY']=str(args.cleanup_binary.resolve())
items=[{'task':task,'opaque':opaque,'binary':str(Path(binary).resolve())} for task,artifacts in json.loads(args.binaries.read_text()).items() for opaque,binary in artifacts.items()];results=[]
for index,p in enumerate(items):
 root=args.fixture_root/('sp'+str(index));root.mkdir(mode=0o700)
 binary=Path(p['binary']);ctx=g.Context(binary,root,None);st=ctx.state('s');row={'task':p['task'],'artifact_id':p['opaque'],'post_freeze':True}
 try:
  if p['task']=='Q4':
   ident=g.seed(st,9001,'failed',g.now_ms()-5000,g.now_ms()-4000,reason='launch_failed');q=st/'.prune-a00000000009-0123456789abcdef0123456789abcdef';q.mkdir(mode=0o700);g.write_private(q/'payload',b'pending retained history\n')
   fd=os.open(st/'.retention',os.O_RDWR|os.O_CREAT,0o600);fcntl.flock(fd,fcntl.LOCK_SH);ctx.locks.append(fd)
   # Read dry preview first so a destructive real call cannot alter the comparison state.
   dry=ctx.run(st,'prune','--dry-run',*(['--keep','0'] if p['opaque']!='base' else [])).ok_json();real=ctx.run(st,'prune',*(['--keep','0'] if p['opaque']!='base' else [])).ok_json()
   row.update(dry=dry,real=real,ordinary_history_preserved=(st/ident).exists(),quarantine_preserved=q.exists(),dry_candidates_equal_real_removed=set(dry['candidates'])==set(real['removed']))
  else:
   caller=ctx.state('c');script=caller/'probe';g.write_private(script,b'#!/bin/sh\nprintf "%s\\n" "$0"\n');script.chmod(0o700)
   r=ctx.run(st,'run','--ttl','30s','--grace','100ms','--','./probe',cwd=caller);v=r.ok_json();ident=v['job']['id'];ctx.launched.append(ident)
   deadline=time.monotonic()+8
   while time.monotonic()<deadline:
    jobs=ctx.run(st,'list','--all',cwd=caller).ok_json()['jobs'];job=next(j for j in jobs if j['id']==ident)
    if job['state']in g.TERMINAL:break
    time.sleep(.1)
   logs=ctx.run(st,'logs',ident,cwd=caller).ok_json();row.update(state=job['state'],actual_lines=logs['lines'],expected_lines=['./probe'],invocation_name_preserved=logs['lines']==['./probe'])
 finally:ctx.close();row['cleanup']=ctx.cleanup
 results.append(row)
args.output.write_text(json.dumps(results,indent=2)+'\n');print('recorded supplementary corroborations',len(results))
