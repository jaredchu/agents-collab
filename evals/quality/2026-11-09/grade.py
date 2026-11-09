#!/usr/bin/env python3
"""Offline artifact grading. No providers; Python3.12+ and isolated public cache.

The grader file is committed by hash before participants and revealed later.
The artifact input is a frozen recorder directory, never an active checkout.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

from process_guard import run,restore_untracked,verify_restoration,cleanup_fixtures

BASE='37975b5245fcb5cac7b16fac74efd01269dff5d8'


def grade(args):
    case=args.artifact.resolve();dest=args.output.resolve();repo=dest/'repo'
    if dest==case or dest.is_relative_to(case):raise ValueError('grader output must be separate from artifact')
    if any((args.cache/f).exists() for f in ['credentials','credentials.toml']):raise ValueError('use credential-free public cache')
    dest.mkdir(parents=True,exist_ok=False);repo.mkdir();started=time.monotonic()
    archive=dest/'base.tar'
    with archive.open('wb') as out:subprocess.run(['git','archive',BASE],cwd=args.source,stdout=out,check=True)
    with tarfile.open(archive) as tar:tar.extractall(repo,filter='data')
    archive.unlink();patch=case/'complete.patch'
    if patch.read_text().strip():subprocess.run(['git','apply',str(patch)],cwd=repo,check=True)
    restore_untracked(case,repo)
    verify_restoration(case,repo)
    fixtures=args.fixture_root.resolve();fixtures.mkdir(mode=0o700,parents=True,exist_ok=False)
    env=os.environ.copy();env.update(PATH=str(args.toolchain.resolve())+os.pathsep+env['PATH'],RUSTC=str(args.toolchain.resolve()/'rustc'),RUSTDOC=str(args.toolchain.resolve()/'rustdoc'),CARGO_HOME=str(args.cache.resolve()),CARGO_TARGET_DIR=str(dest/'target'),CARGO_NET_OFFLINE='true',PROCLEASE_TEST_ROOT=str(fixtures/'t'),PROCLEASE_HOME=str(fixtures/'s'),XDG_STATE_HOME=str(fixtures/'xdg'),STUDY_CLEANUP_BINARY=str(args.cleanup_binary.resolve()),TMPDIR=str(dest/'tmp'))
    (dest/'tmp').mkdir()
    result={'task':args.task,'common':{},'objective':None,'source_fingerprint':hashlib.sha256((case/'final-files.json').read_bytes()).hexdigest(),'grader_sha256':hashlib.sha256(args.grader.read_bytes()).hexdigest()}
    for name,cmd in [('fmt',['cargo','fmt','--check']),('clippy',['cargo','clippy','--all-targets','--','-D','warnings']),('test',['cargo','test']),('build',['cargo','build'])]:
        with (dest/(name+'.log')).open('w') as out:
            r=run(cmd,cwd=repo,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=300)
        result['common'][name]={k:r[k] for k in ['exit_code','timed_out','owned_process_group']}
        if r['timed_out'] or r['owned_process_group']!='absent':
            result['incomplete']=True;result['stopped_after']=name;break
    if result['common'].get('build',{}).get('exit_code')==0 and not result.get('incomplete'):
        with (dest/'objective.json').open('w') as out,(dest/'objective.stderr').open('w') as err:
            r=run([str(args.python.resolve()),str(args.grader.resolve()),'--binary',str(dest/'target/debug/proclease'),'--task',args.task,'--root',str(fixtures/'o'),'--source',str(repo)],env=env,stdout=out,stderr=err,timeout=180)
            result['objective_exit_code']=r['exit_code'];result['objective_supervision']={k:r[k] for k in ['timed_out','owned_process_group']}
            if r['timed_out'] or r['owned_process_group']!='absent':result['incomplete']=True
        try:result['objective']=json.loads((dest/'objective.json').read_text())
        except (ValueError,OSError):result['objective_parse_error']=True
    else:result['objective_not_run']='build failed or check scheduling stopped; unavailable downstream checks are not individually counted defects'
    result['fixture_cleanup']=cleanup_fixtures(fixtures,args.cleanup_binary.resolve())
    if not result['fixture_cleanup']['observable_cleanup_complete']:result['incomplete']=True
    result['wall_clock_s']=round(time.monotonic()-started,3);(dest/'grade.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'task':args.task,'common':result['common'],'objective_exit':result.get('objective_exit_code')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['artifact','output','source','grader','toolchain','cache','fixture-root','python','cleanup-binary']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--task',required=True)
    grade(p.parse_args())
