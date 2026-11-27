"""Native message rendering; synthetic inputs only, never model dispatch."""
import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / 'skills/agents-collab/scripts'
sys.path.insert(0, str(SCRIPTS))
import backend


def inventory(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class NativeDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve();objects = self.root / 'objects';objects.mkdir()
        def store(value):
            raw = backend.encoded(value) if isinstance(value, dict) else value
            key = backend.safe.digest(raw);(objects / key).write_bytes(raw);return key
        self.store = store
        source = store('original µ frozen source\n'.encode())
        self.artifact = store({'entries':[{'path':'source.txt','kind':'file','object':source}]})
        self.packet = {'purpose':'review','artifact':self.artifact,'instructions':'Neutral review'}
        self.packet_id = store({'packet':self.packet})
        self.state = {'state':'active','current_artifact':self.artifact,
                      'packets':[{'id':self.packet_id,'spec':self.packet}],
                      'assignments':[{'spec':{'id':'review-1','packet':self.packet_id,'role':'reviewer',
                                            'output_destination':str(self.root / 'result.json')},
                                      'state':'launching','observations':[{'receipt':{'invocation':None}}],
                                      'requested':{'transport':'codex-native','model':'synthetic','reasoning':'medium'}}]}
        self.engine = backend.Backend.__new__(backend.Backend);self.engine.record = self.root
        self.engine.host = self.root
        self.engine.call = mock.Mock(return_value={'integrity':'verified'})
        self.args = argparse.Namespace(assignment='review-1')

    def test_message_has_registered_identities_immutable_context_and_utf8_digest(self):
        before = inventory(self.root)
        result = backend.native_dispatch(self.engine,self.args,self.state)
        for text in ('Assignment: review-1','Packet-SHA256: '+self.packet_id,
                     'Artifact-SHA256: '+self.artifact,'original µ frozen source'):
            self.assertIn(text,result['message'])
        self.assertEqual(result['message_sha256'],hashlib.sha256(result['message'].encode()).hexdigest())
        self.assertIs(result['writes'],False);self.assertEqual(result['dispatch'],'none')
        self.assertEqual(before,inventory(self.root))
        self.assertNotIn('effort_resolution', result)

    def test_auto_resolves_from_exact_scope_and_frozen_source(self):
        self.state['spec'] = {'editable_scope': ['source.txt']}
        requested = self.state['assignments'][0]['requested']
        requested['reasoning'] = 'auto'
        for transport in ('codex-native', 'claude-cli'):
            requested['transport'] = transport
            result = backend.render_dispatch(self.engine, self.args, self.state, transport)
            self.assertEqual(result['requested']['reasoning'], 'auto')
            self.assertEqual(result['effort_resolution']['resolved'], 'medium')
        self.state['spec']['editable_scope'] = []
        self.assertEqual(backend.render_dispatch(self.engine, self.args, self.state, 'claude-cli')
                         ['effort_resolution']['resolved'], 'high')

        manifest = backend.safe.strict_json(self.engine.frozen(self.artifact))
        manifest['entries'].append(dict(manifest['entries'][0], path='support.txt'))
        self.artifact = self.store(manifest)
        self.packet = dict(self.packet, artifact=self.artifact)
        self.packet_id = self.store({'packet': self.packet})
        self.state.update(current_artifact=self.artifact,
                          packets=[{'id': self.packet_id, 'spec': self.packet}])
        self.state['assignments'][0]['spec']['packet'] = self.packet_id
        self.state['spec']['editable_scope'] = ['source.txt']
        result = backend.render_dispatch(self.engine, self.args, self.state, 'claude-cli')
        self.assertEqual(result['effort_resolution']['resolved'], 'high')

    def test_wrong_or_uncertain_assignment_states_refuse(self):
        changes = [lambda s:s.update(state='completed'),lambda s:s.update(assignments=[]),
                   lambda s:s['assignments'].append(copy.deepcopy(s['assignments'][0])),
                   lambda s:s['assignments'][0].update(state='running'),
                   lambda s:s['assignments'][0]['observations'].append({'receipt':{'invocation':'already-started'}}),
                   lambda s:s['assignments'][0].update(continuation={'partial_work':'required'}),
                   lambda s:s['assignments'][0]['requested'].update(transport='claude-cli'),
                   lambda s:s.update(current_artifact='0'*64),
                   lambda s:s['packets'][0]['spec'].update(purpose='writer_context'),
                   lambda s:s['packets'][0]['spec'].update(instructions='mutable altered packet')]
        for change in changes:
            state = copy.deepcopy(self.state);change(state);before = inventory(self.root)
            with self.subTest(change=change),self.assertRaises(ValueError):
                backend.native_dispatch(self.engine,self.args,state)
            self.assertEqual(before,inventory(self.root))

    def test_dispatch_and_replacement_refuse_an_output_created_after_assignment(self):
        destination = self.root / 'result.json'
        destination.write_text('unreconciled output')
        before = inventory(self.root)
        with self.assertRaisesRegex(ValueError, 'registered output destination already exists'):
            backend.native_dispatch(self.engine, self.args, self.state)
        assignment = self.state['assignments'][0]
        assignment['requested']['transport'] = 'claude-cli'
        with self.assertRaisesRegex(ValueError, 'registered output destination already exists'):
            backend.render_dispatch(self.engine, self.args, self.state, 'claude-cli')
        assignment['continuation'] = {'partial_work': 'required'}
        with self.assertRaisesRegex(ValueError, 'registered output destination already exists'):
            backend.check_replacement_output(self.engine, self.args, self.state)
        self.assertEqual(before, inventory(self.root))

    def test_corrupt_object_or_failed_integrity_never_yields_message(self):
        self.engine.call.return_value = {'integrity':'failed'}
        with self.assertRaises(ValueError):backend.native_dispatch(self.engine,self.args,self.state)
        self.engine.call.return_value = {'integrity':'verified'}
        (self.root / 'objects' / self.packet_id).write_text('corrupt')
        with self.assertRaisesRegex(ValueError,'immutable object hash'):
            backend.native_dispatch(self.engine,self.args,self.state)

    def test_manual_mode_refuses_without_record_or_trace_writes(self):
        before=inventory(self.root);out=io.StringIO();err=io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code=backend.main(['--config',str(self.root/'absent.json'),'native-dispatch',
                               '--record',str(self.root/'absent-record'),'--assignment','review-1'])
        self.assertEqual(code,1);self.assertEqual(out.getvalue(),'')
        self.assertEqual(json.loads(err.getvalue())['fallback'],'none')
        self.assertEqual(before,inventory(self.root))


@unittest.skipUnless(os.environ.get('AGENTS_COLLAB_TEST_BINARY'),'set explicit real CLI for offline engine tests')
class NativeDispatchEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.repo=self.root/'repo';self.repo.mkdir()
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        (self.repo/'source.txt').write_text('immutable original source\n')
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','base'],check=True)
        (self.root/'records').mkdir();self.config=self.root/'backend.json';self.profile=self.root/'profile.json'
        self.config.write_text(json.dumps({'version':1,'mode':'cli','binary':str(Path(os.environ['AGENTS_COLLAB_TEST_BINARY']).resolve())}))
        p=json.loads((SCRIPTS.parent/'examples/profile.example.json').read_text());p['records_root']=str(self.root/'records')
        p['agents'].update({name:{'model':'synthetic-native','transport':'codex-native','reasoning':'medium'} for name in ['writer','reviewer']})
        p['review']['candidates']=['reviewer'];self.profile.write_text(json.dumps(p))

    def invoke(self,*args):
        out=io.StringIO();err=io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code=backend.main(['--config',str(self.config),'--profile',str(self.profile),*args])
        return code,out.getvalue(),err.getvalue()

    def prepared(self, role, *, task=None, scope=('source.txt',), lead_effort=None):
        scope_args = [arg for path in scope for arg in ('--scope', path)]
        path_args = [arg for path in scope for arg in ('--paths', path)]
        code,out,err=self.invoke('start','--repository',str(self.repo),'--project','fixture','--task',task or role,
            '--writer','writer','--reviewer','reviewer',*scope_args,'--requirement','R1=Scope',
            '--criterion','C1=Check','--boundary','No model invocation','--check','offline')
        self.assertEqual(code,0,err);task=json.loads(out);record=task['record'];host=Path(task['host'])
        instructions=host/'instructions.txt';instructions.write_text('Read frozen source. No model is called by this test.');output=host/'context.txt'
        code,out,err=self.invoke('context','--record',record,'--purpose','review' if role=='reviewer' else 'writer_context',
            *path_args,'--quiescence','Synthetic fixture','--instructions',str(instructions),'--output',str(output))
        self.assertEqual(code,0,err);context=json.loads(out)
        options = ('assignment', '--record', record, '--id', 'job-1', '--packet', context['packet'],
                   '--agent', role, '--role', role, '--output-destination', str(host / 'result.json'))
        if lead_effort is not None:
            code, _, err = self.invoke(*options)
            self.assertEqual(code, 1)
            self.assertIn('active lead', err)
            shown = self.invoke('show', '--record', record)
            self.assertEqual(json.loads(shown[1])['record']['assignments'], [])
            options += ('--lead-effort', lead_effort)
        code, out, err = self.invoke(*options)
        self.assertEqual(code,0,err)
        return record,context,output,json.loads(out)

    def test_real_writer_and_reviewer_messages_ignore_mutable_context_without_writes(self):
        for role in ['writer','reviewer']:
            record,context,path,_=self.prepared(role);path.write_text('wrong mutable context file')
            before=inventory(self.root)
            code,out,err=self.invoke('native-dispatch','--record',record,'--assignment','job-1')
            with self.subTest(role=role):
                self.assertEqual(code,0,err);result=json.loads(out)
                self.assertEqual((result['packet'],result['artifact']),(context['packet'],context['artifact']))
                self.assertIn('immutable original source',result['message'])
                self.assertNotIn('wrong mutable context file',result['message'])
                self.assertIn(context['packet'],result['message']);self.assertIn(context['artifact'],result['message'])
                self.assertNotIn('workflow',result);self.assertEqual(before,inventory(self.root))

    def test_real_auto_intent_records_medium_and_requires_matching_interface_receipt(self):
        profile = json.loads(self.profile.read_text())
        profile['agents']['reviewer']['reasoning'] = 'auto'
        self.profile.write_text(json.dumps(profile))
        record, _, output, _ = self.prepared('reviewer')
        workflows = [json.loads(path.read_text()) for path in output.parent.glob('workflow-*.json')]
        assignment, = [entry for entry in workflows if entry['command'] == 'assignment']
        self.assertEqual(assignment['effort_resolution']['resolved'], 'medium')
        options = ('observe', '--record', record, '--assignment', 'job-1', '--state', 'completed',
                   '--invocation', 'synthetic-session', '--interface-model', 'synthetic-native',
                   '--boundary-observations', 'Offline fixture')
        code, _, err = self.invoke(*options, '--interface-effort', 'high')
        self.assertEqual(code, 1)
        self.assertIn('auto reasoning resolved to medium', err)
        code, out, err = self.invoke('native-dispatch', '--record', record, '--assignment', 'job-1')
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)['effort_resolution'], assignment['effort_resolution'])
        code, _, err = self.invoke(*options, '--interface-effort', 'medium')
        self.assertEqual(code, 0, err)

    def test_auto_writer_resolves_effort_and_requires_matching_receipt(self):
        profile = json.loads(self.profile.read_text())
        profile['agents']['reviewer']['reasoning'] = 'auto'
        cases = [
            ('claude-cli', 'medium', ('source.txt',)),
            ('codex-native', 'high', ('source.txt', 'notes.txt')),
        ]
        for transport, expected, scope in cases:
            with self.subTest(transport=transport, expected=expected):
                for path in scope[1:]:
                    (self.repo / path).write_text('Additional source in the wide case.\n')
                writer = profile['agents']['writer']
                writer.update(transport=transport, reasoning='auto', model='synthetic-writer')
                self.profile.write_text(json.dumps(profile))
                record, _, _, assignment = self.prepared('writer', task=f'writer-{transport}', scope=scope)
                effort = assignment['effort_resolution']
                self.assertEqual((effort['requested'], effort['resolved']), ('auto', expected))
                if transport == 'codex-native':
                    code, out, err = self.invoke('native-dispatch', '--record', record, '--assignment', 'job-1')
                    self.assertEqual(code, 0, err)
                    self.assertEqual(json.loads(out)['effort_resolution'], effort)
                options = ('observe', '--record', record, '--assignment', 'job-1', '--state', 'completed',
                           '--invocation', 'synthetic-writer', '--interface-model', writer['model'],
                           '--boundary-observations', 'Offline fixture')
                for incorrect in ('low', 'xhigh', 'ultra'):
                    code, _, err = self.invoke(*options, '--interface-effort', incorrect)
                    self.assertEqual(code, 1)
                    self.assertIn(f'auto reasoning resolved to {expected}', err)
                code, _, err = self.invoke(*options, '--interface-effort', expected)
                self.assertEqual(code, 0, err)

    def test_inherit_copies_the_captured_lead_effort_through_both_dispatchers(self):
        profile = json.loads(self.profile.read_text())
        worker = profile['agents']['reviewer']
        for transport, dispatch in [('codex-native', 'native-dispatch'), ('claude-cli', 'claude-dispatch')]:
            with self.subTest(transport=transport):
                worker.update(transport=transport, reasoning='inherit')
                self.profile.write_text(json.dumps(profile))
                record, _, _, assignment = self.prepared('reviewer', task=transport, lead_effort='xhigh')
                code, out, err = self.invoke(dispatch, '--record', record, '--assignment', 'job-1')
                self.assertEqual(code, 0, err)
                resolution = json.loads(out)['effort_resolution']
                self.assertEqual(resolution, assignment['effort_resolution'])
                self.assertEqual((resolution['requested'], resolution['resolved']), ('inherit', 'xhigh'))
                receipt = ('observe', '--record', record, '--assignment', 'job-1', '--state', 'completed',
                           '--invocation', 'synthetic-session', '--interface-model', worker['model'],
                           '--boundary-observations', 'Offline fixture')
                code, _, err = self.invoke(*receipt, '--interface-effort', 'high')
                self.assertEqual(code, 1)
                self.assertIn('inherit reasoning resolved to xhigh', err)
                code, _, err = self.invoke(*receipt, '--interface-effort', 'xhigh')
                self.assertEqual(code, 0, err)

    def test_real_started_assignment_cannot_be_rendered_for_redispatch(self):
        record,_,_,_=self.prepared('reviewer')
        code,out,err=self.invoke('observe','--record',record,'--assignment','job-1','--state','running',
            '--invocation','synthetic-started','--boundary-observations','Synthetic receipt; no worker actually launched')
        self.assertEqual(code,0,err);before=inventory(self.root)
        code,out,err=self.invoke('native-dispatch','--record',record,'--assignment','job-1')
        self.assertEqual((code,out),(1,''));self.assertEqual(json.loads(err)['fallback'],'none')
        self.assertEqual(before,inventory(self.root))


if __name__=='__main__':unittest.main()
