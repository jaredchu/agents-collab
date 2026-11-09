#!/usr/bin/env python3
"""Offline structural/receipt checks; no provider or participant calls."""
import importlib.util
import json
from pathlib import Path
import re
import os
import sys
import tempfile
import subprocess
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('eval_run',HERE/'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Materials(unittest.TestCase):
    def test_seed_identity(self):
        manifest = json.loads((HERE/'seeds/manifest.json').read_text())
        for seed in manifest['files']:
            self.assertEqual(seed['sha256'], runner.sha(HERE/seed['path']))

    def test_prompt_separation_and_schedule(self):
        tasks = json.loads((HERE/'tasks.json').read_text())['tasks']
        for task in tasks:
            self.assertFalse(re.search(r'agents-collab|astra|fable|opus|reviewer|collaborat',task['prompt'],re.I))
        schedule = json.loads((HERE/'schedule.json').read_text())['runs']
        self.assertEqual(len(schedule),36)
        self.assertEqual(len({x['run_id'] for x in schedule}),36)
        self.assertEqual(sum(x['condition']=='A' and x['order_in_pair']==1 for x in schedule),9)
        for task in tasks:
            for rep in range(1,4):
                self.assertEqual({x['condition'] for x in schedule if x['task']==task['id'] and x['repetition']==rep},{'A','B'})

    def test_observed_dispatch_not_wait(self):
        def event(item):return {'method':'item/completed','params':{'item':item}}
        events=[event({'type':'collabAgentToolCall','tool':'wait','model':None}),
                event({'type':'subAgentActivity','kind':'started','agentThreadId':'unique','model':'gpt-6-astra','reasoningEffort':'high'}),
                event({'type':'subAgentActivity','kind':'started','agentThreadId':'unique','model':'gpt-6-astra','reasoningEffort':'high'}),
                event({'type':'agentMessage','text':'I delegated to a model'})]
        r=runner.receipts(events)
        self.assertEqual(len(r['native_dispatches']),1)
        self.assertEqual(r['native_dispatches'][0]['fresh_history'],'unknown')
        self.assertEqual(r['skill_read_candidates'],[])

    def test_skill_read_needs_output(self):
        events=[{'method':'item/completed','params':{'item':{'type':'commandExecution',
                'command':'cat /example/agents-collab/SKILL.md','exitCode':0,
                'aggregatedOutput':'# Agents Collab\n## Load and resolve'}}}]
        self.assertTrue(runner.receipts(events)['skill_read_candidates'][0]['content_observed'])

    def test_relative_and_absolute_symlink_fixture(self):
        spec=importlib.util.spec_from_file_location('eval_fixtures',HERE/'fixtures.py')
        fixtures=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixtures)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            for safe in [True,False]:
                binary=root/('safe' if safe else 'unsafe')
                binary.write_text('#!'+sys.executable+'\n'+
                    'import os,sys,json\nfrom pathlib import Path\n'+
                    'p=Path(os.environ["PROCLEASE_HOME"])/sys.argv[-1]/"output.log"\n'+
                    ('if p.is_symlink(): print("refused");sys.exit(1)\n' if safe else '')+
                    'text=p.read_text()\nprint(json.dumps({"lines":text.splitlines()}))\n')
                binary.chmod(0o700)
                for relative in [True,False]:
                    dest=root/(binary.name+str(relative))
                    supplied=Path(os.path.relpath(dest)) if relative else dest
                    result=fixtures.evaluate(binary,supplied,'C1')
                    self.assertEqual(result['symlink_refused_json'],safe)
                    self.assertEqual(result['symlink_refused_human'],safe)
                    self.assertTrue(result['regular_log'])

    @unittest.skipUnless(hasattr(os,'fork'),'POSIX process-group check')
    def test_cleanup_checks_child_after_parent_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            script=Path(tmp)/'parent.py'
            script.write_text('import os,signal,time,json\n'+
                'r,w=os.pipe()\npid=os.fork()\n'+
                'if pid==0:\n os.close(r)\n signal.signal(signal.SIGTERM,signal.SIG_IGN)\n os.write(w,b"ready")\n time.sleep(30)\n os._exit(0)\n'+
                'os.close(w)\nos.read(r,5)\n'+
                'print(json.dumps({"child":pid}),flush=True)\ntime.sleep(30)\n')
            rpc=runner.RPC([sys.executable,str(script)],os.environ.copy(),Path(tmp)/'stderr',Path(tmp))
            child=rpc.read(time.monotonic()+5)['child']
            result=rpc.close()
            state=subprocess.run(['ps','-o','stat=','-p',str(child)],capture_output=True,text=True).stdout.strip()
            self.assertTrue(not state or state.startswith('Z'),state)
            self.assertIn(result['owned_process_group'],['absent','still_present','unknown'])

    def test_committed_and_untracked_changes_remain_in_evidence(self):
        def git(repo,*args):return runner.command(['git',*args],repo)
        def snapshot(source,dest,task):
            dest.mkdir()
            (dest/'example.txt').write_text('initial\n')
            git(dest,'init','-q')
            git(dest,'add','.')
            git(dest,'-c','user.name=Evaluation','-c','user.email=evaluation@example.invalid','commit','-qm','initial')
        class FakeRPC:
            def __init__(self,argv,env,stderr,cwd):
                self.cwd=cwd;self.events=[];self.proc=SimpleNamespace(pid=0)
            def request(self,method,params,deadline):
                if method=='thread/start':return {'thread':{'id':'fake'},'model':'gpt-6.1-sol','reasoningEffort':'high'}
                if method=='turn/start':
                    (self.cwd/'example.txt').write_text('committed change\n')
                    git(self.cwd,'add','example.txt')
                    git(self.cwd,'-c','user.name=Evaluation','-c','user.email=evaluation@example.invalid','commit','-qm','unauthorized')
                    (self.cwd/'new.txt').write_text('untracked evidence\n')
                return {}
            def send(self,obj):pass
            def read(self,deadline):return {'method':'turn/completed','params':{'threadId':'fake','turn':{'status':'completed'}}}
            def close(self):return {'owned_process_group':'not_launched','external_provider_workers':'unverified'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            args=SimpleNamespace(work_root=root/'work',source=root,task='R1',run_id='dry',
                fixture_root=root/'fixtures',toolchain=root,cache=root,explicit_skill=False,
                condition='B',phase='gate',minutes=1)
            with patch.object(runner,'snapshot',snapshot),patch.object(runner,'RPC',FakeRPC):
                runner.run(args)
            case=root/'work/cases/dry'
            state=json.loads((case/'state.json').read_text())
            self.assertTrue(state['history_changed'])
            self.assertIn('+committed change',(case/'final.diff').read_text())
            self.assertEqual((case/'untracked.private/new.txt').read_text(),'untracked evidence\n')


if __name__=='__main__':unittest.main()
