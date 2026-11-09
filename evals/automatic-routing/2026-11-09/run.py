#!/usr/bin/env python3
"""Study-only RPC recorder. Requires existing subscription-authenticated CLIs.

No HOME/CODEX_HOME changes, permission bypass, production edits, or auto-publish.
Raw events are private diagnostics; review/sanitize evidence before publishing.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import tarfile
import time

HERE = Path(__file__).resolve().parent
BASE = '37975b5245fcb5cac7b16fac74efd01269dff5d8'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv, cwd, **kwargs):
    return subprocess.run(argv, cwd=cwd, check=True, capture_output=True, **kwargs)


def snapshot(source, destination, task):
    """Export only frozen tracked bytes, without future refs or live state."""
    destination.mkdir(parents=True, exist_ok=False)
    archive = destination.parent / 'base.tar'
    with archive.open('wb') as out:
        subprocess.run(['git', 'archive', BASE], cwd=source, stdout=out, check=True)
    # git archive of this verified public commit contains no escaping paths.
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError('archive member escapes snapshot')
        tar.extractall(destination, filter='data')
    seed = task.get('seed')
    if seed and 'patch' in seed:
        command(['git', 'apply', str(HERE / seed['patch'])], destination)
    command(['git', 'init', '-q'], destination)
    command(['git', 'add', '.'], destination)
    command(['git', '-c', 'user.name=Evaluation', '-c',
             'user.email=evaluation@example.invalid', 'commit', '-qm',
             'Evaluation snapshot based on ProcLease 37975b5 (may include authored evaluation changes)'], destination)
    archive.unlink()


class RPC:
    def __init__(self, argv, env, stderr, cwd):
        self.err = stderr.open('wb')
        self.proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.err,
                                     bufsize=0, start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)
        self.buffer = b''
        self.queue = []
        self.events = []
        self.next_id = 0

    def send(self, obj):
        self.proc.stdin.write((json.dumps(obj) + '\n').encode())

    def read(self, deadline):
        while not self.queue:
            if time.monotonic() >= deadline:
                raise TimeoutError('study hard deadline')
            if self.proc.poll() is not None:
                raise RuntimeError('app-server exited before turn completion')
            if not self.selector.select(timeout=.25):
                continue
            data = os.read(self.proc.stdout.fileno(), 65536)
            if not data:
                raise RuntimeError('app-server output closed')
            self.buffer += data
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                if line.strip():
                    self.queue.append(json.loads(line))
        obj = self.queue.pop(0)
        if 'method' in obj:
            self.events.append(obj)
        # Unattended study: never grant an interactive request or tool escalation.
        if 'id' in obj and 'method' in obj:
            self.send({'id': obj['id'], 'error': {'code': -32000,
                       'message': 'Interactive request unavailable in this study'}})
        return obj

    def request(self, method, params, deadline):
        self.next_id += 1
        ident = self.next_id
        self.send({'id': ident, 'method': method, 'params': params})
        while True:
            obj = self.read(deadline)
            if obj.get('id') == ident and 'method' not in obj:
                if 'error' in obj:
                    raise RuntimeError(json.dumps(obj['error']))
                return obj['result']

    def close(self):
        def alive():
            try:
                os.killpg(self.proc.pid, 0)
                return True
            except ProcessLookupError:
                return False
            except PermissionError:
                return None
        def stop(sig):
            try:
                os.killpg(self.proc.pid, sig)
            except ProcessLookupError:
                pass
        # Reap the parent, but check group survival independently of its exit.
        stop(signal.SIGTERM)
        grace = time.monotonic() + 5
        while alive() is True and time.monotonic() < grace:
            self.proc.poll()
            time.sleep(.05)
        if alive() is True:
            stop(signal.SIGKILL)
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        deadline = time.monotonic() + 2
        while alive() is True and time.monotonic() < deadline:
            time.sleep(.05)
        observed = alive()
        self.selector.close()
        self.proc.stdin.close()
        self.proc.stdout.close()
        self.err.close()
        return {'owned_process_group': 'absent' if observed is False else
                'still_present' if observed is True else 'unknown',
                'external_provider_workers': 'unverified'}


def receipts(events):
    result = {'skill_read_candidates': [], 'native_dispatches': [],
              'claude_command_candidates': [], 'commands': 0,
              'token_updates': [], 'errors': [], 'final_messages': []}
    seen = set()
    for n, event in enumerate(events):
        method = event.get('method', '')
        p = event.get('params', {})
        item = p.get('item', {})
        if method == 'item/completed' and item.get('type') == 'commandExecution':
            result['commands'] += 1
            cmd = item.get('command', '')
            out = item.get('aggregatedOutput', '') or ''
            if 'agents-collab' in cmd and 'SKILL.md' in cmd:
                result['skill_read_candidates'].append({'event': n, 'command': cmd,
                    'exit_code': item.get('exitCode'),
                    'content_observed': '# Agents Collab' in out and 'Load and resolve' in out})
            if 'claude' in cmd:
                result['claude_command_candidates'].append({'event': n, 'command': cmd,
                    'exit_code': item.get('exitCode'), 'output': out})
        if item.get('type') == 'subAgentActivity' and item.get('kind') == 'started':
            key = item.get('agentThreadId')
            if key not in seen:
                seen.add(key)
                result['native_dispatches'].append({'event': n, 'thread_id': key,
                    'model': item.get('model'), 'reasoning': item.get('reasoningEffort'),
                    'fresh_history': 'unknown'})
        if method == 'thread/tokenUsage/updated':
            result['token_updates'].append({'event': n, 'data': p})
        if method == 'error':
            result['errors'].append({'event': n, 'data': p})
        if method == 'item/completed' and item.get('type') == 'agentMessage':
            result['final_messages'].append({'event': n, 'text': item.get('text', '')})
    return result


def run(args):
    work = args.work_root.resolve()
    if work.is_relative_to(HERE.parents[2]) or work == Path.home():
        raise ValueError('work root must be private and outside source')
    case = work / 'cases' / args.run_id
    case.mkdir(parents=True, exist_ok=False)
    task = next(t for t in json.loads((HERE / 'tasks.json').read_text())['tasks']
                if t['id'] == args.task)
    repo = case / 'repo'
    snapshot(args.source.resolve(), repo, task)
    initial_commit = command(['git','rev-parse','HEAD'],repo).stdout.decode().strip()
    initial_tree = command(['git','rev-parse','HEAD^{tree}'],repo).stdout.decode().strip()
    for name in ['scratch', 'records', 'target', 'tmp']:
        (case / name).mkdir()
    fixtures = args.fixture_root.resolve() / args.run_id
    fixtures.mkdir(parents=True, exist_ok=False)
    os.chmod(fixtures, 0o700)
    profile = json.loads((HERE / 'profile.example.json').read_text())
    profile['records_root'] = str(case / 'records')
    (case / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
    input_path = case / 'input.patch'
    if task.get('seed') and 'input' in task['seed']:
        input_path.write_bytes((HERE / task['seed']['input']).read_bytes())
    prompt = task['prompt'].replace('{INPUT_PATH}', str(input_path)).replace(
        '{SCRATCH_DIR}', str(case / 'scratch')).replace('{OUTPUT_PATH}', str(case / 'review.json'))
    if args.explicit_skill:
        prompt += '\n\nUse $agents-collab for this task.'
    env = os.environ.copy()
    # No credential values are logged or copied; existing CLI login is retained.
    for key in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
                'CARGO_REGISTRY_TOKEN', 'CARGO_REGISTRIES_CRATES_IO_TOKEN']:
        if env.get(key):
            raise ValueError('credential override present: ' + key)
    env.update(PATH=str(args.toolchain.resolve()) + os.pathsep + env['PATH'],
               RUSTC=str(args.toolchain.resolve() / 'rustc'),
               RUSTDOC=str(args.toolchain.resolve() / 'rustdoc'),
               CARGO_HOME=str(args.cache.resolve()), CARGO_TARGET_DIR=str(case / 'target'),
               CARGO_NET_OFFLINE='true', PROCLEASE_TEST_ROOT=str(fixtures),
               PROCLEASE_HOME=str(fixtures / 'state'), TMPDIR=str(case / 'tmp'))
    # Identical metadata for A/B. No route/category instruction is supplied.
    instruction = (
        'This is a disposable evaluation snapshot. Complete the ticket within its scope. '
        'Do not commit, push, publish, modify global settings, or edit another checkout. '
        'Temporary outputs belong in ' + str(case / 'scratch') + '. '
        'If a workflow needs external configuration, the supplied configuration file is ' +
        str(case / 'profile.json') + '. Do not read another user configuration profile. '
        'Build tools are available at ' + str(args.toolchain.resolve()) + '; use this cargo '
        'if your login shell cannot find it. Keep supplied CARGO_HOME, CARGO_TARGET_DIR, '
        'PROCLEASE_TEST_ROOT, PROCLEASE_HOME and TMPDIR in all tests and child assignments. '
        'Only case files, the supplied build cache, and test fixtures are writable. '
        'Do not inspect evaluation rubrics, harness source, other runs or their outputs. '
        'Use existing subscription-authenticated access only. If access or a tool is denied, '
        'report it without changing settings, adding API credentials or bypassing permissions.')
    config = {'model_reasoning_effort': 'high', 'approval_policy': 'never',
              'sandbox_mode': 'workspace-write', 'features.memories': False,
              'features.multi_agent': True, 'web_search': 'disabled',
              'sandbox_workspace_write.network_access': True,
              'sandbox_workspace_write.writable_roots': [str(case), str(fixtures), str(args.cache.resolve())],
              'skills.config': [{'name': 'agents-collab', 'enabled': args.condition == 'B'}]}
    argv = ['codex', 'app-server', '--stdio', '--disable', 'apps', '--disable', 'hooks']
    for key, value in config.items():
        # JSON values are accepted TOML scalars/inline arrays for these fields.
        if key == 'skills.config':
            value = '[{name="agents-collab",enabled=' + ('true' if args.condition == 'B' else 'false') + '}]'
        else:
            value = json.dumps(value)
        argv += ['-c', key + '=' + value]
    started = time.monotonic()
    deadline = started + args.minutes * 60
    state = {'run_id': args.run_id, 'task': args.task, 'condition': args.condition,
             'phase': 'explicit-skill-diagnostic' if args.explicit_skill else args.phase,
             'status': 'launching', 'start': dt.datetime.now(dt.timezone.utc).isoformat(),
             'deadline_seconds': args.minutes * 60, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
             'package_sha256': {str(p.relative_to(HERE)): sha(p) for p in HERE.rglob('*') if p.is_file()
                                and '__pycache__' not in p.parts},
             'usage': {'lead': 'unknown', 'children': 'unknown'}, 'interventions': 0,
             'initial_commit': initial_commit, 'initial_tree': initial_tree}
    state_path = case / 'state.json'
    state_path.write_text(json.dumps(state, indent=2) + '\n')
    rpc = None
    try:
        rpc = RPC(argv, env, case / 'stderr.txt', repo)
        state.update(pid=rpc.proc.pid, status='running')
        state_path.write_text(json.dumps(state, indent=2) + '\n')
        rpc.request('initialize', {'clientInfo': {'name': 'agents_collab_public_eval', 'version': '1'},
                                  'capabilities': {'experimentalApi': True}}, min(deadline, time.monotonic()+30))
        rpc.send({'method': 'initialized', 'params': {}})
        skill_state = rpc.request('skills/list', {'cwds': [str(repo)], 'forceReload': True},
                                  min(deadline, time.monotonic()+30))
        (case / 'skill-state.json').write_text(json.dumps(skill_state, indent=2) + '\n')
        root = rpc.request('thread/start', {'cwd': str(repo), 'model': 'gpt-6.1-sol',
                           'ephemeral': True, 'approvalPolicy': 'never', 'sandbox': 'workspace-write',
                           'config': {'model_reasoning_effort': 'high'},
                           'developerInstructions': instruction}, min(deadline, time.monotonic()+30))
        tid = root['thread']['id']
        state['lead_accepted'] = {k: root.get(k) for k in ['model', 'reasoningEffort', 'approvalPolicy', 'sandbox']}
        rpc.request('turn/start', {'threadId': tid, 'model': 'gpt-6.1-sol', 'effort': 'high',
                    'input': [{'type': 'text', 'text': prompt}]}, min(deadline, time.monotonic()+30))
        while True:
            obj = rpc.read(deadline)
            if obj.get('method') == 'turn/completed' and obj.get('params', {}).get('threadId') == tid:
                state['turn'] = obj['params']['turn']
                state['status'] = 'completed' if state['turn'].get('status') == 'completed' else 'turn_failed'
                break
        children = receipts(rpc.events)['native_dispatches']
        metadata = []
        for child in children:
            try:
                result = rpc.request('thread/read', {'threadId': child['thread_id'], 'includeTurns': False},
                                     min(deadline, time.monotonic()+5))
                th = result['thread']
                metadata.append({k: th.get(k) for k in ['id','model','reasoningEffort','parentThreadId','forkedFromId','ephemeral']})
            except (RuntimeError, TimeoutError) as exc:
                metadata.append({'id': child['thread_id'], 'metadata_unavailable': str(exc)})
        (case / 'child-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    except TimeoutError as exc:
        state.update(status='timeout', error=str(exc))
    except Exception as exc:
        state.update(status='harness_error', error=str(exc))
    finally:
        if rpc:
            state['cleanup'] = rpc.close()
            (case / 'events.private.json').write_text(json.dumps(rpc.events) + '\n')
            (case / 'receipts.private.json').write_text(json.dumps(receipts(rpc.events), indent=2) + '\n')
        state['wall_clock_s'] = round(time.monotonic()-started, 3)
        state.setdefault('cleanup', {'owned_process_group':'not_launched', 'external_provider_workers':'unverified'})
        state_path.write_text(json.dumps(state, indent=2) + '\n')
        try:
            final_head = command(['git','rev-parse','HEAD'],repo).stdout.decode().strip()
            state['final_head'] = final_head
            state['history_changed'] = final_head != initial_commit
            (case / 'final.diff').write_bytes(command(['git','diff','--binary',initial_commit], repo).stdout)
            (case / 'git-status.txt').write_bytes(command(['git','status','--short'], repo).stdout)
            untracked = command(['git','ls-files','--others','--exclude-standard','-z'],repo).stdout
            entries = []
            for raw in untracked.split(b'\0'):
                if not raw:
                    continue
                name = os.fsdecode(raw)
                source = repo / name
                entry = {'path':name}
                if source.is_symlink():
                    entry['symlink'] = os.readlink(source)
                elif source.is_file():
                    dest = case / 'untracked.private' / name
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(source.read_bytes())
                    entry['sha256'] = sha(dest)
                else:
                    entry['non_regular_not_copied'] = True
                entries.append(entry)
            (case / 'untracked-manifest.private.json').write_text(json.dumps(entries,indent=2)+'\n')
        except (OSError,subprocess.CalledProcessError) as exc:
            state['final_evidence_error'] = str(exc)
        state_path.write_text(json.dumps(state, indent=2) + '\n')
    print(json.dumps({k: state[k] for k in ['run_id','status','wall_clock_s']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--fixture-root', type=Path, required=True,
                        help='Short path: Unix domain sockets have a platform path limit')
    parser.add_argument('--task', choices=['R1','R2','S1','S2','C1','C2'], required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--condition', choices=['A','B'], required=True)
    parser.add_argument('--phase', choices=['gate','study'], default='gate')
    parser.add_argument('--explicit-skill', action='store_true')
    parser.add_argument('--minutes', type=float, default=60)
    args = parser.parse_args()
    if not args.run_id.replace('-', '').isalnum() or args.minutes <= 0:
        parser.error('run-id must be alphanumeric with hyphens; minutes must be positive')
    run(args)
