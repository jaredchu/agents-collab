#!/usr/bin/env python3
"""Offline regression checks; no model calls, user profile edits or network."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('quality_run',HERE/'run.py');run=importlib.util.module_from_spec(spec);spec.loader.exec_module(run)


def snapshot(source,dest,task):
    dest.mkdir();(dest/'example.txt').write_text('initial\n\n')
    run.transport.command(['git','init','-q'],dest);run.transport.command(['git','add','.'],dest)
    run.transport.command(['git','-c','user.name=Evaluation','-c','user.email=evaluation@example.invalid','commit','-qm','initial'],dest)


class Harness(unittest.TestCase):
    def test_cli_draft_cleanup_preserves_patch_and_untracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();material=root/'source/evals/quality/date';material.mkdir(parents=True)
            (material/'profile.example.json').write_text('{}')
            import shutil
            shutil.copy2(HERE/'process_guard.py',material/'process_guard.py')
            bin=root/'bin';bin.mkdir();fake=bin/'claude'
            fake.write_text('#!/usr/bin/env python3\nimport sys,json,os\nfrom pathlib import Path\nsys.stdin.read()\nPath("example.txt").write_text("changed\\n\\n")\nPath("new.txt").write_text("untracked\\n")\nprint(json.dumps({"type":"result","is_error":False,"modelUsage":{"claude-opus-5-5":{}}}))\n');fake.chmod(0o700)
            args=argparse.Namespace(work_root=root/'private',source=root,toolchain=bin,cache=root/'cache',fixture_root=root/'fixtures',python=Path('/usr/bin/python3'),cleanup_binary=Path('/usr/bin/true'),stage='draft',task='Q1',arm=None,minutes=1)
            with patch.object(run,'HERE',material),patch.object(run,'task_data',lambda x:{'prompt':'synthetic task'}),patch.object(run.transport,'snapshot',snapshot),contextlib.redirect_stdout(io.StringIO()):run.main(args)
            case=root/'private/drafts/Q1-draft';state=json.loads((case/'state.json').read_text())
            self.assertEqual(state['status'],'completed')
            self.assertFalse(state['history_changed'])
            self.assertEqual(state['cleanup']['owned_process_group'],'absent')
            self.assertEqual((case/'untracked.private/new.txt').read_text(),'untracked\n')
            self.assertTrue((case/'final.patch').read_bytes().endswith(b' \n'))
            # The recorded patch must apply, including trailing blank context.
            target=root/'apply';snapshot(root,target,{})
            run.transport.command(['git','apply',str(case/'final.patch')],target)
            self.assertEqual((target/'example.txt').read_text(),'changed\n\n')

    def test_identical_draft_tree_reaches_three_branches(self):
        class FakeRPC:
            def __init__(self,argv,env,stderr,cwd,case):self.proc=argparse.Namespace(pid=0);self.events=[];self.argv=argv
            def request(self,method,params,deadline):
                return {'thread':{'id':'fake'},'model':'gpt-6.1-sol','reasoningEffort':'high'} if method=='thread/start' else {}
            def send(self,obj):pass
            def read(self,deadline):return {'method':'turn/completed','params':{'threadId':'fake','turn':{'status':'completed'}}}
            def close(self):return {'owned_process_group':'not_launched','external_provider_workers':'unverified'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();material=root/'source/evals/quality/date';material.mkdir(parents=True)
            (material/'profile.example.json').write_text('{}')
            import shutil
            shutil.copy2(HERE/'process_guard.py',material/'process_guard.py')
            draft=root/'private/drafts/Q1-draft';draft.mkdir(parents=True)
            base=root/'initial';snapshot(root,base,{})
            (base/'example.txt').write_text('common draft\n\n')
            (draft/'final.patch').write_bytes(run.transport.command(['git','diff'],base).stdout)
            (draft/'final-files.json').write_text('{}')
            (base/'new.txt').write_text('same new file\n')
            public_snapshot=run.git(base,'rev-parse','HEAD')
            run.transport.command(['git','add','.'],base)
            run.transport.command(['git','-c','user.name=Evaluation','-c','user.email=evaluation@example.invalid','commit','-qm','frozen common draft'],base)
            import shutil
            shutil.copytree(base,draft/'repo')
            (draft/'state.json').write_text(json.dumps({'frozen_draft_commit':run.git(base,'rev-parse','HEAD'),'public_snapshot_commit':public_snapshot}))
            trees=[];commits=[]
            for arm in 'ABC':
                args=argparse.Namespace(work_root=root/'private',source=root,toolchain=root,cache=root/'cache',fixture_root=root/'fixtures',python=Path('/usr/bin/python3'),cleanup_binary=Path('/usr/bin/true'),stage='finish',task='Q1',arm=arm,minutes=1)
                with patch.object(run,'HERE',material),patch.object(run,'task_data',lambda x:{'prompt':'synthetic task'}),patch.object(run.transport,'snapshot',snapshot),patch.object(run,'RPC',FakeRPC),contextlib.redirect_stdout(io.StringIO()):run.main(args)
                case=root/'private/runs'/('Q1-'+arm);state=json.loads((case/'state.json').read_text());trees.append(state['initial_tree']);commits.append(state['initial_commit'])
                self.assertEqual((case/'repo/example.txt').read_text(),'common draft\n\n')
                self.assertEqual((case/'repo/new.txt').read_text(),'same new file\n')
                self.assertEqual((case/'final.patch').read_bytes(),b'')
            self.assertEqual(len(set(trees)),1)
            self.assertEqual(len(set(commits)),1)

    def test_artifact_round_trip_modes_links_deletion(self):
        import shutil,tarfile
        from process_guard import restore_untracked,verify_restoration,manifest
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case=root/'case';case.mkdir();repo=case/'repo';snapshot(root,repo,{})
            (repo/'mode.sh').write_text('unchanged bytes\n');(repo/'mode.sh').chmod(0o755)
            run.transport.command(['git','add','.'],repo)
            run.transport.command(['git','-c','user.name=Evaluation','-c','user.email=evaluation@example.invalid','commit','-qm','base mode'],repo)
            initial=run.git(repo,'rev-parse','HEAD');before=manifest(repo)
            (repo/'mode.sh').chmod(0o644);(repo/'example.txt').unlink()
            (repo/'tests').mkdir();(repo/'tests/helper.sh').write_text('#!/bin/sh\nexit 0\n');(repo/'tests/helper.sh').chmod(0o755)
            (repo/'tests/helper-link').symlink_to('helper.sh')
            run.collect(case,initial);after=json.loads((case/'final-files.json').read_text())
            self.assertNotEqual(before['mode.sh'],after['mode.sh'])
            self.assertEqual(after['tests/helper.sh']['git_mode'],'100755')
            self.assertEqual((case/'untracked.private/tests/helper.sh').stat().st_mode&0o111,0o111)
            target=root/'restored';target.mkdir()
            archive=io.BytesIO(run.transport.command(['git','archive',initial],repo).stdout)
            with tarfile.open(fileobj=archive) as tar:tar.extractall(target,filter='data')
            run.transport.command(['git','apply',str(case/'final.patch')],target)
            restore_untracked(case,target)
            self.assertTrue(verify_restoration(case,target))
            self.assertFalse((target/'example.txt').exists())
            self.assertTrue((target/'tests/helper-link').is_symlink())
            self.assertEqual((target/'tests/helper.sh').stat().st_mode&0o111,0o111)

    @unittest.skipUnless(hasattr(os,'fork'),'POSIX process-group check')
    def test_timeout_stops_inherited_child(self):
        import sys,time
        from process_guard import run as supervised
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);script=root/'hang.py';pidfile=root/'child'
            script.write_text('import os,signal,time\n'+
                'r,w=os.pipe()\npid=os.fork()\n'+
                'if pid==0:\n os.close(r)\n signal.signal(signal.SIGTERM,signal.SIG_IGN)\n os.write(w,b"ready")\n time.sleep(30)\n os._exit(0)\n'+
                'os.close(w)\nos.read(r,5)\n'+
                'open('+repr(str(pidfile))+',"w").write(str(pid))\ntime.sleep(30)\n')
            r=supervised([sys.executable,str(script)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=.5)
            self.assertTrue(r['timed_out']);self.assertEqual(r['exit_code'],124)
            child=int(pidfile.read_text());state=subprocess.run(['ps','-o','stat=','-p',str(child)],capture_output=True,text=True).stdout.strip()
            self.assertTrue(not state or state.startswith('Z'),state)


if __name__=='__main__':unittest.main()
