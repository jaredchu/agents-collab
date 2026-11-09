use serde_json::{Value, json};
use std::{
    fs,
    os::unix::fs::{PermissionsExt, symlink},
    path::{Path, PathBuf},
    process::{Command, Output},
    sync::{Arc, Barrier},
};
use tempfile::TempDir;
struct Fixture {
    _tmp: TempDir,
    repo: PathBuf,
    record: PathBuf,
    inputs: PathBuf,
    profile: PathBuf,
    rev: u64,
    seq: u64,
}
fn git(repo: &Path, args: &[&str]) {
    let o = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(args)
        .output()
        .unwrap();
    assert!(
        o.status.success(),
        "git {:?}: {}",
        args,
        String::from_utf8_lossy(&o.stderr)
    );
}
fn execute(
    command: &str,
    record: &Path,
    input: Option<&Path>,
    key: Option<&str>,
    expected: Option<u64>,
    profile: Option<&Path>,
    fault: Option<&str>,
) -> Output {
    let mut c = Command::new(env!("CARGO_BIN_EXE_agents-collab"));
    c.args(command.split(' '))
        .arg("--json")
        .arg("--record")
        .arg(record);
    if let Some(i) = input {
        c.arg("--input").arg(i);
    }
    if let Some(k) = key {
        c.args(["--key", k, "--actor", "owner"]);
    }
    if let Some(e) = expected {
        c.arg("--expect").arg(e.to_string());
    }
    if let Some(p) = profile {
        c.arg("--profile").arg(p);
    }
    if let Some(f) = fault {
        c.env("AGENTS_COLLAB_FAULT", f);
    }
    c.output().unwrap()
}
fn body(out: &Output) -> Value {
    serde_json::from_slice(&out.stdout).unwrap_or_else(|_| panic!("bad output: {:?}", out))
}
fn good(out: &Output) -> Value {
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stdout)
    );
    body(out)["data"].clone()
}
impl Fixture {
    fn new() -> Self {
        let tmp = tempfile::tempdir().unwrap();
        let base = tmp.path().canonicalize().unwrap();
        let repo = base.join("source");
        let inputs = base.join("inputs");
        let records = base.join("records");
        for d in [&repo, &inputs, &records] {
            fs::create_dir(d).unwrap();
        }
        git(&repo, &["init", "-q"]);
        git(&repo, &["config", "user.name", "Synthetic"]);
        git(
            &repo,
            &["config", "user.email", "synthetic@example.invalid"],
        );
        fs::write(repo.join("file.txt"), "original\n").unwrap();
        fs::write(repo.join("deleted.txt"), "old\n").unwrap();
        fs::write(repo.join(".gitignore"), "ignored.txt\n.env\n").unwrap();
        git(&repo, &["add", "."]);
        git(&repo, &["commit", "-qm", "fixture"]);
        let profile = inputs.join("profile.json");
        fs::write(&profile,serde_json::to_vec(&json!({"version":1,"name":"Synthetic profile label","agents":{"writer":{"model":"synthetic-writer","transport":"codex-native","reasoning":"inherit"},"alpha":{"model":"synthetic-a","transport":"codex-native","reasoning":"inherit"},"beta":{"model":"synthetic-b","transport":"codex-native","reasoning":"inherit"}},"routing":{"small_writer":"current-session","substantial_writer":"writer"},"review":{"on_consequential_work":"single","candidates":["alpha","beta"],"prefer_different_model":true,"recipes":{"pair":["alpha","beta"]},"max_followup_rounds":1},"effort_check":"supported-control","access":"existing-authorized-access","bounds":{"enforcement":"advisory","writer_minutes":30,"reviewer_minutes":10,"review_output_words":800},"records_root":records})).unwrap()).unwrap();
        Self {
            _tmp: tmp,
            repo,
            record: records.join("synthetic/task/collaboration"),
            inputs,
            profile,
            rev: 0,
            seq: 0,
        }
    }
    fn file(&mut self, v: Value) -> PathBuf {
        self.seq += 1;
        let p = self.inputs.join(format!("{}.json", self.seq));
        fs::write(&p, serde_json::to_vec(&v).unwrap()).unwrap();
        p
    }
    fn task(&self) -> Value {
        json!({"schema_version":1,"project":"synthetic","task":"task","repository":self.repo,"requirements":[{"id":"R1","kind":"requirement","text":"Preserve requested behavior verbatim.","source":"synthetic ticket"},{"id":"C1","kind":"criterion","text":"Offline checks pass.","source":"synthetic ticket"},{"id":"S1","kind":"safeguard","text":"No external calls or publication.","source":"synthetic policy"}],"authority_boundaries":["Owner approval is declarative evidence, not authentication."],"writer":"writer","editable_scope":["file.txt"],"reviewers":["alpha","beta"],"required_checks":["offline"],"required_approvals":["owner"],"decision_authorities":["owner"]})
    }
    fn create(&mut self) {
        let p = self.file(self.task());
        let v = good(&execute(
            "task create",
            &self.record,
            Some(&p),
            Some("create"),
            Some(0),
            Some(&self.profile),
            None,
        ));
        self.rev = v["revision"].as_u64().unwrap();
    }
    fn apply(&mut self, cmd: &str, v: Value) -> Value {
        let p = self.file(v);
        let key = format!("op{}", self.seq);
        let out = execute(
            cmd,
            &self.record,
            Some(&p),
            Some(&key),
            Some(self.rev),
            None,
            None,
        );
        let v = good(&out);
        self.rev = v["revision"].as_u64().unwrap();
        v["result"].clone()
    }
    fn reject(&mut self, cmd: &str, v: Value, contains: &str) {
        let p = self.file(v);
        let out = execute(
            cmd,
            &self.record,
            Some(&p),
            Some(&format!("reject{}", self.seq)),
            Some(self.rev),
            None,
            None,
        );
        assert!(!out.status.success());
        assert!(
            body(&out)["error"]["message"]
                .as_str()
                .unwrap()
                .contains(contains),
            "{}",
            body(&out)
        );
    }
    fn show(&self) -> Value {
        good(&execute(
            "task show",
            &self.record,
            None,
            None,
            None,
            None,
            None,
        ))["record"]
            .clone()
    }
    fn freeze(&mut self) -> String {
        self.apply("artifact freeze",json!({"paths":[".gitignore","deleted.txt","file.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"synthetic writer stopped","atomic_required":false,"base":"HEAD"}))["artifact"].as_str().unwrap().into()
    }
    fn packet_spec(&self, artifact: &str, round: u64) -> Value {
        json!({"artifact":artifact,"round":round,"instructions":"Inspect the frozen bytes against every requirement.","access_policy":"fresh host session; source read only; automatic context is reported, no sandbox claim","coverage":{"R1":[artifact],"C1":[artifact],"S1":[artifact]},"evidence":[{"category":"source_claim","description":"Synthetic artifact supplied by coordinator","object":artifact}],"neutral_initial":true})
    }
    fn packet(&mut self, artifact: &str, round: u64) -> String {
        self.apply("packet seal", self.packet_spec(artifact, round))["packet"]
            .as_str()
            .unwrap()
            .into()
    }
    fn prepare(&mut self, id: &str, agent: &str, packet: &str) {
        self.apply("assignment prepare",json!({"id":id,"packet":packet,"agent":agent,"role":"reviewer","editable_scope":[],"output_destination":format!("private-result-{id}")}));
    }
    fn receipt(&self, id: &str, state: &str) -> Value {
        json!({"schema_version":1,"assignment":id,"state":state,"invocation":if state=="launching"{Value::Null}else{json!(format!("host-session-{id}"))},"process_start":null,"interface_model":null,"interface_effort":null,"observed_model":null,"observed_effort":null,"boundary_observations":"Synthetic offline host; no model ran; isolation unknown.","exit_code":if state=="completed"{json!(0)}else{Value::Null},"reason":"synthetic host receipt","reconciled":true,"absence_established":false})
    }
    fn finish_invocation(&mut self, id: &str) {
        self.apply("assignment observe", self.receipt(id, "launching"));
        self.apply("assignment observe", self.receipt(id, "completed"));
    }
    fn review_spec(&self, id: &str, artifact: &str, packet: &str) -> Value {
        json!({"schema_version":1,"assignment":id,"artifact":artifact,"packet":packet,"verdict":"pass","verification":[{"category":"verified_observation","description":"Synthetic offline checks only; not real review evidence","object":artifact}],"limits":"No models, external services, authority or runtime effort attestation.","findings":[],"fresh_session":"synthetic separate receipt","automatic_context":"unknown; no real reviewer","tool_boundary":"synthetic only; filesystem isolation not claimed"})
    }
    fn review(&mut self, id: &str, artifact: &str, packet: &str) {
        let r = self.review_spec(id, artifact, packet);
        assert_eq!(
            self.apply("review import", r)["validation"],
            "valid_structure_only"
        );
    }
    fn complete(&mut self, a: &str) -> Value {
        self.apply("task complete",json!({"artifact":a,"criteria":{"C1":[a]},"checks":{"offline":[a]},"approvals":{"owner":[a]},"reason":"Synthetic complete workflow; evidence truth remains caller responsibility."}))
    }
}
#[test]
fn complete_two_reviewer_workflow_and_explicit_export() {
    let mut f = Fixture::new();
    f.create();
    f.apply(
        "task activate",
        json!({"reason":"authorized synthetic work"}),
    );
    let a = f.freeze();
    let p = f.packet(&a, 0);
    let input = f.file(json!({"packet":p}));
    let shown = good(&execute(
        "packet show",
        &f.record,
        Some(&input),
        None,
        None,
        None,
        None,
    ));
    assert_eq!(
        shown["sealed_packet"]["requirements"]
            .as_array()
            .unwrap()
            .len(),
        3
    );
    for (id, agent) in [("A", "alpha"), ("B", "beta")] {
        f.prepare(id, agent, &p);
        f.finish_invocation(id);
        f.review(id, &a, &p);
    }
    assert_eq!(f.complete(&a)["state"], "completed");
    let show = f.show();
    assert_eq!(show["reviews"].as_array().unwrap().len(), 2);
    assert_eq!(
        show["spec"]["requirements"][0]["text"],
        "Preserve requested behavior verbatim."
    );
    let input = f.file(json!({"fields":["state","revision","reviews"]}));
    let exported = good(&execute(
        "task export",
        &f.record,
        Some(&input),
        None,
        None,
        None,
        None,
    ));
    assert!(
        exported["selected_private_records"]
            .get("profile")
            .is_none()
    );
    assert_eq!(exported["selected_private_records"]["state"], "completed");
    f.reject("task activate", json!({"reason":"reset"}), "terminal");
}
#[test]
fn repair_waits_for_every_initial_reviewer_then_consumes_single_followup() {
    let mut f = Fixture::new();
    f.create();
    f.apply("task activate", json!({"reason":"start"}));
    let a = f.freeze();
    let p = f.packet(&a, 0);
    f.prepare("A", "alpha", &p);
    f.prepare("B", "beta", &p);
    f.finish_invocation("A");
    let mut r = f.review_spec("A", &a, &p);
    r["verdict"] = json!("changes_required");
    r["findings"] = json!([{"id":"F1","location":"R1/file.txt","scenario":"Synthetic regression","evidence":"Reasoning from supplied bytes","uncertainty":"known synthetic test case","material":true,"recommendation":"repair bytes"}]);
    f.apply("review import", r);
    let selection = json!({"paths":[".gitignore","deleted.txt","file.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"writer stopped","atomic_required":false,"base":"HEAD"});
    f.reject("artifact freeze", selection.clone(), "all required");
    f.finish_invocation("B");
    f.review("B", &a, &p);
    f.apply("finding resolve",json!({"finding":"F1","decision":"addressed","reason":"Writer repairs the regression","evidence":[a],"authority":"owner","criterion_compatible":true}));
    f.reject("task complete",json!({"artifact":a,"criteria":{"C1":[a]},"checks":{"offline":[a]},"approvals":{"owner":[a]},"reason":"premature"}),"completion blocked");
    fs::write(f.repo.join("file.txt"), "repaired\n").unwrap();
    let a2 = f.freeze();
    assert_ne!(a, a2);
    let p2 = f.packet(&a2, 1);
    for (id, agent) in [("A2", "alpha"), ("B2", "beta")] {
        f.prepare(id, agent, &p2);
        f.finish_invocation(id);
        f.review(id, &a2, &p2);
    }
    f.reject("artifact freeze", selection, "round cap");
    assert_eq!(f.complete(&a2)["state"], "completed");
}
#[test]
fn unknown_launch_is_not_duplicate_slot_and_blocked_access_recovers_without_clock_reset() {
    let mut f = Fixture::new();
    f.create();
    let a = f.freeze();
    let p = f.packet(&a, 0);
    f.prepare("A", "alpha", &p);
    f.apply("assignment observe", f.receipt("A", "launching"));
    let deadline = f.show()["assignments"][0]["deadline"].clone();
    f.apply(
        "task reconcile",
        json!({"reason":"host crashed before attach"}),
    );
    assert_eq!(f.show()["assignments"][0]["state"], "unknown");
    f.reject(
        "assignment observe",
        f.receipt("A", "launching"),
        "no retry",
    );
    let mut running = f.receipt("A", "running");
    running["reconciled"] = json!(false);
    f.reject("assignment observe", running, "requires explicit host");
    f.apply("assignment observe", f.receipt("A", "blocked"));
    f.apply(
        "task block",
        json!({"reason":"real access/quota interruption remains unfinished"}),
    );
    assert_eq!(f.show()["state"], "blocked");
    f.apply("assignment observe", f.receipt("A", "completed"));
    f.apply(
        "task activate",
        json!({"reason":"existing host reconciled after restored access; no redispatch"}),
    );
    f.review("A", &a, &p);
    assert_eq!(f.show()["assignments"][0]["deadline"], deadline);
    assert!(f.show()["reviews"].as_array().unwrap().len() == 1);
}
#[test]
fn malformed_forged_stale_and_incomplete_reviews_are_preserved_but_do_not_complete() {
    let mut f = Fixture::new();
    f.create();
    let a = f.freeze();
    let p = f.packet(&a, 0);
    f.prepare("A", "alpha", &p);
    let r = f.review_spec("A", &a, &p);
    let invalid = f.apply("review import", r.clone());
    assert_eq!(invalid["validation"], "rejected");
    f.finish_invocation("A");
    let mut forged = r.clone();
    forged["artifact"] = json!("f".repeat(64));
    assert_eq!(f.apply("review import", forged)["validation"], "rejected");
    let mut missing = r.clone();
    missing.as_object_mut().unwrap().remove("limits");
    assert_eq!(f.apply("review import", missing)["validation"], "rejected");
    let mut no_evidence = r.clone();
    no_evidence["verification"] = json!([]);
    assert_eq!(
        f.apply("review import", no_evidence)["validation"],
        "rejected"
    );
    let path = f.inputs.join("broken.json");
    fs::write(&path, b"{broken").unwrap();
    let v = good(&execute(
        "review import",
        &f.record,
        Some(&path),
        Some("malformed"),
        Some(f.rev),
        None,
        None,
    ));
    f.rev = v["revision"].as_u64().unwrap();
    assert_eq!(v["result"]["validation"], "rejected");
    let id = v["result"]["original"].as_str().unwrap();
    assert_eq!(
        fs::read(f.record.join("objects").join(id)).unwrap(),
        b"{broken"
    );
    assert_eq!(f.show()["reviews"].as_array().unwrap().len(), 0);
    f.review("A", &a, &p);
    assert_eq!(f.apply("review import", r)["validation"], "rejected");
    assert_eq!(f.show()["reviews"].as_array().unwrap().len(), 1);
}
#[test]
fn mixed_git_snapshot_preserves_index_modes_symlink_bytes_deletion_and_binary() {
    let mut f = Fixture::new();
    f.create();
    fs::write(f.repo.join("file.txt"), "staged\n").unwrap();
    git(&f.repo, &["add", "file.txt"]);
    fs::write(f.repo.join("file.txt"), b"working\0binary\xff").unwrap();
    fs::set_permissions(f.repo.join("file.txt"), fs::Permissions::from_mode(0o755)).unwrap();
    git(&f.repo, &["rm", "-q", "deleted.txt"]);
    symlink("../unavailable-external", f.repo.join("link")).unwrap();
    fs::write(f.repo.join("new.bin"), [0, 255, 1]).unwrap();
    fs::write(f.repo.join("ignored.txt"), "explicit ignored").unwrap();
    let v=f.apply("artifact freeze",json!({"paths":["file.txt","deleted.txt","link","new.bin","ignored.txt"],"omissions":{".gitignore":"Supporting exclusion rules irrelevant to review target"},"acknowledged_sensitive":[],"quiescence":"coordinated writer stop","atomic_required":false,"base":"HEAD"}));
    let id = v["artifact"].as_str().unwrap();
    let m: Value =
        serde_json::from_slice(&fs::read(f.record.join("objects").join(id)).unwrap()).unwrap();
    let entries = m["entries"].as_array().unwrap();
    let file = entries.iter().find(|x| x["path"] == "file.txt").unwrap();
    assert_eq!(file["mode"], 0o755);
    assert_ne!(file["object"], file["index_object"]);
    assert_eq!(
        fs::read(
            f.record
                .join("objects")
                .join(file["index_object"].as_str().unwrap())
        )
        .unwrap(),
        b"staged\n"
    );
    let link = entries.iter().find(|x| x["path"] == "link").unwrap();
    assert_eq!(link["kind"], "symlink");
    assert_eq!(
        fs::read(
            f.record
                .join("objects")
                .join(link["object"].as_str().unwrap())
        )
        .unwrap(),
        b"../unavailable-external"
    );
    let deleted = entries.iter().find(|x| x["path"] == "deleted.txt").unwrap();
    assert_eq!(
        fs::read(
            f.record
                .join("objects")
                .join(deleted["head_object"].as_str().unwrap())
        )
        .unwrap(),
        b"old\n"
    );
    assert_eq!(deleted["head_mode"], "100644");
    assert_eq!(deleted["base_object"], deleted["head_object"]);
    assert_eq!(
        entries.iter().find(|x| x["path"] == "deleted.txt").unwrap()["kind"],
        "deleted"
    );
    assert_eq!(
        entries.iter().find(|x| x["path"] == "ignored.txt").unwrap()["provenance"],
        "explicit-ignored"
    );
}
#[test]
fn selection_requires_omissions_rejects_traversal_sensitive_implicit_atomic_and_symlink_parent() {
    let mut f = Fixture::new();
    f.create();
    let mut s = json!({"paths":["file.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"writer stopped","atomic_required":false,"base":"HEAD"});
    f.reject("artifact freeze", s.clone(), "every tracked/untracked");
    s["paths"] = json!([".gitignore", "deleted.txt", "file.txt", "../outside"]);
    f.reject("artifact freeze", s.clone(), "path traversal");
    s["paths"] = json!([".gitignore", "deleted.txt", "file.txt", ".env"]);
    fs::write(f.repo.join(".env"), "synthetic").unwrap();
    f.reject("artifact freeze", s.clone(), "sensitive-looking");
    s["acknowledged_sensitive"] = json!([".env"]);
    s["atomic_required"] = json!(true);
    f.reject("artifact freeze", s.clone(), "atomic multi-file");
    s["atomic_required"] = json!(false);
    symlink(&f.inputs, f.repo.join("alias")).unwrap();
    s["paths"] = json!([".gitignore", "deleted.txt", "file.txt", "alias/child"]);
    s["omissions"] = json!({"alias":"not selected"});
    f.reject("artifact freeze", s, "symlink in");
}
#[test]
fn idempotency_conflicting_key_stale_revision_and_concurrent_mutations() {
    let mut f = Fixture::new();
    f.create();
    let p = f.file(json!({"reason":"start"}));
    let first = execute(
        "task activate",
        &f.record,
        Some(&p),
        Some("same"),
        Some(f.rev),
        None,
        None,
    );
    let first_v = good(&first);
    assert_eq!(
        first_v,
        good(&execute(
            "task activate",
            &f.record,
            Some(&p),
            Some("same"),
            Some(f.rev),
            None,
            None
        ))
    );
    assert!(
        !execute(
            "task block",
            &f.record,
            Some(&p),
            Some("same"),
            Some(f.rev),
            None,
            None
        )
        .status
        .success()
    );
    f.rev = first_v["revision"].as_u64().unwrap();
    assert!(
        !execute(
            "task block",
            &f.record,
            Some(&p),
            Some("stale"),
            Some(f.rev - 1),
            None,
            None
        )
        .status
        .success()
    );
    let barrier = Arc::new(Barrier::new(3));
    let mut handles = Vec::new();
    for i in 0..2 {
        let (barrier, p, root, rev) = (barrier.clone(), p.clone(), f.record.clone(), f.rev);
        handles.push(std::thread::spawn(move || {
            barrier.wait();
            execute(
                "task block",
                &root,
                Some(&p),
                Some(&format!("concurrent{i}")),
                Some(rev),
                None,
                None,
            )
        }));
    }
    barrier.wait();
    let results: Vec<_> = handles.into_iter().map(|h| h.join().unwrap()).collect();
    assert_eq!(results.iter().filter(|x| x.status.success()).count(), 1);
    assert_eq!(f.show()["revision"], f.rev + 1);
}
#[test]
fn fault_boundaries_never_commit_missing_objects_and_after_commit_retry_is_idempotent() {
    for fault in [
        "crash:object-written",
        "crash:object-synced",
        "crash:object-published",
        "crash:before-commit",
        "crash:after-commit",
        "no-space",
    ] {
        let mut f = Fixture::new();
        f.create();
        let p = f.file(json!({"reason":format!("start-{fault}")}));
        let out = execute(
            "task activate",
            &f.record,
            Some(&p),
            Some("fault-op"),
            Some(f.rev),
            None,
            Some(fault),
        );
        assert!(!out.status.success());
        let shown = f.show();
        assert_eq!(
            shown["state"],
            if fault == "crash:after-commit" {
                "active"
            } else {
                "prepared"
            }
        );
        let current = shown["revision"].as_u64().unwrap();
        if fault == "crash:after-commit" {
            assert_eq!(
                good(&execute(
                    "task activate",
                    &f.record,
                    Some(&p),
                    Some("fault-op"),
                    Some(f.rev),
                    None,
                    None
                ))["revision"],
                current
            );
        } else {
            f.rev = current;
            f.apply(
                "task reconcile",
                json!({"reason":"reconcile fault staging and leave unreferenced objects intact"}),
            );
            assert!(
                fs::read_dir(f.record.join("staging"))
                    .unwrap()
                    .next()
                    .is_none()
            );
            good(&execute(
                "task check",
                &f.record,
                None,
                None,
                None,
                None,
                None,
            ));
        }
    }
}
#[test]
fn corruption_missing_objects_unavailable_storage_and_repository_overlap_fail_closed() {
    let mut f = Fixture::new();
    f.create();
    let a = f.freeze();
    let object = f.record.join("objects").join(&a);
    let original = fs::read(&object).unwrap();
    fs::write(&object, "corrupt").unwrap();
    assert!(
        !execute("task check", &f.record, None, None, None, None, None)
            .status
            .success()
    );
    f.reject(
        "task activate",
        json!({"reason":"must not complete"}),
        "object hash mismatch",
    );
    fs::remove_file(&object).unwrap();
    assert!(
        !execute("task show", &f.record, None, None, None, None, None)
            .status
            .success()
    );
    fs::write(&object, original).unwrap();
    let moved = f.record.with_file_name("unmounted");
    fs::rename(&f.record, &moved).unwrap();
    assert!(
        !execute("task show", &f.record, None, None, None, None, None)
            .status
            .success()
    );
    assert!(!f.record.exists());
    for mode in ["missing", "inside", "other-repository", "symlink"] {
        let mut g = Fixture::new();
        let mut profile: Value = serde_json::from_slice(&fs::read(&g.profile).unwrap()).unwrap();
        let root = match mode {
            "missing" => g.inputs.join("missing-volume"),
            "inside" => g.repo.clone(),
            "other-repository" => {
                git(&g.inputs, &["init", "-q"]);
                g.inputs.clone()
            }
            _ => {
                let path = g.inputs.join("alias");
                symlink(&g.repo, &path).unwrap();
                path
            }
        };
        profile["records_root"] = json!(root);
        fs::write(&g.profile, serde_json::to_vec(&profile).unwrap()).unwrap();
        let p = g.file(g.task());
        let out = execute(
            "task create",
            &g.record,
            Some(&p),
            Some("create"),
            Some(0),
            Some(&g.profile),
            None,
        );
        assert!(!out.status.success(), "{mode}");
    }
}
#[test]
fn required_supervisor_and_runtime_attestation_are_honestly_blocked() {
    for field in ["timing", "effort"] {
        let mut f = Fixture::new();
        let mut p: Value = serde_json::from_slice(&fs::read(&f.profile).unwrap()).unwrap();
        if field == "timing" {
            p["bounds"]["enforcement"] = json!("required");
        } else {
            p["effort_check"] = json!("runtime-attestation");
        }
        fs::write(&f.profile, serde_json::to_vec(&p).unwrap()).unwrap();
        f.create();
        let a = f.freeze();
        let p = f.packet(&a, 0);
        f.prepare("A", "alpha", &p);
        f.reject(
            "assignment observe",
            f.receipt("A", "launching"),
            "record-only CLI cannot validate",
        );
        assert_eq!(f.show()["assignments"][0]["state"], "prepared");
    }
}
#[test]
fn missing_evidence_and_incompatible_deferral_never_override_acceptance() {
    let mut f = Fixture::new();
    f.create();
    f.apply("task activate", json!({"reason":"start"}));
    let a = f.freeze();
    let p = f.packet(&a, 0);
    let mut incomplete = f.packet_spec(&a, 0);
    incomplete["coverage"].as_object_mut().unwrap().remove("S1");
    f.reject("packet seal", incomplete, "coverage");
    for (id, agent) in [("A", "alpha"), ("B", "beta")] {
        f.prepare(id, agent, &p);
        f.finish_invocation(id);
        f.review(id, &a, &p);
    }
    f.reject("task complete",json!({"artifact":a,"criteria":{},"checks":{"offline":[a]},"approvals":{"owner":[a]},"reason":"missing criterion"}),"exact criterion");
    f.reject("task complete",json!({"artifact":a,"criteria":{"C1":["f".repeat(64)]},"checks":{"offline":[a]},"approvals":{"owner":[a]},"reason":"forged"}),"unknown evidence");
}
#[test]
fn native_profile_validation_agrees_with_python_contract_cases() {
    let mut variants = Vec::new();
    let mut f = Fixture::new();
    let base: Value = serde_json::from_slice(&fs::read(&f.profile).unwrap()).unwrap();
    variants.push((base.clone(), true));
    for (pointer, value) in [
        ("/version", json!(true)),
        ("/version", json!(2)),
        ("/bounds/writer_minutes", json!(0)),
        ("/bounds/reviewer_minutes", json!(1.5)),
        ("/bounds/enforcement", json!("hard")),
        ("/agents/alpha/reasoning", json!("default")),
        ("/agents/alpha/transport", json!("host")),
        ("/review/candidates", json!(["alpha", "alpha"])),
        ("/routing/small_writer", json!("absent")),
        ("/records_root", json!("../escape")),
        ("/name", json!("")),
    ] {
        let mut v = base.clone();
        *v.pointer_mut(pointer).unwrap() = value;
        variants.push((v, false));
    }
    let mut unknown = base.clone();
    unknown["unknown"] = json!(1);
    variants.push((unknown, false));
    for (i, (v, valid)) in variants.into_iter().enumerate() {
        let path = f.file(v);
        let py = Command::new("python3")
            .arg(
                Path::new(env!("CARGO_MANIFEST_DIR"))
                    .join("../skills/agents-collab/scripts/validate_profile.py"),
            )
            .arg(&path)
            .output()
            .unwrap();
        assert_eq!(py.status.success(), valid, "Python case {i}");
        fs::copy(&path, &f.profile).unwrap();
        let spec = f.file(f.task());
        let rust = execute(
            "task create",
            &f.record,
            Some(&spec),
            Some("create"),
            Some(0),
            Some(&f.profile),
            None,
        );
        assert_eq!(
            rust.status.success(),
            valid,
            "Rust case {i}: {}",
            String::from_utf8_lossy(&rust.stdout)
        );
    }
}
#[test]
fn completed_reviews_cannot_approve_drifted_live_source() {
    let mut f = Fixture::new();
    f.create();
    f.apply("task activate", json!({"reason":"start"}));
    let a = f.freeze();
    let p = f.packet(&a, 0);
    for (id, agent) in [("A", "alpha"), ("B", "beta")] {
        f.prepare(id, agent, &p);
        f.finish_invocation(id);
        f.review(id, &a, &p);
    }
    fs::write(f.repo.join("file.txt"), "unreviewed change").unwrap();
    f.reject("task complete",json!({"artifact":a,"criteria":{"C1":[a]},"checks":{"offline":[a]},"approvals":{"owner":[a]},"reason":"must not complete changed bytes"}),"live source identity changed");
}
#[test]
fn capture_detects_external_writer_drift() {
    use std::io::{BufRead, BufReader};
    let mut f = Fixture::new();
    f.create();
    let p=f.file(json!({"paths":[".gitignore","deleted.txt","file.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"declared quiescent but test violates it","atomic_required":false,"base":"HEAD"}));
    let mut child = Command::new(env!("CARGO_BIN_EXE_agents-collab"))
        .args(["artifact", "freeze", "--json", "--record"])
        .arg(&f.record)
        .arg("--input")
        .arg(p)
        .args(["--key", "drift", "--actor", "owner", "--expect", "1"])
        .env("AGENTS_COLLAB_CAPTURE_PAUSE", "test")
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap();
    let mut line = String::new();
    BufReader::new(child.stderr.take().unwrap())
        .read_line(&mut line)
        .unwrap();
    assert!(line.contains("capture-scanned-test-gate"));
    fs::write(f.repo.join("file.txt"), "externally changed during scan").unwrap();
    let out = child.wait_with_output().unwrap();
    assert!(!out.status.success());
    assert!(
        body(&out)["error"]["message"]
            .as_str()
            .unwrap()
            .contains("source drift")
    );
    assert!(f.show()["artifacts"].as_array().unwrap().is_empty());
}
#[test]
fn blocked_review_is_incomplete_not_a_consumed_valid_result() {
    let mut f = Fixture::new();
    f.create();
    let a = f.freeze();
    let p = f.packet(&a, 0);
    f.prepare("A", "alpha", &p);
    f.finish_invocation("A");
    let mut r = f.review_spec("A", &a, &p);
    r["verdict"] = json!("blocked");
    assert_eq!(f.apply("review import", r)["validation"], "incomplete");
    assert_eq!(f.show()["reviews"].as_array().unwrap().len(), 0);
    assert_eq!(f.show()["assignments"][0]["state"], "blocked");
    f.apply("assignment observe", f.receipt("A", "completed"));
    f.review("A", &a, &p);
}
#[test]
fn duplicate_json_keys_and_nonregular_inputs_are_rejected_without_hanging() {
    let mut f = Fixture::new();
    let p = f.file(f.task());
    fs::write(&f.profile, b"{\"version\":1,\"version\":1}").unwrap();
    assert!(
        !execute(
            "task create",
            &f.record,
            Some(&p),
            Some("create"),
            Some(0),
            Some(&f.profile),
            None
        )
        .status
        .success()
    );
    let fifo = f.inputs.join("fifo");
    let path = std::ffi::CString::new(fifo.as_os_str().as_encoded_bytes()).unwrap();
    assert_eq!(unsafe { libc::mkfifo(path.as_ptr(), 0o600) }, 0);
    assert!(
        !execute(
            "task create",
            &f.record,
            Some(&fifo),
            Some("create"),
            Some(0),
            Some(&f.profile),
            None
        )
        .status
        .success()
    );
}
#[test]
fn concurrent_result_imports_commit_once_and_identical_retries_return_same_receipt() {
    let mut f = Fixture::new();
    f.create();
    let a = f.freeze();
    let p = f.packet(&a, 0);
    f.prepare("A", "alpha", &p);
    f.finish_invocation("A");
    let result = f.file(f.review_spec("A", &a, &p));
    let barrier = Arc::new(Barrier::new(3));
    let mut handles = Vec::new();
    for _ in 0..2 {
        let (barrier, result, record, rev) =
            (barrier.clone(), result.clone(), f.record.clone(), f.rev);
        handles.push(std::thread::spawn(move || {
            barrier.wait();
            execute(
                "review import",
                &record,
                Some(&result),
                Some("same-import"),
                Some(rev),
                None,
                None,
            )
        }));
    }
    barrier.wait();
    let outputs: Vec<_> = handles
        .into_iter()
        .map(|h| good(&h.join().unwrap()))
        .collect();
    assert_eq!(outputs[0], outputs[1]);
    assert_eq!(f.show()["reviews"].as_array().unwrap().len(), 1);
    assert_eq!(f.show()["revision"], f.rev + 1);
}
#[test]
fn incompatible_deferral_and_replacement_reviewers_cannot_bypass_completion() {
    let mut f = Fixture::new();
    f.create();
    f.apply("task activate", json!({"reason":"start"}));
    let a = f.freeze();
    let p = f.packet(&a, 0);
    for (id, agent) in [("A", "alpha"), ("B", "beta")] {
        f.prepare(id, agent, &p);
        f.finish_invocation(id);
        let mut r = f.review_spec(id, &a, &p);
        if id == "A" {
            r["verdict"] = json!("changes_required");
            r["findings"] = json!([{"id":"F1","location":"C1","scenario":"Acceptance cannot be satisfied","evidence":"Synthetic proof","uncertainty":"declared synthetic","material":true,"recommendation":"owner decision"}]);
        }
        f.apply("review import", r);
    }
    f.apply("finding resolve",json!({"finding":"F1","decision":"deferred","reason":"Owner declaration cannot waive incompatible acceptance","evidence":[a],"authority":"owner","criterion_compatible":false}));
    f.reject("task complete",json!({"artifact":a,"criteria":{"C1":[a]},"checks":{"offline":[a]},"approvals":{"owner":[a]},"reason":"cannot override"}),"completion blocked");
    f.reject("assignment prepare",json!({"id":"replacement","packet":p,"agent":"writer","role":"reviewer","editable_scope":[],"output_destination":"private"}),"fixed required set");
    f.apply(
        "task cancel",
        json!({"reason":"owner stops unresolved task; no completion claim"}),
    );
    assert_eq!(f.show()["state"], "cancelled");
}

#[test]
fn storage_symlink_redirection_is_rejected_before_publication() {
    let mut f = Fixture::new();
    f.create();
    let outside = f.inputs.join("outside");
    fs::create_dir(&outside).unwrap();
    fs::remove_dir(f.record.join("staging")).unwrap();
    symlink(&outside, f.record.join("staging")).unwrap();
    f.reject(
        "task activate",
        json!({"reason":"must not write through redirected staging"}),
        "symlink",
    );
    assert!(fs::read_dir(outside).unwrap().next().is_none());
    assert_eq!(f.show()["revision"], 1);
}

#[test]
fn cached_completion_and_creation_retries_fail_on_current_evidence_damage() {
    for damage in ["corrupt", "missing"] {
        let mut f = Fixture::new();
        f.create();
        f.apply("task activate", json!({"reason":"start"}));
        let a = f.freeze();
        let p = f.packet(&a, 0);
        for (id, agent) in [("A", "alpha"), ("B", "beta")] {
            f.prepare(id, agent, &p);
            f.finish_invocation(id);
            f.review(id, &a, &p);
        }
        let expected = f.rev;
        let completion=f.file(json!({"artifact":a,"criteria":{"C1":[a]},"checks":{"offline":[a]},"approvals":{"owner":[a]},"reason":"complete after frozen checks"}));
        let lost = execute(
            "task complete",
            &f.record,
            Some(&completion),
            Some("unacknowledged"),
            Some(expected),
            None,
            Some("crash:after-commit"),
        );
        assert!(!lost.status.success());
        assert_eq!(f.show()["state"], "completed");
        let path = f.record.join("objects").join(&a);
        let original = fs::read(&path).unwrap();
        if damage == "corrupt" {
            fs::write(&path, "corrupted").unwrap();
        } else {
            fs::remove_file(&path).unwrap();
        }
        let retry = execute(
            "task complete",
            &f.record,
            Some(&completion),
            Some("unacknowledged"),
            Some(expected),
            None,
            None,
        );
        assert!(
            !retry.status.success(),
            "cached completion must report {damage}"
        );
        let task = f.file(f.task());
        let create = execute(
            "task create",
            &f.record,
            Some(&task),
            Some("create"),
            Some(0),
            Some(&f.profile),
            None,
        );
        assert!(
            !create.status.success(),
            "cached creation must report {damage}"
        );
        let db = rusqlite::Connection::open(f.record.join("state.sqlite3")).unwrap();
        let revision: i64 = db
            .query_row(
                "SELECT revision FROM operations WHERE key='unacknowledged'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(revision as u64, expected + 1);
        drop(db);
        fs::write(path, original).unwrap();
        assert_eq!(
            good(&execute(
                "task complete",
                &f.record,
                Some(&completion),
                Some("unacknowledged"),
                Some(expected),
                None,
                None
            ))["state"],
            "completed"
        );
        assert_eq!(
            good(&execute(
                "task create",
                &f.record,
                Some(&task),
                Some("create"),
                Some(0),
                Some(&f.profile),
                None
            ))["revision"],
            1
        );
    }
}

#[test]
fn detached_checkout_keeps_frozen_records_inspectable_but_cannot_complete_or_capture() {
    let mut f = Fixture::new();
    f.create();
    f.apply("task activate", json!({"reason":"start"}));
    let a = f.freeze();
    let p = f.packet(&a, 0);
    for (id, agent) in [("A", "alpha"), ("B", "beta")] {
        f.prepare(id, agent, &p);
        f.finish_invocation(id);
        f.review(id, &a, &p);
    }
    let moved = f.repo.with_file_name("detached-source");
    fs::rename(&f.repo, &moved).unwrap();
    let shown = good(&execute(
        "task show",
        &f.record,
        None,
        None,
        None,
        None,
        None,
    ));
    assert_eq!(shown["live_source"]["status"], "unavailable");
    assert_eq!(shown["record"]["reviews"].as_array().unwrap().len(), 2);
    let export = f.file(json!({"fields":["spec","reviews","packets"]}));
    let exported = good(&execute(
        "task export",
        &f.record,
        Some(&export),
        None,
        None,
        None,
        None,
    ));
    assert_eq!(exported["live_source"]["status"], "unavailable");
    let input = f.file(json!({"packet":p}));
    let packet = good(&execute(
        "packet show",
        &f.record,
        Some(&input),
        None,
        None,
        None,
        None,
    ));
    assert_eq!(packet["live_source"]["status"], "unavailable");
    let original: Value =
        serde_json::from_slice(&fs::read(f.record.join("objects").join(&p)).unwrap()).unwrap();
    assert_eq!(packet["sealed_packet"], original);
    f.apply(
        "task reconcile",
        json!({"reason":"source checkout removed; frozen evidence remains usable"}),
    );
    let checked = good(&execute(
        "task check",
        &f.record,
        None,
        None,
        None,
        None,
        None,
    ));
    assert_eq!(checked["live_source"]["status"], "unavailable");
    assert!(
        !checked["completion_blockers"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    f.reject("task complete",json!({"artifact":a,"criteria":{"C1":[a]},"checks":{"offline":[a]},"approvals":{"owner":[a]},"reason":"live source is missing"}),"Git inspection failed");
    f.reject("artifact freeze",json!({"paths":[".gitignore","deleted.txt","file.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"stopped","atomic_required":false,"base":"HEAD"}),"No such file");
    symlink(&f.record, &f.repo).unwrap();
    assert!(
        !execute("task show", &f.record, None, None, None, None, None)
            .status
            .success(),
        "current source alias must not bypass overlap validation"
    );
    fs::remove_file(&f.repo).unwrap();
    fs::rename(moved, &f.repo).unwrap();
    assert_eq!(f.complete(&a)["state"], "completed");
}

#[test]
fn staged_and_unstaged_git_file_directory_replacements_preserve_both_sides() {
    for direction in ["file-to-directory", "directory-to-file"] {
        for staged in [false, true] {
            let mut f = Fixture::new();
            if direction == "directory-to-file" {
                fs::create_dir(f.repo.join("shape")).unwrap();
                fs::write(f.repo.join("shape/child"), "old child\n").unwrap();
                git(&f.repo, &["add", "shape"]);
                git(&f.repo, &["commit", "-qm", "directory fixture"]);
            }
            f.create();
            let (old, new, old_bytes) = if direction == "file-to-directory" {
                fs::remove_file(f.repo.join("file.txt")).unwrap();
                fs::create_dir(f.repo.join("file.txt")).unwrap();
                fs::write(f.repo.join("file.txt/child"), "new child\n").unwrap();
                ("file.txt", "file.txt/child", b"original\n".as_slice())
            } else {
                fs::remove_dir_all(f.repo.join("shape")).unwrap();
                fs::write(f.repo.join("shape"), "new file\n").unwrap();
                ("shape/child", "shape", b"old child\n".as_slice())
            };
            if staged {
                git(&f.repo, &["add", "-A"]);
            }
            let mut paths = vec![".gitignore", "deleted.txt", "file.txt", old, new];
            paths.sort();
            paths.dedup();
            let result=f.apply("artifact freeze",json!({"paths":paths,"omissions":{},"acknowledged_sensitive":[],"quiescence":"coordinated stop","atomic_required":false,"base":"HEAD"}));
            let id = result["artifact"].as_str().unwrap();
            let manifest: Value =
                serde_json::from_slice(&fs::read(f.record.join("objects").join(id)).unwrap())
                    .unwrap();
            let entries = manifest["entries"].as_array().unwrap();
            let deletion = entries.iter().find(|e| e["path"] == old).unwrap();
            assert_eq!(deletion["kind"], "deleted", "{direction} staged={staged}");
            assert!(deletion["object"].is_null());
            assert_eq!(
                fs::read(
                    f.record
                        .join("objects")
                        .join(deletion["head_object"].as_str().unwrap())
                )
                .unwrap(),
                old_bytes
            );
            let replacement = entries.iter().find(|e| e["path"] == new).unwrap();
            assert_eq!(replacement["kind"], "file");
            assert!(replacement["object"].is_string());
            good(&execute(
                "task check",
                &f.record,
                None,
                None,
                None,
                None,
                None,
            ));
        }
    }
}

#[test]
fn recorded_writer_output_gets_initial_review_then_recorded_repair_uses_followup() {
    let mut f = Fixture::new();
    f.create();
    f.apply(
        "task activate",
        json!({"reason":"start recorded writer workflow"}),
    );
    let input = f.freeze();
    let mut context = f.packet_spec(&input, 0);
    context["purpose"] = json!("writer_context");
    context["neutral_initial"] = json!(false);
    let writer_packet = f.apply("packet seal", context)["packet"]
        .as_str()
        .unwrap()
        .to_string();
    f.apply("assignment prepare",json!({"id":"W","packet":writer_packet,"agent":"writer","role":"writer","editable_scope":["file.txt"],"output_destination":"private-writer-output"}));
    f.reject("assignment prepare",json!({"id":"not-a-review","packet":writer_packet,"agent":"alpha","role":"reviewer","editable_scope":[],"output_destination":"private"}),"reviewer requires");
    f.apply("assignment observe", f.receipt("W", "launching"));
    fs::write(f.repo.join("file.txt"), "initial writer output\n").unwrap();
    f.reject("artifact freeze",json!({"paths":[".gitignore","deleted.txt","file.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"not actually finished","atomic_required":false,"base":"HEAD"}),"reconcile active");
    f.apply("assignment observe", f.receipt("W", "completed"));
    let output = f.freeze();
    assert_ne!(input, output);
    let review_packet = f.packet(&output, 0);
    for (id, agent) in [("A", "alpha"), ("B", "beta")] {
        f.prepare(id, agent, &review_packet);
        f.finish_invocation(id);
        let mut r = f.review_spec(id, &output, &review_packet);
        if id == "A" {
            r["verdict"] = json!("changes_required");
            r["findings"] = json!([{"id":"WriterFix","location":"R1","scenario":"synthetic defect in initial output","evidence":"supplied source reasoning","uncertainty":"synthetic fixture","material":true,"recommendation":"repair"}]);
            f.apply("review import", r);
            let mut premature = f.packet_spec(&output, 1);
            premature["purpose"] = json!("writer_context");
            f.reject("packet seal", premature, "finish every required reviewer");
        } else {
            f.apply("review import", r);
        }
    }
    let mut repair_context = f.packet_spec(&output, 1);
    repair_context["purpose"] = json!("writer_context");
    let repair_packet = f.apply("packet seal", repair_context)["packet"]
        .as_str()
        .unwrap()
        .to_string();
    f.apply("assignment prepare",json!({"id":"W2","packet":repair_packet,"agent":"writer","role":"writer","editable_scope":["file.txt"],"output_destination":"private-repair-output"}));
    f.apply("assignment observe", f.receipt("W2", "launching"));
    fs::write(f.repo.join("file.txt"), "repaired writer output\n").unwrap();
    f.apply("assignment observe", f.receipt("W2", "completed"));
    f.apply("finding resolve",json!({"finding":"WriterFix","decision":"addressed","reason":"recorded writer repairs defect","evidence":[output],"authority":"owner","criterion_compatible":true}));
    let repaired = f.freeze();
    let followup = f.packet(&repaired, 1);
    for (id, agent) in [("A2", "alpha"), ("B2", "beta")] {
        f.prepare(id, agent, &followup);
        f.finish_invocation(id);
        f.review(id, &repaired, &followup);
    }
    let mut over = f.packet_spec(&repaired, 2);
    over["purpose"] = json!("writer_context");
    f.reject("packet seal", over, "round cap");
    let state = f.show();
    assert_eq!(state["reviews"].as_array().unwrap().len(), 4);
    assert_eq!(
        state["packets"]
            .as_array()
            .unwrap()
            .iter()
            .filter(|p| p["spec"]["purpose"] == "review")
            .count(),
        2
    );
    assert_eq!(
        state["assignments"]
            .as_array()
            .unwrap()
            .iter()
            .filter(|a| a["spec"]["role"] == "writer")
            .count(),
        2
    );
    assert_eq!(f.complete(&repaired)["state"], "completed");
}

#[test]
fn reattached_old_writer_blocks_prepared_replacement_launch_until_reconciled_terminal() {
    let mut f = Fixture::new();
    f.create();
    f.apply(
        "task activate",
        json!({"reason":"synthetic interrupted writer recovery"}),
    );
    let input = f.freeze();
    let mut first = f.packet_spec(&input, 0);
    first["purpose"] = json!("writer_context");
    let first_packet = f.apply("packet seal", first)["packet"]
        .as_str()
        .unwrap()
        .to_string();
    f.apply("assignment prepare",json!({"id":"W1","packet":first_packet,"agent":"writer","role":"writer","editable_scope":["file.txt"],"output_destination":"private-first-writer"}));
    f.apply("assignment observe", f.receipt("W1", "launching"));
    let original = f.show()["assignments"][0].clone();
    f.apply(
        "task reconcile",
        json!({"reason":"host launch receipt gap"}),
    );
    f.apply("assignment observe", f.receipt("W1", "running"));
    f.apply("assignment observe", f.receipt("W1", "interrupted"));
    let mut second = f.packet_spec(&input, 0);
    second["purpose"] = json!("writer_context");
    second["instructions"] =
        json!("Continue the remaining initial writing after interrupted host work");
    let second_packet = f.apply("packet seal", second)["packet"]
        .as_str()
        .unwrap()
        .to_string();
    f.apply("assignment prepare",json!({"id":"W2","packet":second_packet,"agent":"writer","role":"writer","editable_scope":["file.txt"],"output_destination":"private-replacement-writer"}));
    // The old worker is truthfully reattached after replacement preparation.
    // Preserve that observation instead of pretending the worker stopped.
    f.apply("assignment observe", f.receipt("W1", "running"));
    let before = f.show();
    assert_eq!(before["assignments"][0]["state"], "running");
    assert_eq!(before["assignments"][1]["state"], "prepared");
    let revision = f.rev;
    f.reject(
        "assignment observe",
        f.receipt("W2", "launching"),
        "writer launch blocked",
    );
    let refused = f.show();
    assert_eq!(refused["revision"], revision);
    assert_eq!(refused["assignments"], before["assignments"]);
    assert!(refused["assignments"][1]["launch_at"].is_null());
    assert!(refused["assignments"][1]["deadline"].is_null());
    assert_eq!(
        refused["assignments"][0]["launch_at"],
        original["launch_at"]
    );
    assert_eq!(refused["assignments"][0]["deadline"], original["deadline"]);
    assert!(
        refused["assignments"][0]["observations"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|o| o["receipt"]["invocation"].as_str())
            .all(|id| id == "host-session-W1")
    );
    f.reject("artifact freeze",json!({"paths":[".gitignore","deleted.txt","file.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"must not capture competing work","atomic_required":false,"base":"HEAD"}),"reconcile active");
    f.reject("task complete",json!({"artifact":input,"criteria":{"C1":[input]},"checks":{"offline":[input]},"approvals":{"owner":[input]},"reason":"unresolved writer activity cannot complete"}),"completion blocked");
    f.apply("assignment observe", f.receipt("W1", "unknown"));
    f.reject(
        "assignment observe",
        f.receipt("W2", "launching"),
        "writer launch blocked",
    );
    // Only reconciled terminal evidence permits the new intent; W1's original
    // invocation/deadline survive, and the replacement gets its own first launch.
    f.apply("assignment observe", f.receipt("W1", "completed"));
    f.apply("assignment observe", f.receipt("W2", "launching"));
    let launched = f.show();
    assert_eq!(launched["assignments"][0]["deadline"], original["deadline"]);
    assert_eq!(launched["assignments"][0]["state"], "completed");
    assert_eq!(launched["assignments"][1]["state"], "launching");
    assert!(launched["assignments"][1]["launch_at"].is_u64());
    let replacement_deadline = launched["assignments"][1]["deadline"].clone();
    f.reject(
        "assignment observe",
        f.receipt("W2", "launching"),
        "no retry/duplicate launch",
    );
    assert_eq!(f.show()["assignments"][1]["deadline"], replacement_deadline);
    fs::write(f.repo.join("file.txt"), "recovered writer output\n").unwrap();
    f.apply("assignment observe", f.receipt("W2", "completed"));
    let output = f.freeze();
    let packet = f.packet(&output, 0);
    for (id, agent) in [("A", "alpha"), ("B", "beta")] {
        f.prepare(id, agent, &packet);
        f.finish_invocation(id);
        f.review(id, &output, &packet);
    }
    assert_eq!(f.complete(&output)["state"], "completed");
    assert_eq!(f.show()["assignments"][0]["deadline"], original["deadline"]);
}
