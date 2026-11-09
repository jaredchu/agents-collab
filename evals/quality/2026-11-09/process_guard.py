"""Bound check processes and inspect only explicitly owned fixture registries."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time


def group_state(pid):
    try:os.killpg(pid,0);return 'present'
    except ProcessLookupError:return 'absent'
    except PermissionError:return 'unknown'


def stop_group(process,grace=2):
    for sig,seconds in [(signal.SIGTERM,grace),(signal.SIGKILL,2)]:
        try:os.killpg(process.pid,sig)
        except ProcessLookupError:break
        except PermissionError:return 'unknown'
        end=time.monotonic()+seconds
        while group_state(process.pid)=='present' and time.monotonic()<end:
            process.poll();time.sleep(.025)
        if group_state(process.pid)=='absent':break
    try:process.wait(timeout=2)
    except subprocess.TimeoutExpired:process.kill();process.wait()
    return group_state(process.pid)


def run(argv,*,cwd=None,env=None,stdout=None,stderr=None,timeout=300):
    p=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
    timed=False;out=err=None
    try:out,err=p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:timed=True;out=exc.output;err=exc.stderr
    finally:cleanup=stop_group(p)
    # After termination, never wait indefinitely for a detached inherited pipe.
    if timed:
        try:
            more_out,more_err=p.communicate(timeout=.5)
            if more_out is not None:out=more_out
            if more_err is not None:err=more_err
        except subprocess.TimeoutExpired:pass
    for stream in [p.stdin,p.stdout,p.stderr]:
        if stream:stream.close()
    return {'exit_code':124 if timed else p.returncode,'timed_out':timed,
            'owned_process_group':cleanup,'stdout':out,'stderr':err}


def manifest(repo):
    """Tracked and ordinary untracked source identity, including Git modes."""
    names=subprocess.run(['git','ls-files','-c','-o','--exclude-standard','-z'],cwd=repo,capture_output=True,check=True).stdout.split(b'\0')
    import hashlib
    result={}
    for raw in sorted(set(names)):
        if not raw:continue
        name=os.fsdecode(raw);p=Path(repo)/name
        if p.is_symlink():result[name]={'symlink':os.readlink(p),'git_mode':'120000'}
        elif p.is_file():result[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'git_mode':'100755' if p.stat().st_mode & 0o111 else '100644'}
    return result


def restore_untracked(case,repo):
    for entry in json.loads((Path(case)/'untracked.json').read_text()):
        name=entry['path'];dest=Path(repo)/name
        # Source names come from git ls-files, still validate lexical traversal.
        if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('unsafe artifact path')
        dest.parent.mkdir(parents=True,exist_ok=True)
        if 'symlink' in entry:
            if dest.exists() or dest.is_symlink():dest.unlink()
            dest.symlink_to(entry['symlink'])
        elif 'sha256' in entry:
            source=Path(case)/'untracked.private'/name
            if dest.is_symlink():dest.unlink()
            dest.write_bytes(source.read_bytes());os.chmod(dest,0o755 if entry.get('git_mode')=='100755' else 0o644)


def verify_restoration(case,repo):
    expected=json.loads((Path(case)/'final-files.json').read_text())
    # The reconstructed grading tree has no .git; enumerate only expected files,
    # then compare its actual regular/symlink source paths before build outputs.
    import hashlib
    actual={}
    for p in Path(repo).rglob('*'):
        if p.is_symlink():actual[str(p.relative_to(repo))]={'symlink':os.readlink(p),'git_mode':'120000'}
        elif p.is_file():actual[str(p.relative_to(repo))]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'git_mode':'100755' if p.stat().st_mode & 0o111 else '100644'}
    mismatch=sorted(k for k in set(expected)|set(actual) if expected.get(k)!=actual.get(k))
    if mismatch:raise ValueError('artifact reconstruction mismatch: '+', '.join(mismatch[:12]))
    return True


def cleanup_fixtures(root,binary):
    """Use trusted ProcLease on job IDs found only below this owned fixture root.

    A process with deleted metadata or a different detached session cannot be
    ruled out by this inventory. Never signal a PID copied from a record.
    """
    root=Path(root).resolve();jobs=[];unresolved=[]
    terminal={'stopped','expired','exited','failed','interrupted'}
    for launch in root.rglob('launch.json'):
        if launch.is_symlink() or not re.fullmatch('[0-9a-f]{12}',launch.parent.name):continue
        state=launch.parent.parent
        if not state.resolve().is_relative_to(root):continue
        marker=launch.parent/'.quality-simulated-fixture'
        if marker.is_file() and not marker.is_symlink() and marker.read_text()=='no process behind this record':continue
        rec=launch.parent/'record.json'
        try:data=json.loads(rec.read_text()) if not rec.is_symlink() else {}
        except (OSError,ValueError):data={}
        record={'id':launch.parent.name,'registry':str(state),'state':data.get('state')}
        if data.get('state') not in terminal:
            with tempfile.TemporaryFile(dir=root) as out,tempfile.TemporaryFile(dir=root) as err:
                r=run([str(binary),'--state-dir',str(state),'--json','stop',launch.parent.name],stdout=out,stderr=err,timeout=5)
                out.seek(0)
                try:answer=json.loads(out.read());record['stop_state']=answer.get('job',{}).get('state')
                except ValueError:record['stop_state']='unverified'
                record['stop_exit']=r['exit_code']
        jobs.append(record)
    end=time.monotonic()+6
    while True:
        unresolved=[]
        for job in jobs:
            p=Path(job['registry'])/job['id'];rec=p/'record.json'
            try:data=json.loads(rec.read_text()) if not rec.is_symlink() else {}
            except (OSError,ValueError):data={}
            job['final_state']=data.get('state')
            if data.get('state') not in terminal or (p/'ctl.sock').exists():unresolved.append(job['id'])
        if not unresolved or time.monotonic()>=end:break
        time.sleep(.1)
    return {'jobs':jobs,'unresolved_ids':unresolved,'observable_cleanup_complete':not unresolved,
            'detached_process_absence':'not guaranteed when metadata has been deleted'}
