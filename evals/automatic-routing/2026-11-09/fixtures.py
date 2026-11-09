#!/usr/bin/env python3
"""Process-free CLI acceptance fixtures. Run only on disposable state roots."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def seed(root, number, *, owner='a', task='t1', state='exited', finished=None):
    ident = f'{number:012x}'
    directory = root / ident
    directory.mkdir(mode=0o700)
    now = int(time.time() * 1000)
    record = dict(schema_version=1, id=ident, argv=['/usr/bin/true'], cwd='/',
                  owner=owner, task=task, name=None, url=None, created_at_ms=now-100000-number,
                  expires_at_ms=now-50000, state=state, reason='command_exit', keeper_pid=0,
                  guardian_pid=None, command_pid=None, exit_code=0, finished_at_ms=finished,
                  log_limit_bytes=1048576, logs_truncated=False, error=None)
    (directory/'record.json').write_text(json.dumps(record))
    (directory/'output.log').write_text('one\ntwo\nthree\n')
    return ident


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.glob('*/record.json')}


def evaluate(binary, root, task):
    root = root.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    env = os.environ.copy()
    env['PROCLEASE_HOME'] = str(root.resolve())
    checks = {}
    def call(*args):
        return subprocess.run([str(binary.resolve()), *args], env=env, capture_output=True,
                              text=True, timeout=10)
    def data(*args):
        r = call('--json', *args)
        try:
            return r, json.loads(r.stdout)
        except ValueError:
            return r, {}
    def ids(value):
        return {j['id'] for j in value.get('jobs', [])}
    now = int(time.time()*1000)
    if task == 'C1':
        ident = seed(root, 0xc01, finished=now-60000)
        output = root/ident/'output.log'
        output.unlink()
        marker = root/'marker.txt'
        marker.write_text('GRADER-MARKER-C1')
        output.symlink_to(marker)
        assert marker.is_file() and output.resolve(strict=True) == marker.resolve(strict=True)
        for mode, args in [('json', ['--json']), ('human', [])]:
            r = call(*args, 'logs', ident)
            checks['symlink_refused_'+mode] = r.returncode == 1 and 'GRADER-MARKER-C1' not in r.stdout+r.stderr
        output.unlink()
        output.write_text('one\ntwo\nthree\n')
        r, value = data('logs', ident)
        checks['regular_log'] = r.returncode == 0 and value.get('lines') == ['one','two','three']
    elif task == 'S1':
        matching = [seed(root, i+1, owner='a', task='t1', finished=now-15000+i*1000) for i in range(7)]
        other = [seed(root, 20+i, owner='b', task='t2', finished=now-2000+i*200) for i in range(3)]
        none = seed(root, 30, task=None, finished=now-10000)
        ua = seed(root, 40, state='unknown')
        ub = seed(root, 41, owner='b', task='t2', state='unknown')
        malformed = root/'000000000099'
        malformed.mkdir(mode=0o700)
        (malformed/'record.json').write_text('invalid-json')
        before = hashes(root)
        for verb in ['list','watch']:
            once = ['--once'] if verb == 'watch' else []
            for label, flags, expected in [
                ('owner-all',['--all','--owner','a'],set(matching+[none,ua])),
                ('task-all',['--all','--task','t1'],set(matching+[ua])),
                ('both',['--all','--owner','a','--task','t1'],set(matching+[ua])),
                ('default',['--owner','a','--task','t1'],set(matching[-5:]+[ua])),
                ('case',['--all','--owner','A'],set()),
                ('owner-b',['--all','--owner','b'],set(other+[ub]))]:
                r, value = data(verb,*once,*flags)
                checks[verb+'-'+label] = ids(value) == expected and 'jobs' in value
                checks[verb+'-'+label+'-warnings'] = bool(value.get('warnings'))
            for label in ['a\x01','x'*513]:
                r, value = data(verb,*once,'--owner',label)
                checks[verb+'-invalid-'+str(len(label))] = r.returncode == 1 and 'error' in value and 'jobs' not in value
        checks['record_bytes_unchanged'] = before == hashes(root)
    elif task == 'S2':
        finished = [seed(root, i+1, finished=now-100000+i*1000) for i in range(12)]
        ua = seed(root, 40, state='unknown')
        ub = seed(root, 41, state='unknown')
        unverified = seed(root, 42)
        required = {ua,ub,unverified}
        before = hashes(root)
        for limit, expected, omitted in [(0,required,12),(4,required|set(finished[-4:]),8),
                                          (100,required|set(finished),0)]:
            r, value = data('list','--all','--limit',str(limit))
            checks['all-limit-'+str(limit)] = r.returncode == 0 and ids(value) == expected and value.get('omitted_finished') == omitted
        r, value = data('list','--all')
        checks['without_limit_envelope'] = 'omitted_finished' not in value and ids(value) == required|set(finished)
        r = call('list','--all','--limit','4')
        checks['human_notice'] = r.returncode == 0 and '8' in r.stderr and '--limit' in r.stderr
        for label in ['-1','abc','101']:
            r, value = data('list','--limit',label)
            checks['invalid-'+label] = r.returncode != 0 and 'jobs' not in value
        # Recent-window and tie tests use a separate state directory, not real jobs.
        recent = root/'recent'
        recent.mkdir(mode=0o700)
        env['PROCLEASE_HOME'] = str(recent)
        for i in range(8): seed(recent, i+1, finished=now-15000+i*1000)
        r, value = data('list','--limit','2')
        checks['recent_window'] = ids(value) == {f'{i:012x}' for i in [7,8]} and value.get('omitted_finished') == 3
        tie = root/'tie'
        tie.mkdir(mode=0o700)
        env['PROCLEASE_HOME'] = str(tie)
        for i in [1,2]: seed(tie, i, finished=now-60000)
        r, value = data('list','--all','--limit','1')
        checks['finish_time_tie'] = ids(value) == {'000000000002'}
        checks['record_bytes_unchanged'] = before == hashes(root)
    else:
        raise ValueError('supported fixture tasks: S1 S2 C1')
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--task', choices=['S1','S2','C1'], required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.binary,args.root,args.task),indent=2))
