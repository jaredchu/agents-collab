#!/usr/bin/env python3
"""Study-only quality pilot recorder; existing subscriptions, no global edits.

Python3.12+. Protocol/tasks/rubric and grader commitment must be publicly frozen
before calling draft or finish. Reuses the previously reviewed RPC transport.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
import shutil

from process_guard import manifest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('routing_transport',HERE.parents[1]/'automatic-routing/2026-11-09/run.py')
transport=importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
BASE=transport.BASE


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def git(repo,*args):
    return transport.command(['git',*args],repo).stdout.decode().strip()


def env_for(args,case):
    env=os.environ.copy()
    for key in ['OPENAI_API_KEY','ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','CARGO_REGISTRY_TOKEN','CARGO_REGISTRIES_CRATES_IO_TOKEN']:
        if env.get(key):raise ValueError('credential/provider override present: '+key)
    fixtures=args.fixture_root.resolve()/case.name
    fixtures.mkdir(parents=True,exist_ok=False,mode=0o700)
    env.update(PATH=str(args.toolchain.resolve())+os.pathsep+env['PATH'],RUSTC=str(args.toolchain.resolve()/'rustc'),RUSTDOC=str(args.toolchain.resolve()/'rustdoc'),CARGO_HOME=str(args.cache.resolve()),CARGO_TARGET_DIR=str(case/'target'),CARGO_NET_OFFLINE='true',PROCLEASE_TEST_ROOT=str(fixtures),PROCLEASE_HOME=str(fixtures/'s'),XDG_STATE_HOME=str(fixtures/'xdg'),TMPDIR=str(case/'tmp'))
    env['STUDY_CLEANUP_BINARY']=str(args.cleanup_binary.resolve())
    return env,fixtures


def check_helper(case,env):
    keys=['PATH','RUSTC','RUSTDOC','CARGO_HOME','CARGO_TARGET_DIR','CARGO_NET_OFFLINE','PROCLEASE_TEST_ROOT','PROCLEASE_HOME','XDG_STATE_HOME','TMPDIR','STUDY_CLEANUP_BINARY']
    write(case/'test-env.json',{k:env[k] for k in keys})
    code="""from pathlib import Path
import os,json,sys
from process_guard import run,cleanup_fixtures
p=Path(__file__).resolve().parent
e=os.environ.copy();e.update(json.loads((p/'test-env.json').read_text()))
commands=[['cargo','fmt','--check'],['cargo','clippy','--all-targets','--','-D','warnings'],['cargo','test']]
results=[]
for i,c in enumerate(commands):
 with (p/('check-'+str(i)+'.log')).open('w') as out:
  import subprocess
  r=run(c,cwd=p/'repo',env=e,stdout=out,stderr=subprocess.STDOUT,timeout=240)
 results.append({'command':c,'exit_code':r['exit_code'],'timed_out':r['timed_out'],'owned_process_group':r['owned_process_group']})
 if r['timed_out'] or r['owned_process_group']!='absent':break
cleanup=cleanup_fixtures(Path(e['PROCLEASE_TEST_ROOT']),Path(e['STUDY_CLEANUP_BINARY']))
(p/'fixture-cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\\n')
(p/'checks.json').write_text(json.dumps(results,indent=2)+'\\n')
print(json.dumps({'checks':results,'cleanup':cleanup}))
sys.exit(0 if len(results)==3 and all(x['exit_code']==0 and x['owned_process_group']=='absent' for x in results) and cleanup['observable_cleanup_complete'] else 1)
"""
    shutil.copy2(HERE/'process_guard.py',case/'process_guard.py')
    (case/'checks.py').write_text(code)


def collect(case,initial):
    repo=case/'repo';result={}
    try:
        result.update(final_head=git(repo,'rev-parse','HEAD'),initial_commit=initial,
                      history_changed=git(repo,'rev-parse','HEAD')!=initial)
        (case/'final.patch').write_bytes(transport.command(['git','diff','--binary',initial],repo).stdout)
        (case/'status.txt').write_text(git(repo,'status','--short')+'\n')
        entries=[]
        for name in git(repo,'ls-files','--others','--exclude-standard','-z').split('\0'):
            if not name:continue
            src=repo/name;entry={'path':name}
            if src.is_symlink():entry.update(symlink=os.readlink(src),git_mode='120000')
            elif src.is_file():
                dest=case/'untracked.private'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);entry['sha256']=transport.sha(dest);entry['git_mode']='100755' if src.stat().st_mode & 0o111 else '100644'
            else:entry['non_regular_not_copied']=True
            entries.append(entry)
        write(case/'untracked.json',entries)
        # Freeze a tracked final tree for anonymous grading, including ordinary
        # untracked files. Git metadata and ignored build artifacts are excluded.
        write(case/'final-files.json',manifest(repo))
    except (OSError,subprocess.CalledProcessError) as exc:result['evidence_error']=str(exc)
    return result


class RPC(transport.RPC):
    def __init__(self,*args,case,**kwargs):
        super().__init__(*args,**kwargs);self.case=case
        self.log=(case/'events.temporary.jsonl').open('w')
    def read(self,deadline):
        obj=super().read(deadline)
        method=obj.get('method','')
        if method and not method.startswith(('account/','mcpServer/')):
            self.log.write(json.dumps(obj)+'\n');self.log.flush()
        if method=='item/completed':
            item=obj.get('params',{}).get('item',{})
            if item.get('type')=='agentMessage':write(self.case/'progress.json',{'thread':obj['params'].get('threadId'),'text':item.get('text',''),'observed_at':dt.datetime.now(dt.timezone.utc).isoformat()})
        return obj
    def close(self):
        result=super().close();self.log.close();return result


def common_rules(case,args):
    return ('Only the disposable repository and case scratch are editable; no commits, pushes, publishing, global settings, other checkouts, profiles, grader materials or other runs. '
            'Do not inspect the public study package/rubric/hidden checks. Requirements are in the task. Preserve all existing project safeguards. '
            'No new dependencies. Keep source changes within the task allowlist. No API keys or spending fallback; existing subscription CLIs only. '
            'Only the assigned writer changes source; lead/reviewer source intent is read-only. Fresh reviewer contexts with no transcript inheritance. '
            'Temporary artifacts and collaboration records belong outside the repo in '+str(case/'scratch')+'. '
            'External benchmark profile, if needed: '+str(case/'profile.json')+'. Do not read another user profile. '
            'For reliable verification execute '+str(args.python.resolve())+' '+str(case/'checks.py')+'; it sets the exact disposable build/fixture environment. '
            'Do not edit checks.py, process_guard.py or test-env.json. Forward this helper and environment in every child assignment. '
            'CLI writer tools may include Read,Edit,Write,Glob,Grep and only the Bash command for this check helper plus read-only git status/diff/rev-parse. '
            'Use safe-mode, explicit model/effort, existing login, strict empty MCP, fresh invocation and no session persistence; never permission bypass. '
            'The finishing budget is40min including dispatch/checks, review target8min and revision target20min (advisory unless actually supervised). '
            'At most one review/check and one repair pass; no reviewer follow-up or repeated critique loop. Normal compile/test corrections within the repair pass are allowed. '
            'Review the existing frozen draft before revising. If a required route is unavailable, record the block; no model substitution or solo fallback. '
            'Record material findings with concrete failure scenario, evidence and severity, dispositions and final checks in '+str(case/'handoff.md')+'. '
            'If review finds no justified change, keep the draft and verify it. Never invent changes merely to demonstrate activity.')


def task_data(task_id):
    data=json.loads((HERE/'tasks.json').read_text())
    return next(t for t in data['tasks'] if t['id']==task_id)


def main(args):
    root=args.work_root.resolve()
    if root==Path.home() or root.is_relative_to(HERE.parents[2]):raise ValueError('private work root outside source required')
    task=task_data(args.task);ident=args.task+'-'+('draft' if args.stage=='draft' else args.arm)
    case=root/('drafts' if args.stage=='draft' else 'runs')/ident
    case.mkdir(parents=True,exist_ok=False,mode=0o700)
    for name in ['tmp','scratch','target']:(case/name).mkdir()
    if args.stage=='draft':
        transport.snapshot(args.source.resolve(),case/'repo',{'seed':None})
        public_snapshot=git(case/'repo','rev-parse','HEAD')
    else:
        draft=root/'drafts'/(args.task+'-draft')
        draft_state=json.loads((draft/'state.json').read_text())
        frozen=draft_state.get('frozen_draft_commit')
        if not frozen:raise ValueError('initial draft is not frozen')
        transport.command(['git','clone','--no-hardlinks','--quiet',str(draft/'repo'),str(case/'repo')],case)
        transport.command(['git','remote','remove','origin'],case/'repo')
        if git(case/'repo','rev-parse','HEAD')!=frozen:raise ValueError('draft identity drift')
        public_snapshot=draft_state['public_snapshot_commit']
    initial=git(case/'repo','rev-parse','HEAD')
    env,fixtures=env_for(args,case);check_helper(case,env)
    profile=json.loads((HERE/'profile.example.json').read_text());profile['records_root']=str(case/'scratch');write(case/'profile.json',profile)
    start=time.monotonic();deadline=start+args.minutes*60
    state={'id':ident,'task':args.task,'stage':args.stage,'arm':args.arm if args.stage=='finish' else None,'status':'launching','start':dt.datetime.now(dt.timezone.utc).isoformat(),'hard_seconds':args.minutes*60,'public_snapshot_commit':public_snapshot,'initial_commit':initial,'initial_tree':git(case/'repo','rev-parse','HEAD^{tree}'),'interventions':0}
    write(case/'state.json',state)
    rpc=None;process=None
    try:
        rules=common_rules(case,args)
        if args.stage=='draft':
            prompt=task['prompt']+'\n\nCreate the initial implementation and tests as a single writer. Complete ordinary verification using the supplied helper. No collaborators or other providers. Do not read any study or grader files.\n\n'+rules
            write(case/'request.json',{'model':'claude-opus-5-5','effort':'high','prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()})
            helper=str(args.python.resolve())+' '+str(case/'checks.py')
            cmd=['claude','-p','--safe-mode','--model','claude-opus-5-5','--effort','high','--tools','Read,Edit,Write,Glob,Grep,Bash','--permission-mode','acceptEdits','--permission-prompts','none','--allowedTools','Read','Edit','Write','Glob','Grep','Bash('+helper+')','Bash(git status:*)','Bash(git diff:*)','Bash(git rev-parse:*)','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--no-session-persistence','--output-format','json','--add-dir',str(case)]
            with (case/'provider-result.json').open('w') as out,(case/'stderr.txt').open('w') as err:
                process=subprocess.Popen(cmd,cwd=case/'repo',env=env,stdin=subprocess.PIPE,stdout=out,stderr=err,text=True,start_new_session=True)
                state.update(status='running',pid=process.pid,model_requested='claude-opus-5-5',effort_requested='high');write(case/'state.json',state)
                try:process.communicate(prompt,timeout=max(1,deadline-time.monotonic()));state.update(status='completed' if process.returncode==0 else 'provider_failure',exit_code=process.returncode)
                except subprocess.TimeoutExpired:state['status']='timeout'
                finally:
                    # Use the reviewed group cleanup even when parent already exited.
                    holder=object.__new__(transport.RPC);holder.proc=process;holder.proc.stdout=out;holder.selector=selectors.DefaultSelector();holder.err=err
                    state['cleanup']=holder.close()
        else:
            enabled=args.arm=='C';argv=['codex','app-server','--stdio','--disable','apps','--disable','hooks']
            config={'model_reasoning_effort':'high','approval_policy':'never','sandbox_mode':'workspace-write','features.memories':False,'features.multi_agent':True,'web_search':'disabled','sandbox_workspace_write.network_access':True,'sandbox_workspace_write.writable_roots':[str(case),str(fixtures),str(args.cache.resolve())]}
            for key,value in config.items():argv+=['-c',key+'='+json.dumps(value)]
            argv+=['-c','skills.config=[{name="agents-collab",enabled='+('true' if enabled else 'false')+'}]']
            rpc=RPC(argv,env,case/'stderr.txt',case/'repo',case=case);state.update(pid=rpc.proc.pid,status='running');write(case/'state.json',state)
            rpc.request('initialize',{'clientInfo':{'name':'agents_collab_quality_pilot','version':'1'},'capabilities':{'experimentalApi':True}},min(deadline,time.monotonic()+30));rpc.send({'method':'initialized','params':{}})
            response=rpc.request('thread/start',{'cwd':str(case/'repo'),'model':'gpt-6.1-sol','ephemeral':True,'approvalPolicy':'never','sandbox':'workspace-write','config':{'model_reasoning_effort':'high'},'developerInstructions':rules},min(deadline,time.monotonic()+30))
            tid=response['thread']['id'];state['lead_accepted']={k:response.get(k) for k in ['model','reasoningEffort','approvalPolicy','sandbox']};write(case/'state.json',state)
            prompt=task['prompt']+'\n\nAn initial draft is already present. Review it against the requirements, complete at most one repair pass if justified, then verify the final state. Preserve scope. '
            if args.arm=='A':prompt+='Use a fresh claude-opus-5-5 / high CLI writer to check its own model’s draft and make justified corrections in the same assignment (target28min). Do not dispatch a different reviewer or use agents-collab. You coordinate only; do not edit source yourself.'
            elif args.arm=='B':prompt+='Use one fresh no-history gpt-6-astra / high native reviewer for an independent read-only review of this frozen draft. Give the task, applicable project constraints and artifact identity. Then, only if justified changes are needed, use a fresh claude-opus-5-5 / high CLI writer to resolve findings and verify. You coordinate manually, without agents-collab, and do not edit source yourself.'
            else:prompt+='Use $agents-collab for this task. You coordinate only and do not edit source yourself. Obtain the configured independent review of the existing draft before dispatching any necessary revision writer.'
            (case/'task-prompt.txt').write_text(prompt)
            rpc.request('turn/start',{'threadId':tid,'model':'gpt-6.1-sol','effort':'high','input':[{'type':'text','text':prompt}]},min(deadline,time.monotonic()+30))
            while True:
                obj=rpc.read(deadline)
                if obj.get('method')=='turn/completed' and obj.get('params',{}).get('threadId')==tid:
                    turn=obj['params']['turn'];state.update(status='completed' if turn.get('status')=='completed' else 'turn_failed',turn_status=turn.get('status'));break
            extracted=transport.receipts(rpc.events);write(case/'receipts.temporary.json',extracted)
            metas=[]
            for child in extracted['native_dispatches']:
                try:
                    th=rpc.request('thread/read',{'threadId':child['thread_id'],'includeTurns':False},min(deadline,time.monotonic()+5))['thread'];metas.append({k:th.get(k) for k in ['id','model','reasoningEffort','forkedFromId','parentThreadId','ephemeral']})
                except (RuntimeError,TimeoutError) as exc:metas.append({'id':child['thread_id'],'error':str(exc)})
            write(case/'child-metadata.json',metas)
    except TimeoutError as exc:state.update(status='timeout',error=str(exc))
    except Exception as exc:state.update(status='harness_error',error=str(exc))
    finally:
        if rpc:state['cleanup']=rpc.close()
        state.update(collect(case,initial));state['wall_clock_s']=round(time.monotonic()-start,3);write(case/'state.json',state)
        if args.stage=='draft':
            try:
                # Operator capture, after participant evidence is recorded;
                # never a participant-authorized repository commit.
                transport.command(['git','add','.'],case/'repo')
                transport.command(['git','-c','core.hooksPath=/dev/null','-c','user.name=Evaluation','-c','user.email=evaluation@example.invalid','commit','--allow-empty','-qm','Frozen common initial draft'],case/'repo')
                state['frozen_draft_commit']=git(case/'repo','rev-parse','HEAD')
                state['frozen_draft_tree']=git(case/'repo','rev-parse','HEAD^{tree}')
            except (OSError,subprocess.CalledProcessError) as exc:state['draft_freeze_error']=str(exc)
            write(case/'state.json',state)
        # Initial/final changes relative to the public base are separate from
        # revision-only changes. The initial commit ID cannot hide participant commits.
        try:(case/'complete.patch').write_bytes(transport.command(['git','diff','--binary',public_snapshot],case/'repo').stdout)
        except (OSError,subprocess.CalledProcessError) as exc:state['complete_evidence_error']=str(exc);write(case/'state.json',state)
    print(json.dumps({k:state.get(k) for k in ['id','status','wall_clock_s']}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['work-root','source','toolchain','cache','fixture-root','python','cleanup-binary']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--stage',choices=['draft','finish'],required=True);p.add_argument('--task',required=True);p.add_argument('--arm',choices=['A','B','C']);p.add_argument('--minutes',type=float,required=True)
    args=p.parse_args()
    if args.stage=='finish' and not args.arm:p.error('--arm required for finishing')
    if not args.task.isalnum() or args.minutes<=0:p.error('safe task ID and positive minutes required')
    main(args)
