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
fn dotted_projects_keep_exact_layout_and_can_be_reopened() {
    for project in [
        "example.com",
        "api.example.co.uk",
        "A_b-1.example",
        &format!("{}.b", "a".repeat(38)),
    ] {
        let mut f = Fixture::new();
        let records = f.record.ancestors().nth(3).unwrap().to_path_buf();
        f.record = records.join(project).join("task/collaboration");
        let mut spec = f.task();
        spec["project"] = json!(project);
        let input = f.file(spec);
        let created = good(&execute(
            "task create",
            &f.record,
            Some(&input),
            Some("create"),
            Some(0),
            Some(&f.profile),
            None,
        ));
        assert_eq!(created["record"], json!(f.record));
        assert_eq!(f.show()["spec"]["project"], project);
        assert_eq!(
            good(&execute(
                "task check",
                &f.record,
                None,
                None,
                None,
                None,
                None
            ))["integrity"],
            "verified"
        );
    }
}

#[test]
fn unsafe_project_names_and_dotted_task_ids_fail_before_creation() {
    for project in [
        "",
        ".",
        "..",
        ".hidden",
        "example.",
        "a..b",
        "a.-b",
        "a._b",
        "../example.com",
        "a/b.com",
        "a\\b.com",
        "/example.com",
        "a b.com",
        "a\nb.com",
        "a\0b.com",
        "é.com",
        &format!("{}.b", "a".repeat(39)),
    ] {
        let mut f = Fixture::new();
        let mut spec = f.task();
        spec["project"] = json!(project);
        let input = f.file(spec);
        let out = execute(
            "task create",
            &f.record,
            Some(&input),
            Some("create"),
            Some(0),
            Some(&f.profile),
            None,
        );
        assert!(!out.status.success(), "accepted {project:?}");
        assert!(
            body(&out)["error"]["message"]
                .as_str()
                .unwrap()
                .contains("unsafe project component")
        );
        assert!(!f.record.parent().unwrap().exists());
    }
    let mut f = Fixture::new();
    let mut spec = f.task();
    spec["project"] = json!("example.com");
    spec["task"] = json!("task.name");
    let input = f.file(spec);
    let out = execute(
        "task create",
        &f.record,
        Some(&input),
        Some("create"),
        Some(0),
        Some(&f.profile),
        None,
    );
    assert!(!out.status.success());
    assert!(
        body(&out)["error"]["message"]
            .as_str()
            .unwrap()
            .contains("unsafe project/task component")
    );
    assert!(!f.record.parent().unwrap().exists());
}

#[test]
fn dotted_project_storage_symlinks_fail_before_creation() {
    for child in ["project", "task"] {
        for dangling in [false, true] {
            let mut f = Fixture::new();
            let records = f.record.ancestors().nth(3).unwrap().to_path_buf();
            let project = records.join("example.com");
            let outside = f.inputs.join("outside");
            if !dangling {
                fs::create_dir(&outside).unwrap();
            }
            let alias = if child == "project" {
                project.clone()
            } else {
                fs::create_dir(&project).unwrap();
                project.join("task")
            };
            symlink(&outside, &alias).unwrap();
            f.record = project.join("task/collaboration");
            let mut spec = f.task();
            spec["project"] = json!("example.com");
            let input = f.file(spec);
            let out = execute(
                "task create",
                &f.record,
                Some(&input),
                Some("create"),
                Some(0),
                Some(&f.profile),
                None,
            );
            assert!(!out.status.success());
            assert!(
                body(&out)["error"]["message"]
                    .as_str()
                    .unwrap()
                    .contains("symlink")
            );
            if dangling {
                assert!(!outside.exists());
            } else {
                assert!(fs::read_dir(outside).unwrap().next().is_none());
            }
        }
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

fn quota_fixture() -> Fixture {
    let f = Fixture::new();
    let mut profile: Value = serde_json::from_slice(&fs::read(&f.profile).unwrap()).unwrap();
    for agent in ["writer", "alpha"] {
        profile["agents"][agent]["transport"] = json!("claude-cli");
    }
    fs::write(&f.profile, serde_json::to_vec(&profile).unwrap()).unwrap();
    f
}
fn handoff_spec(id: &str, replacement: &str, packet: &str, evidence: &str) -> Value {
    json!({"assignment":id,"replacement":replacement,"packet":packet,"agent":"continuation-codex",
        "selection":{"model":"synthetic-codex","transport":"codex-native","reasoning":"inherit"},
        "output_destination":format!("private-{replacement}"),"decision":"continue_with_codex","authority":"owner",
        "decision_evidence":[evidence],"reason":"Synthetic quota receipt; owner explicitly chose available Codex",
        "previous_invocation":format!("host-session-{id}"),"timing":"preserve_deadline",
        "instructions":"Continue the unfinished slot on the exact sealed contract. Writer: preserve current partial source; reviewer: fresh neutral packet only, no writer transcript.","partial_work":null})
}
fn interrupt_absent(f: &mut Fixture, id: &str) {
    f.apply("assignment observe", f.receipt(id, "launching"));
    let mut receipt = f.receipt(id, "interrupted");
    receipt["absence_established"] = json!(true);
    receipt["reason"] = json!(
        "Synthetic quota failure; host reconciled original invocation exit and no remaining worker"
    );
    f.apply("assignment observe", receipt);
}
#[test]
fn interrupted_reviewer_handoff_preserves_slot_round_history_and_format() {
    let mut f = quota_fixture();
    f.create();
    f.apply("task activate", json!({"reason":"synthetic authorization"}));
    let a = f.freeze();
    let p = f.packet(&a, 0);
    f.prepare("review-a", "alpha", &p);
    interrupt_absent(&mut f, "review-a");
    let before = f.show();
    assert_eq!(before["schema_version"], 1);
    let h = handoff_spec("review-a", "review-codex", &p, &a);
    let response = f.apply("assignment handoff", h.clone());
    assert_eq!(response["logical_slot"], "alpha");
    let after = f.show();
    assert_eq!(after["schema_version"], 2);
    assert_eq!(after["profile"], before["profile"]);
    assert_eq!(after["profile_hash"], before["profile_hash"]);
    assert_eq!(
        after["assignments"][0]["observations"],
        before["assignments"][0]["observations"]
    );
    assert_eq!(after["assignments"][0]["state"], "superseded");
    assert_eq!(
        after["assignments"][0]["requested"]["transport"],
        "claude-cli"
    );
    assert_eq!(
        after["assignments"][1]["requested"]["model"],
        "synthetic-codex"
    );
    assert_eq!(
        after["assignments"][1]["deadline"],
        before["assignments"][0]["deadline"]
    );
    f.reject("assignment handoff", h, "replacement identity already used");
    f.reject(
        "assignment observe",
        f.receipt("review-a", "completed"),
        "superseded",
    );
    let rejected = f.apply("review import", f.review_spec("review-a", &a, &p));
    assert_eq!(rejected["validation"], "rejected");
    f.finish_invocation("review-codex");
    let mut review = f.review_spec("review-codex", &a, &p);
    review["fresh_session"] = json!("host-session-review-codex");
    assert_eq!(
        f.apply("review import", review)["validation"],
        "valid_structure_only"
    );
    f.prepare("review-b", "beta", &p);
    f.finish_invocation("review-b");
    f.apply("review import", f.review_spec("review-b", &a, &p));
    f.complete(&a);
    let record = f.show();
    assert_eq!(record["state"], "completed");
    assert_eq!(record["packets"].as_array().unwrap().len(), 1);
    assert_eq!(record["reviews"].as_array().unwrap().len(), 2);
    // Older CLIs check this durable SQL marker before interpreting the JSON.
    let db = rusqlite::Connection::open(f.record.join("state.sqlite3")).unwrap();
    let version: i64 = db
        .query_row("SELECT schema_version FROM state", [], |r| r.get(0))
        .unwrap();
    assert_eq!(version, 2);
}
#[test]
fn interrupted_writer_handoff_preserves_live_partial_work_and_original_deadline() {
    let mut f = quota_fixture();
    f.create();
    let a = f.freeze();
    let mut spec = f.packet_spec(&a, 0);
    spec["purpose"] = json!("writer_context");
    spec["neutral_initial"] = json!(false);
    let p = f.apply("packet seal", spec)["packet"]
        .as_str()
        .unwrap()
        .to_string();
    f.apply("assignment prepare", json!({"id":"write-a","packet":p,"agent":"writer","role":"writer","editable_scope":["file.txt"],"output_destination":"old-result"}));
    interrupt_absent(&mut f, "write-a");
    fs::write(f.repo.join("file.txt"), "unfinished partial changes\n").unwrap();
    let mut h = handoff_spec("write-a", "write-codex", &p, &a);
    f.reject(
        "assignment handoff",
        h.clone(),
        "snapshot of current partial work",
    );
    h["partial_work"] = json!({"paths":[".gitignore","deleted.txt","file.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"original absent; source quiescent","atomic_required":false,"base":"HEAD"});
    let before = f.show();
    let result = f.apply("assignment handoff", h);
    let preserved = result["preserved_work"].as_str().unwrap();
    let manifest: Value =
        serde_json::from_slice(&fs::read(f.record.join("objects").join(preserved)).unwrap())
            .unwrap();
    let partial = manifest["entries"]
        .as_array()
        .unwrap()
        .iter()
        .find(|e| e["path"] == "file.txt")
        .unwrap()["object"]
        .as_str()
        .unwrap();
    assert_eq!(
        fs::read_to_string(f.record.join("objects").join(partial)).unwrap(),
        "unfinished partial changes\n"
    );
    assert_eq!(
        fs::read_to_string(f.repo.join("file.txt")).unwrap(),
        "unfinished partial changes\n"
    );
    assert_eq!(f.show()["current_artifact"], a);
    f.finish_invocation("write-codex");
    assert_eq!(
        f.show()["assignments"][1]["deadline"],
        before["assignments"][0]["deadline"]
    );
    assert_eq!(f.show()["assignments"][1]["state"], "completed");
}
#[test]
fn handoff_fails_closed_on_decision_liveness_identity_timing_and_packet() {
    let mut f = quota_fixture();
    f.create();
    let a = f.freeze();
    let p = f.packet(&a, 0);
    f.prepare("a", "alpha", &p);
    f.apply("assignment observe", f.receipt("a", "launching"));
    let mut h = handoff_spec("a", "replacement", &p, &a);
    f.reject("assignment handoff", h.clone(), "only an interrupted");
    f.apply("assignment observe", f.receipt("a", "unknown"));
    f.reject("assignment handoff", h.clone(), "only an interrupted");
    f.apply("assignment observe", f.receipt("a", "interrupted"));
    f.reject("assignment handoff", h.clone(), "absence");
    let mut receipt = f.receipt("a", "interrupted");
    receipt["absence_established"] = json!(true);
    f.apply("assignment observe", receipt);
    for (key, value, message) in [
        ("decision", json!("wait"), "explicit owner choice"),
        (
            "decision_evidence",
            json!([]),
            "evidence references required",
        ),
        ("authority", json!("stranger"), "authority/actor"),
        (
            "output_destination",
            json!("private-result-a"),
            "distinct output destination",
        ),
        (
            "previous_invocation",
            json!("wrong"),
            "invocation identity mismatch",
        ),
        ("timing", json!("reset_deadline"), "preserve_deadline"),
        ("packet", json!(a), "sealed handoff packet"),
        ("agent", json!("alpha"), "cannot redefine"),
    ] {
        let mut bad = h.clone();
        bad[key] = value;
        f.reject("assignment handoff", bad, message);
    }
    h["selection"] = Value::Null;
    h["agent"] = json!("beta");
    f.apply("assignment handoff", h);
    f.apply("assignment observe", f.receipt("replacement", "launching"));
    let mut reused = f.receipt("replacement", "completed");
    reused["invocation"] = json!("host-session-a");
    f.reject("assignment observe", reused, "fresh session");
}
#[test]
fn continuation_session_cannot_be_reused_by_another_reviewer_in_either_order() {
    for continuation_first in [true, false] {
        let mut f = quota_fixture();
        f.create();
        f.apply("task activate", json!({"reason":"synthetic authorization"}));
        let a = f.freeze();
        let p = f.packet(&a, 0);
        f.prepare("review-a", "alpha", &p);
        interrupt_absent(&mut f, "review-a");
        let mut h = handoff_spec("review-a", "continuation", &p, &a);
        // Both logical slots may use the same configured execution agent,
        // but they must not use the same declared invocation.
        h["agent"] = json!("beta");
        h["selection"] = Value::Null;
        f.apply("assignment handoff", h);
        f.prepare("review-b", "beta", &p);
        for id in ["continuation", "review-b"] {
            f.apply("assignment observe", f.receipt(id, "launching"));
        }
        let (first, second) = if continuation_first {
            ("continuation", "review-b")
        } else {
            ("review-b", "continuation")
        };
        // Repeated observations within one assignment remain valid.
        for state in ["running", "running", "completed"] {
            f.apply("assignment observe", f.receipt(first, state));
        }
        let mut review = f.review_spec(first, &a, &p);
        review["fresh_session"] = json!(format!("host-session-{first}"));
        f.apply("review import", review);
        let before = f.show();
        for state in ["running", "completed", "interrupted"] {
            let mut reused = f.receipt(second, state);
            reused["invocation"] = json!(format!("host-session-{first}"));
            f.reject("assignment observe", reused, "fresh session");
            assert_eq!(f.show(), before);
        }
        // The rejected identity does not poison recovery with a distinct one.
        for state in ["running", "completed"] {
            f.apply("assignment observe", f.receipt(second, state));
        }
        let mut review = f.review_spec(second, &a, &p);
        review["fresh_session"] = json!(format!("host-session-{second}"));
        f.apply("review import", review);
        assert_eq!(f.complete(&a)["state"], "completed");
    }
}

#[test]
fn handoff_cannot_replace_completed_or_unfavorable_review() {
    for verdict in ["pass", "changes_required", "blocked"] {
        let mut f = quota_fixture();
        f.create();
        let a = f.freeze();
        let p = f.packet(&a, 0);
        f.prepare("a", "alpha", &p);
        f.finish_invocation("a");
        f.reject(
            "assignment handoff",
            handoff_spec("a", "b", &p, &a),
            "only an interrupted",
        );
        let mut review = f.review_spec("a", &a, &p);
        review["verdict"] = json!(verdict);
        f.apply("review import", review);
        f.reject(
            "assignment handoff",
            handoff_spec("a", "b", &p, &a),
            "only an interrupted",
        );
        if verdict == "blocked" {
            let mut receipt = f.receipt("a", "interrupted");
            receipt["absence_established"] = json!(true);
            f.apply("assignment observe", receipt);
            f.apply("assignment handoff", handoff_spec("a", "b", &p, &a));
            assert_eq!(f.show()["invalid_results"].as_array().unwrap().len(), 1);
        } else {
            let mut receipt = f.receipt("a", "interrupted");
            receipt["absence_established"] = json!(true);
            f.reject(
                "assignment observe",
                receipt,
                "valid result already imported",
            );
        }
    }
}
#[test]
fn racing_handoffs_keep_cas_and_idempotency() {
    let mut f = quota_fixture();
    f.create();
    let a = f.freeze();
    let p = f.packet(&a, 0);
    f.prepare("a", "alpha", &p);
    interrupt_absent(&mut f, "a");
    let input = f.file(handoff_spec("a", "b", &p, &a));
    let other = f.file(handoff_spec("a", "c", &p, &a));
    let barrier = Arc::new(Barrier::new(2));
    let workers: Vec<_> = [(input.clone(), "handoff-1"), (other, "handoff-2")]
        .into_iter()
        .map(|(path, key)| {
            let record = f.record.clone();
            let expected = f.rev;
            let gate = barrier.clone();
            std::thread::spawn(move || {
                gate.wait();
                execute(
                    "assignment handoff",
                    &record,
                    Some(&path),
                    Some(key),
                    Some(expected),
                    None,
                    None,
                )
            })
        })
        .collect();
    let outputs: Vec<_> = workers.into_iter().map(|t| t.join().unwrap()).collect();
    assert_eq!(outputs.iter().filter(|o| o.status.success()).count(), 1);
    let winner = if outputs[0].status.success() { 0 } else { 1 };
    let loser = 1 - winner;
    assert!(
        body(&outputs[loser])["error"]["message"]
            .as_str()
            .unwrap()
            .contains("stale revision")
    );
    // Replay the winner with exactly the original key, revision and input.
    let path = if winner == 0 {
        input
    } else {
        f.inputs.join(format!("{}.json", f.seq))
    };
    let replay = execute(
        "assignment handoff",
        &f.record,
        Some(&path),
        Some(if winner == 0 {
            "handoff-1"
        } else {
            "handoff-2"
        }),
        Some(f.rev),
        None,
        None,
    );
    assert_eq!(good(&replay), good(&outputs[winner]));
    assert_eq!(f.show()["assignments"].as_array().unwrap().len(), 2);
}

#[test]
fn handoff_refuses_stale_writer_packet_and_writer_session_as_reviewer() {
    let mut f = quota_fixture();
    f.create();
    let a = f.freeze();
    let mut packet = f.packet_spec(&a, 0);
    packet["purpose"] = json!("writer_context");
    packet["neutral_initial"] = json!(false);
    let p = f.apply("packet seal", packet)["packet"]
        .as_str()
        .unwrap()
        .to_string();
    f.apply("assignment prepare", json!({"id":"w","packet":p,"agent":"writer","role":"writer","editable_scope":["file.txt"],"output_destination":"writer-result"}));
    interrupt_absent(&mut f, "w");
    fs::write(f.repo.join("file.txt"), "partial writer source\n").unwrap();
    let changed = f.freeze();
    assert_ne!(a, changed);
    f.reject(
        "assignment handoff",
        handoff_spec("w", "replacement", &p, &a),
        "stale/mismatched handoff packet",
    );
    // Reconcile the original writer to finish, then create a neutral review stage.
    f.apply("assignment observe", f.receipt("w", "completed"));
    let p = f.packet(&changed, 0);
    f.prepare("review-a", "alpha", &p);
    interrupt_absent(&mut f, "review-a");
    f.apply(
        "assignment handoff",
        handoff_spec("review-a", "review-codex", &p, &changed),
    );
    f.apply("assignment observe", f.receipt("review-codex", "launching"));
    let mut reused = f.receipt("review-codex", "completed");
    reused["invocation"] = json!("host-session-w");
    f.reject("assignment observe", reused, "fresh session");
    f.apply("assignment observe", f.receipt("review-codex", "completed"));
    let rejected = f.apply("review import", f.review_spec("review-codex", &changed, &p));
    assert_eq!(rejected["validation"], "rejected");
    assert!(
        rejected["reason"]
            .as_str()
            .unwrap()
            .contains("fresh_session")
    );
    let mut review = f.review_spec("review-codex", &changed, &p);
    review["fresh_session"] = json!("host-session-review-codex");
    assert_eq!(
        f.apply("review import", review)["validation"],
        "valid_structure_only"
    );
}

#[test]
fn writer_handoff_preserves_directory_partial_work_and_allows_absent_future_paths() {
    let mut f = quota_fixture();
    fs::create_dir(f.repo.join("src")).unwrap();
    fs::write(f.repo.join("src/existing.txt"), "tracked baseline\n").unwrap();
    fs::write(f.repo.join("src/deleted.txt"), "tracked before deletion\n").unwrap();
    git(&f.repo, &["add", "src"]);
    git(&f.repo, &["commit", "-qm", "directory fixture"]);
    let mut task = f.task();
    task["editable_scope"] = json!(["src", "future.txt", "ignored.txt"]);
    let input = f.file(task);
    f.rev = good(&execute(
        "task create",
        &f.record,
        Some(&input),
        Some("create"),
        Some(0),
        Some(&f.profile),
        None,
    ))["revision"]
        .as_u64()
        .unwrap();
    let artifact = f.apply("artifact freeze", json!({"paths":[".gitignore", "file.txt", "deleted.txt", "src/existing.txt", "src/deleted.txt"], "omissions":{}, "acknowledged_sensitive":[], "quiescence":"no writer yet", "atomic_required":false, "base":"HEAD"}))["artifact"].as_str().unwrap().to_string();
    let mut packet = f.packet_spec(&artifact, 0);
    packet["purpose"] = json!("writer_context");
    packet["neutral_initial"] = json!(false);
    let packet = f.apply("packet seal", packet)["packet"]
        .as_str()
        .unwrap()
        .to_string();
    f.apply("assignment prepare", json!({"id":"writer-old", "packet":packet, "agent":"writer", "role":"writer", "editable_scope":["src", "future.txt", "ignored.txt"], "output_destination":"old-output"}));
    interrupt_absent(&mut f, "writer-old");
    fs::write(
        f.repo.join("src/existing.txt"),
        "unfinished tracked edits\n",
    )
    .unwrap();
    fs::write(f.repo.join("src/partial.txt"), "new unfinished source\n").unwrap();
    fs::remove_file(f.repo.join("src/deleted.txt")).unwrap();
    fs::write(
        f.repo.join("ignored.txt"),
        "explicit ignored partial source\n",
    )
    .unwrap();
    let before = f.show();
    let mut handoff = handoff_spec("writer-old", "writer-new", &packet, &artifact);
    handoff["partial_work"] = json!({"paths":["src/existing.txt", "src/deleted.txt", "ignored.txt"], "omissions":{".gitignore":"unrelated", "file.txt":"unrelated", "deleted.txt":"unrelated", "src/partial.txt":"incorrect omission of partial source"}, "acknowledged_sensitive":[], "quiescence":"original worker absent", "atomic_required":false, "base":"HEAD"});
    f.reject(
        "assignment handoff",
        handoff.clone(),
        "cannot omit scoped inventory",
    );
    assert_eq!(f.show(), before);
    handoff["partial_work"]["paths"] =
        json!(["src/existing.txt", "src/partial.txt", "ignored.txt"]);
    handoff["partial_work"]["omissions"]
        .as_object_mut()
        .unwrap()
        .remove("src/partial.txt");
    handoff["partial_work"]["omissions"]["src/deleted.txt"] =
        json!("incorrect omission of tracked deletion");
    f.reject(
        "assignment handoff",
        handoff.clone(),
        "cannot omit scoped inventory",
    );
    assert_eq!(f.show(), before);
    handoff["partial_work"]["paths"] =
        json!(["src/existing.txt", "src/partial.txt", "src/deleted.txt"]);
    handoff["partial_work"]["omissions"]
        .as_object_mut()
        .unwrap()
        .remove("src/deleted.txt");
    f.reject(
        "assignment handoff",
        handoff.clone(),
        "select existing exact scoped input",
    );
    assert_eq!(f.show(), before);
    handoff["partial_work"]["paths"] = json!([
        "src/existing.txt",
        "src/partial.txt",
        "src/deleted.txt",
        "ignored.txt"
    ]);
    let result = f.apply("assignment handoff", handoff);
    let preserved = result["preserved_work"].as_str().unwrap();
    let manifest: Value =
        serde_json::from_slice(&fs::read(f.record.join("objects").join(preserved)).unwrap())
            .unwrap();
    for (path, content) in [
        ("src/existing.txt", "unfinished tracked edits\n"),
        ("src/partial.txt", "new unfinished source\n"),
        ("ignored.txt", "explicit ignored partial source\n"),
    ] {
        let entry = manifest["entries"]
            .as_array()
            .unwrap()
            .iter()
            .find(|e| e["path"] == path)
            .unwrap();
        assert_eq!(
            fs::read_to_string(
                f.record
                    .join("objects")
                    .join(entry["object"].as_str().unwrap())
            )
            .unwrap(),
            content
        );
        assert_eq!(fs::read_to_string(f.repo.join(path)).unwrap(), content);
    }
    let deleted = manifest["entries"]
        .as_array()
        .unwrap()
        .iter()
        .find(|e| e["path"] == "src/deleted.txt")
        .unwrap();
    assert_eq!(deleted["kind"], "deleted");
    assert!(!f.repo.join("future.txt").exists());
    let after = f.show();
    assert_eq!(after["current_artifact"], before["current_artifact"]);
    assert_eq!(
        after["assignments"][0]["observations"],
        before["assignments"][0]["observations"]
    );
    assert_eq!(
        after["assignments"][1]["deadline"],
        before["assignments"][0]["deadline"]
    );
    assert_eq!(after["assignments"][0]["state"], "superseded");
    assert_eq!(after["schema_version"], 2);
}

fn review_at_cap(f: &mut Fixture, finish_last: bool) -> (String, String) {
    let mut artifact = f.freeze();
    let mut packet = String::new();
    for round in 0..=1 {
        if round > 0 {
            fs::write(f.repo.join("file.txt"), "first repair\n").unwrap();
            artifact = f.freeze();
        }
        packet = f.packet(&artifact, round);
        for (prefix, agent) in [("A", "alpha"), ("B", "beta")] {
            let id = format!("{prefix}{round}");
            f.prepare(&id, agent, &packet);
            if finish_last || round == 0 || prefix == "A" {
                f.finish_invocation(&id);
                let mut review = f.review_spec(&id, &artifact, &packet);
                if round == 1 && prefix == "A" {
                    review["verdict"] = json!("changes_required");
                }
                f.apply("review import", review);
            }
        }
    }
    (artifact, packet)
}
fn extension(packet: &str, evidence: &str, previous: u64) -> Value {
    json!({"packet":packet,"previous_limit":previous,"new_limit":previous+1,
        "authority":"owner","decision_evidence":[evidence],
        "reason":"Owner explicitly permits one additional review after the retained capped result"})
}
#[test]
fn explicit_review_extension_preserves_contract_history_and_requires_fresh_review() {
    let mut f = Fixture::new();
    f.create();
    f.apply("task activate", json!({"reason":"start"}));
    let (artifact, packet) = review_at_cap(&mut f, true);
    let before = f.show();
    let profile_bytes = fs::read(&f.profile).unwrap();
    fs::write(f.repo.join("file.txt"), "second repair\n").unwrap();
    let selection = json!({"paths":[".gitignore","deleted.txt","file.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"writer stopped","atomic_required":false,"base":"HEAD"});
    f.reject("artifact freeze", selection.clone(), "round cap");
    let mut next_context = f.packet_spec(&artifact, 2);
    next_context["purpose"] = json!("writer_context");
    f.reject("packet seal", next_context.clone(), "round cap");
    let result = f.apply("task extend-review", extension(&packet, &artifact, 1));
    assert_eq!(result["effective_review_limit"], 2);
    let after = f.show();
    for field in [
        "spec",
        "profile",
        "profile_hash",
        "state",
        "reason",
        "artifacts",
        "current_artifact",
        "packets",
        "assignments",
        "reviews",
        "findings",
        "invalid_results",
        "completion",
    ] {
        assert_eq!(after[field], before[field], "changed {field}");
    }
    for (id, kind) in before["objects"].as_object().unwrap() {
        assert_eq!(&after["objects"][id], kind);
    }
    assert_eq!(fs::read(&f.profile).unwrap(), profile_bytes);
    assert_eq!(after["schema_version"], 3);
    assert_eq!(after["review_extensions"].as_array().unwrap().len(), 1);
    // An amendment grants no pass and cannot rewrite the existing verdict.
    f.reject("task complete", json!({"artifact":artifact,"criteria":{"C1":[artifact]},"checks":{"offline":[artifact]},"approvals":{"owner":[artifact]},"reason":"extension is not approval"}), "completion blocked");
    f.apply("packet seal", next_context);
    let repaired = f.apply("artifact freeze", selection)["artifact"]
        .as_str()
        .unwrap()
        .to_owned();
    assert_ne!(artifact, repaired);
    f.reject(
        "packet seal",
        f.packet_spec(&repaired, 1),
        "rounds must be sequential",
    );
    let next = f.packet(&repaired, 2);
    for (id, agent) in [("A2", "alpha"), ("B2", "beta")] {
        f.prepare(id, agent, &next);
        f.finish_invocation(id);
        f.review(id, &repaired, &next);
    }
    f.reject("artifact freeze", json!({}), "round cap");
    let first_amendment = f.show()["review_extensions"][0].clone();
    f.apply("task extend-review", extension(&next, &repaired, 2));
    assert_eq!(f.show()["review_extensions"][0], first_amendment);
    assert_eq!(f.show()["review_extensions"].as_array().unwrap().len(), 2);
    assert_eq!(f.complete(&repaired)["state"], "completed");
    f.reject(
        "task extend-review",
        extension(&next, &repaired, 3),
        "terminal",
    );
}
#[test]
fn review_extension_rejects_unauthorized_stale_incomplete_and_live_requests() {
    let mut f = Fixture::new();
    f.create();
    let a = f.freeze();
    let p = f.packet(&a, 0);
    f.reject(
        "task extend-review",
        extension(&p, &a, 1),
        "at effective cap",
    );
    for (id, agent) in [("A", "alpha"), ("B", "beta")] {
        f.prepare(id, agent, &p);
        f.finish_invocation(id);
        f.review(id, &a, &p);
    }
    fs::write(f.repo.join("file.txt"), "repair\n").unwrap();
    let a = f.freeze();
    let p = f.packet(&a, 1);
    f.prepare("A1", "alpha", &p);
    f.prepare("B1", "beta", &p);
    f.finish_invocation("A1");
    f.review("A1", &a, &p);
    let spec = extension(&p, &a, 1);
    f.reject(
        "task extend-review",
        spec.clone(),
        "finish every required reviewer",
    );
    f.finish_invocation("B1");
    f.reject(
        "task extend-review",
        spec.clone(),
        "finish every required reviewer",
    );
    f.review("B1", &a, &p);
    let before = f.show();
    let mut missing = spec.clone();
    missing.as_object_mut().unwrap().remove("decision_evidence");
    f.reject("task extend-review", missing, "missing field");
    for (field, value, error) in [
        (
            "decision_evidence",
            json!([]),
            "evidence references required",
        ),
        ("decision_evidence", json!(["unknown"]), "unknown evidence"),
        ("authority", json!("intruder"), "authority/actor"),
        ("previous_limit", json!(0), "stale previous"),
        ("packet", json!("old-packet"), "stale latest"),
        ("new_limit", json!(1), "exactly previous + 1"),
        ("new_limit", json!(0), "exactly previous + 1"),
        ("new_limit", json!(3), "exactly previous + 1"),
        ("reason", json!("  "), "reason must be nonempty"),
    ] {
        let mut bad = spec.clone();
        bad[field] = value;
        f.reject("task extend-review", bad, error);
    }
    let path = f.file(spec.clone());
    let unauthorized = Command::new(env!("CARGO_BIN_EXE_agents-collab"))
        .args([
            "task",
            "extend-review",
            "--json",
            "--actor",
            "intruder",
            "--key",
            "bad-actor",
            "--expect",
            &f.rev.to_string(),
        ])
        .arg("--record")
        .arg(&f.record)
        .arg("--input")
        .arg(path)
        .output()
        .unwrap();
    assert!(!unauthorized.status.success());
    assert!(
        body(&unauthorized)["error"]["message"]
            .as_str()
            .unwrap()
            .contains("authority/actor")
    );
    assert_eq!(f.show(), before);
    // Legitimately recorded live work on an older writer blocks even a completed capped round.
    // Use the engine's observation support for newly discovered liveness on a historical writer.
    let mut g = Fixture::new();
    g.create();
    let a0 = g.freeze();
    let mut context = g.packet_spec(&a0, 0);
    context["purpose"] = json!("writer_context");
    let wp = g.apply("packet seal", context)["packet"]
        .as_str()
        .unwrap()
        .to_owned();
    g.apply("assignment prepare", json!({"id":"W","packet":wp,"agent":"writer","role":"writer","editable_scope":["file.txt"],"output_destination":"private-writer"}));
    g.finish_invocation("W");
    let (a, p) = review_at_cap(&mut g, true);
    g.apply("assignment observe", g.receipt("W", "running"));
    g.reject(
        "task extend-review",
        extension(&p, &a, 1),
        "nonterminal invocation",
    );
    g.apply("task cancel", json!({"reason":"owner cancels"}));
    g.reject("task extend-review", extension(&p, &a, 1), "terminal");
}
#[test]
fn review_extension_upgrade_faults_idempotency_and_handoff_never_downgrade() {
    for prior_version in [1, 2] {
        let mut f = quota_fixture();
        f.create();
        let (a, p) = review_at_cap(&mut f, true);
        // Exercise the actual historical SQL constraints and state bodies.
        let db = rusqlite::Connection::open(f.record.join("state.sqlite3")).unwrap();
        let mut state = f.show();
        state["schema_version"] = json!(prior_version);
        db.execute_batch(&format!("ALTER TABLE state RENAME TO old_state; CREATE TABLE state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema_version INTEGER NOT NULL CHECK(schema_version IN ({})), revision INTEGER NOT NULL, body TEXT NOT NULL); INSERT INTO state SELECT singleton,{},revision,body FROM old_state; DROP TABLE old_state;", if prior_version == 1 { "1" } else { "1,2" }, prior_version)).unwrap();
        db.execute(
            "UPDATE state SET body=?",
            [serde_json::to_string(&state).unwrap()],
        )
        .unwrap();
        let before = f.show();
        let input = f.file(extension(&p, &a, 1));
        let expected = f.rev;
        let failed = execute(
            "task extend-review",
            &f.record,
            Some(&input),
            Some("extension"),
            Some(expected),
            None,
            Some("before-commit"),
        );
        assert!(!failed.status.success());
        assert_eq!(f.show(), before);
        let version: i64 = db
            .query_row("SELECT schema_version FROM state", [], |r| r.get(0))
            .unwrap();
        assert_eq!(version, prior_version);
        let committed = execute(
            "task extend-review",
            &f.record,
            Some(&input),
            Some("extension"),
            Some(expected),
            None,
            Some("after-commit"),
        );
        assert!(!committed.status.success());
        assert_eq!(f.show()["schema_version"], 3);
        let replay = good(&execute(
            "task extend-review",
            &f.record,
            Some(&input),
            Some("extension"),
            Some(expected),
            None,
            None,
        ));
        f.rev = replay["revision"].as_u64().unwrap();
        assert_eq!(f.show()["review_extensions"].as_array().unwrap().len(), 1);
        let version: i64 = db
            .query_row("SELECT schema_version FROM state", [], |r| r.get(0))
            .unwrap();
        assert_eq!(version, 3); // prior engines admit only 1/2 before decoding state
        if let Some(old_binary) = std::env::var_os("AGENTS_COLLAB_OLD_TEST_BINARY") {
            let before_bytes = fs::read(f.record.join("state.sqlite3")).unwrap();
            let old = Command::new(old_binary)
                .args(["task", "show", "--json", "--record"])
                .arg(&f.record)
                .output()
                .unwrap();
            assert!(!old.status.success());
            assert!(
                body(&old)["error"]["message"]
                    .as_str()
                    .unwrap()
                    .contains("unsupported schema")
            );
            assert_eq!(
                fs::read(f.record.join("state.sqlite3")).unwrap(),
                before_bytes
            );
        }
        let stale = execute(
            "task extend-review",
            &f.record,
            Some(&input),
            Some("different-key"),
            Some(expected),
            None,
            None,
        );
        assert!(
            body(&stale)["error"]["message"]
                .as_str()
                .unwrap()
                .contains("stale revision")
        );
        let mut altered = extension(&p, &a, 1);
        altered["reason"] = json!("different decision");
        let changed_input = f.file(altered);
        let conflict = execute(
            "task extend-review",
            &f.record,
            Some(&changed_input),
            Some("extension"),
            Some(expected),
            None,
            None,
        );
        assert!(
            body(&conflict)["error"]["message"]
                .as_str()
                .unwrap()
                .contains("idempotency key conflicts")
        );
        fs::write(f.repo.join("file.txt"), "additional repair\n").unwrap();
        let new_artifact = f.freeze();
        let packet = f.packet(&new_artifact, 2);
        f.prepare("A2", "alpha", &packet);
        interrupt_absent(&mut f, "A2");
        f.apply(
            "assignment handoff",
            handoff_spec("A2", "new-codex", &packet, &new_artifact),
        );
        assert_eq!(f.show()["schema_version"], 3);
        let version: i64 = db
            .query_row("SELECT schema_version FROM state", [], |r| r.get(0))
            .unwrap();
        assert_eq!(version, 3);
    }
}

fn head(repo: &Path) -> String {
    let out = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(["rev-parse", "HEAD"])
        .output()
        .unwrap();
    assert!(out.status.success());
    String::from_utf8(out.stdout).unwrap().trim().to_owned()
}
fn accept_spec(f: &Fixture, artifact: &str) -> Value {
    json!({"artifact":artifact,"commit":head(&f.repo),"authority":"owner",
        "decision_evidence":[artifact],"reason":"Explicitly bind reviewed staged work to its descendant commit"})
}
fn passing_pair(f: &mut Fixture, artifact: &str, round: u64) -> String {
    let packet = f.packet(artifact, round);
    for (prefix, agent) in [("A", "alpha"), ("B", "beta")] {
        let id = format!("{prefix}{round}");
        f.prepare(&id, agent, &packet);
        f.finish_invocation(&id);
        f.review(&id, artifact, &packet);
    }
    packet
}
fn staged_review(omitted: bool) -> (Fixture, String) {
    let mut f = Fixture::new();
    f.create();
    f.apply("task activate", json!({"reason":"start"}));
    fs::write(f.repo.join("file.txt"), "reviewed staged change\n").unwrap();
    git(&f.repo, &["add", "file.txt"]);
    let a = if omitted {
        f.apply("artifact freeze", json!({"paths":["file.txt"],"omissions":{".gitignore":"unchanged infrastructure","deleted.txt":"unchanged fixture"},"acknowledged_sensitive":[],"quiescence":"writer stopped","atomic_required":false,"base":"HEAD"}))["artifact"].as_str().unwrap().to_owned()
    } else {
        f.freeze()
    };
    passing_pair(&mut f, &a, 0);
    (f, a)
}
fn completion_spec(a: &str) -> Value {
    json!({"artifact":a,"criteria":{"C1":[a]},"checks":{"offline":[a]},"approvals":{"owner":[a]},"reason":"Complete reviewed work"})
}
#[test]
fn explicit_commit_acceptance_preserves_history_and_closes_blocked_task() {
    let (mut f, a) = staged_review(true);
    git(&f.repo, &["commit", "-qm", "reviewed change"]);
    f.reject(
        "task complete",
        completion_spec(&a),
        "live source identity changed",
    );
    f.apply("task block", json!({"reason":"post-commit identity drift"}));
    let before = f.show();
    let original_objects: Vec<_> = before["objects"]
        .as_object()
        .unwrap()
        .keys()
        .map(|id| {
            (
                id.clone(),
                fs::read(f.record.join("objects").join(id)).unwrap(),
            )
        })
        .collect();
    let accepted = f.apply("task accept-commit", accept_spec(&f, &a));
    assert!(accepted["commit_acceptance"].is_string());
    let after = f.show();
    for field in [
        "spec",
        "profile",
        "profile_hash",
        "created_at",
        "state",
        "reason",
        "artifacts",
        "current_artifact",
        "packets",
        "assignments",
        "reviews",
        "findings",
        "invalid_results",
        "completion",
        "review_extensions",
    ] {
        assert_eq!(after[field], before[field], "changed {field}");
    }
    assert_eq!(
        &after["events"].as_array().unwrap()[..before["events"].as_array().unwrap().len()],
        before["events"].as_array().unwrap()
    );
    for (id, bytes) in original_objects {
        assert_eq!(after["objects"][&id], before["objects"][&id]);
        assert_eq!(fs::read(f.record.join("objects").join(id)).unwrap(), bytes);
    }
    assert_eq!(after["schema_version"], 4);
    assert_eq!(after["commit_acceptances"].as_array().unwrap().len(), 1);
    f.reject("task accept-commit", accept_spec(&f, &a), "already has");
    f.reject("task complete", completion_spec(&a), "only active");
    f.apply(
        "task reconcile",
        json!({"reason":"verify retained binding"}),
    );
    f.apply(
        "task activate",
        json!({"reason":"explicitly resume after acceptance"}),
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
    assert_eq!(checked["completion_blockers"], json!([]));
    assert_eq!(f.complete(&a)["state"], "completed");
    f.reject("task accept-commit", accept_spec(&f, &a), "terminal");
}

#[test]
fn commit_acceptance_rejects_omitted_tree_drift_unstaged_work_and_hidden_dirty_files() {
    for scenario in [
        "omitted-commit",
        "unstaged-review",
        "unstaged-mode",
        "dirty",
        "untracked",
        "assume-unchanged",
        "skip-worktree",
        "wrong-head",
        "unrelated",
        "changed-stage",
        "missing-source",
        "ignored-selected",
    ] {
        let (mut f, a) = if ["unstaged-review", "unstaged-mode", "ignored-selected"]
            .contains(&scenario)
        {
            let mut f = Fixture::new();
            f.create();
            f.apply("task activate", json!({"reason":"start"}));
            if scenario == "unstaged-review" {
                fs::write(f.repo.join("file.txt"), "reviewed but not staged\n").unwrap();
            } else if scenario == "unstaged-mode" {
                fs::set_permissions(f.repo.join("file.txt"), fs::Permissions::from_mode(0o755))
                    .unwrap();
            } else {
                fs::write(f.repo.join("ignored.txt"), "ignored evidence\n").unwrap();
            }
            let a = if scenario == "ignored-selected" {
                f.apply("artifact freeze", json!({"paths":[".gitignore","deleted.txt","file.txt","ignored.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"writer stopped","atomic_required":false,"base":"HEAD"}))["artifact"].as_str().unwrap().to_owned()
            } else {
                f.freeze()
            };
            passing_pair(&mut f, &a, 0);
            if scenario != "ignored-selected" {
                git(&f.repo, &["add", "file.txt"]);
            }
            (f, a)
        } else {
            staged_review(true)
        };
        if scenario == "omitted-commit" {
            fs::write(f.repo.join("deleted.txt"), "unreviewed omitted change\n").unwrap();
            git(&f.repo, &["add", "deleted.txt"]);
        }
        let old_head = head(&f.repo);
        git(&f.repo, &["commit", "--allow-empty", "-qm", "commit"]);
        let mut input = accept_spec(&f, &a);
        let expected = match scenario {
            "omitted-commit" | "unstaged-review" | "unstaged-mode" => {
                "complete frozen index changed"
            }
            "dirty" => {
                fs::write(f.repo.join("deleted.txt"), "dirty omitted file\n").unwrap();
                "tracked working bytes"
            }
            "untracked" => {
                fs::write(f.repo.join("extra.txt"), "extra\n").unwrap();
                "requires clean"
            }
            "assume-unchanged" | "skip-worktree" => {
                git(
                    &f.repo,
                    &["update-index", &format!("--{scenario}"), "deleted.txt"],
                );
                fs::write(f.repo.join("deleted.txt"), "hidden dirty omitted file\n").unwrap();
                "tracked working bytes"
            }
            "wrong-head" => {
                input["commit"] = json!(old_head);
                "current HEAD"
            }
            "unrelated" => {
                let tree = Command::new("git")
                    .arg("-C")
                    .arg(&f.repo)
                    .args(["rev-parse", "HEAD^{tree}"])
                    .output()
                    .unwrap();
                let out = Command::new("git")
                    .arg("-C")
                    .arg(&f.repo)
                    .args([
                        "commit-tree",
                        String::from_utf8(tree.stdout).unwrap().trim(),
                        "-m",
                        "unrelated root",
                    ])
                    .output()
                    .unwrap();
                assert!(out.status.success());
                let commit = String::from_utf8(out.stdout).unwrap();
                git(&f.repo, &["reset", "--hard", commit.trim()]);
                input["commit"] = json!(head(&f.repo));
                "Git inspection failed"
            }
            "changed-stage" => {
                fs::write(f.repo.join("deleted.txt"), "different stage\n").unwrap();
                git(&f.repo, &["add", "deleted.txt"]);
                "complete frozen index changed"
            }
            "missing-source" => {
                fs::rename(&f.repo, f.repo.with_file_name("moved")).unwrap();
                "No such file"
            }
            "ignored-selected" => {
                fs::write(f.repo.join("ignored.txt"), "changed ignored evidence\n").unwrap();
                "selected reviewed working"
            }
            _ => unreachable!(),
        };
        let before = f.show();
        f.reject("task accept-commit", input, expected);
        assert_eq!(f.show(), before, "failed acceptance mutated {scenario}");
    }
}

#[test]
fn acceptance_handles_staged_deletion_executable_and_symlink_and_rejects_later_drift() {
    let mut f = Fixture::new();
    f.create();
    f.apply("task activate", json!({"reason":"start"}));
    fs::remove_file(f.repo.join("deleted.txt")).unwrap();
    fs::set_permissions(f.repo.join("file.txt"), fs::Permissions::from_mode(0o755)).unwrap();
    symlink("file.txt", f.repo.join("link.txt")).unwrap();
    git(&f.repo, &["add", "-A"]);
    let a = f.apply("artifact freeze", json!({"paths":[".gitignore","deleted.txt","file.txt","link.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"writer stopped","atomic_required":false,"base":"HEAD"}))["artifact"].as_str().unwrap().to_owned();
    passing_pair(&mut f, &a, 0);
    git(&f.repo, &["commit", "-qm", "reviewed types and modes"]);
    f.apply("task accept-commit", accept_spec(&f, &a));
    for scenario in ["mode", "link", "deletion", "head"] {
        match scenario {
            "mode" => {
                fs::set_permissions(f.repo.join("file.txt"), fs::Permissions::from_mode(0o644))
                    .unwrap()
            }
            "link" => {
                fs::remove_file(f.repo.join("link.txt")).unwrap();
                symlink("deleted.txt", f.repo.join("link.txt")).unwrap();
            }
            "deletion" => fs::write(f.repo.join("deleted.txt"), "restored\n").unwrap(),
            "head" => git(&f.repo, &["commit", "--allow-empty", "-qm", "later commit"]),
            _ => unreachable!(),
        }
        let check = good(&execute(
            "task check",
            &f.record,
            None,
            None,
            None,
            None,
            None,
        ));
        assert!(!check["completion_blockers"].as_array().unwrap().is_empty());
        let input = f.file(completion_spec(&a));
        assert!(
            !execute(
                "task complete",
                &f.record,
                Some(&input),
                Some(scenario),
                Some(f.rev),
                None,
                None
            )
            .status
            .success()
        );
        f.apply("task block", json!({"reason":"drift observed"}));
        for cmd in ["task activate", "task reconcile"] {
            let input = f.file(json!({"reason":"must verify binding"}));
            assert!(
                !execute(
                    cmd,
                    &f.record,
                    Some(&input),
                    Some(&format!("{cmd}-{scenario}")),
                    Some(f.rev),
                    None,
                    None
                )
                .status
                .success()
            );
        }
        match scenario {
            "mode" => {
                fs::set_permissions(f.repo.join("file.txt"), fs::Permissions::from_mode(0o755))
                    .unwrap()
            }
            "link" => {
                fs::remove_file(f.repo.join("link.txt")).unwrap();
                symlink("file.txt", f.repo.join("link.txt")).unwrap();
            }
            "deletion" => fs::remove_file(f.repo.join("deleted.txt")).unwrap(),
            "head" => git(&f.repo, &["reset", "--hard", "HEAD~1"]),
            _ => unreachable!(),
        }
        f.apply(
            "task activate",
            json!({"reason":"original bound source restored"}),
        );
    }
    assert_eq!(f.complete(&a)["state"], "completed");
}

#[test]
fn acceptance_requires_authority_current_artifact_reviews_and_all_assignment_gates() {
    let (mut f, a) = staged_review(false);
    git(&f.repo, &["commit", "-qm", "reviewed"]);
    for (field, value, error) in [
        ("authority", json!("stranger"), "authority/actor"),
        ("artifact", json!("wrong"), "artifact mismatch"),
        ("reason", json!(" "), "nonempty"),
        ("decision_evidence", json!([]), "evidence references"),
        ("commit", json!(&head(&f.repo)[..8]), "exact full commit"),
    ] {
        let mut spec = accept_spec(&f, &a);
        spec[field] = value;
        f.reject("task accept-commit", spec, error);
    }
    for state in [
        "prepared",
        "launching",
        "running",
        "unknown",
        "blocked",
        "interrupted",
    ] {
        let mut f = Fixture::new();
        f.create();
        f.apply("task activate", json!({"reason":"start"}));
        fs::write(f.repo.join("file.txt"), "staged change\n").unwrap();
        git(&f.repo, &["add", "file.txt"]);
        let a = f.freeze();
        let packet = f.packet(&a, 0);
        f.prepare("A", "alpha", &packet);
        f.finish_invocation("A");
        f.review("A", &a, &packet);
        f.prepare("extra", "beta", &packet);
        if state != "prepared" {
            f.apply("assignment observe", f.receipt("extra", "launching"));
            if state != "launching" {
                f.apply("assignment observe", f.receipt("extra", state));
            }
        }
        git(&f.repo, &["commit", "-qm", "reviewed"]);
        f.reject(
            "task accept-commit",
            accept_spec(&f, &a),
            "commit acceptance blocked",
        );
    }
    for verdict in ["missing", "changes_required", "material"] {
        let mut f = Fixture::new();
        f.create();
        f.apply("task activate", json!({"reason":"start"}));
        let a = f.freeze();
        let p = f.packet(&a, 0);
        for (id, agent) in [("A", "alpha"), ("B", "beta")] {
            f.prepare(id, agent, &p);
            f.finish_invocation(id);
            if verdict == "missing" && id == "B" {
                continue;
            }
            let mut r = f.review_spec(id, &a, &p);
            if id == "A" && verdict == "changes_required" {
                r["verdict"] = json!("changes_required");
            }
            if id == "A" && verdict == "material" {
                r["verdict"] = json!("changes_required");
                r["findings"] = json!([{"id":"F1","location":"file.txt","scenario":"synthetic material risk","evidence":"fixture","uncertainty":"none","material":true,"recommendation":"resolve"}]);
            }
            f.apply("review import", r);
        }
        git(&f.repo, &["commit", "--allow-empty", "-qm", "descendant"]);
        f.reject(
            "task accept-commit",
            accept_spec(&f, &a),
            "commit acceptance blocked",
        );
    }
}

#[test]
fn acceptance_migrates_legacy_formats_atomically_and_replays_without_duplicate_binding() {
    for prior in [1, 2, 3] {
        let (mut f, a) = staged_review(false);
        let db = rusqlite::Connection::open(f.record.join("state.sqlite3")).unwrap();
        let mut state = f.show();
        state["schema_version"] = json!(prior);
        let versions = (1..=prior)
            .map(|n| n.to_string())
            .collect::<Vec<_>>()
            .join(",");
        db.execute_batch(&format!("ALTER TABLE state RENAME TO old_state; CREATE TABLE state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema_version INTEGER NOT NULL CHECK(schema_version IN ({versions})), revision INTEGER NOT NULL, body TEXT NOT NULL); INSERT INTO state SELECT singleton,{prior},revision,body FROM old_state; DROP TABLE old_state;")).unwrap();
        db.execute(
            "UPDATE state SET body=?",
            [serde_json::to_string(&state).unwrap()],
        )
        .unwrap();
        git(&f.repo, &["commit", "-qm", "reviewed"]);
        let before = f.show();
        let input = f.file(accept_spec(&f, &a));
        let expected = f.rev;
        let failed = execute(
            "task accept-commit",
            &f.record,
            Some(&input),
            Some("accept"),
            Some(expected),
            None,
            Some("before-commit"),
        );
        assert!(!failed.status.success());
        assert_eq!(f.show(), before);
        let version: i64 = db
            .query_row("SELECT schema_version FROM state", [], |r| r.get(0))
            .unwrap();
        assert_eq!(version, prior);
        let committed = execute(
            "task accept-commit",
            &f.record,
            Some(&input),
            Some("accept"),
            Some(expected),
            None,
            Some("after-commit"),
        );
        assert!(!committed.status.success());
        let replay = good(&execute(
            "task accept-commit",
            &f.record,
            Some(&input),
            Some("accept"),
            Some(expected),
            None,
            None,
        ));
        f.rev = replay["revision"].as_u64().unwrap();
        assert_eq!(f.show()["commit_acceptances"].as_array().unwrap().len(), 1);
        let version: i64 = db
            .query_row("SELECT schema_version FROM state", [], |r| r.get(0))
            .unwrap();
        assert_eq!(version, 4);
        let stale = execute(
            "task accept-commit",
            &f.record,
            Some(&input),
            Some("stale"),
            Some(expected),
            None,
            None,
        );
        assert!(
            body(&stale)["error"]["message"]
                .as_str()
                .unwrap()
                .contains("stale revision")
        );
        let mut altered = accept_spec(&f, &a);
        altered["reason"] = json!("different request");
        let altered = f.file(altered);
        let conflict = execute(
            "task accept-commit",
            &f.record,
            Some(&altered),
            Some("accept"),
            Some(expected),
            None,
            None,
        );
        assert!(
            body(&conflict)["error"]["message"]
                .as_str()
                .unwrap()
                .contains("idempotency key conflicts")
        );
        if let Some(old) = std::env::var_os("AGENTS_COLLAB_PRE_ACCEPT_TEST_BINARY") {
            let bytes = fs::read(f.record.join("state.sqlite3")).unwrap();
            let out = Command::new(old)
                .args(["task", "show", "--json", "--record"])
                .arg(&f.record)
                .output()
                .unwrap();
            assert!(!out.status.success());
            assert!(
                body(&out)["error"]["message"]
                    .as_str()
                    .unwrap()
                    .contains("unsupported schema")
            );
            assert_eq!(fs::read(f.record.join("state.sqlite3")).unwrap(), bytes);
        }
        // Read-only frozen evidence remains usable even if the checkout vanishes.
        fs::rename(&f.repo, f.repo.with_file_name("moved")).unwrap();
        assert_eq!(f.show()["artifacts"], before["artifacts"]);
        let p =
            f.file(json!({"fields":["commit_acceptances","current_commit_acceptance","reviews"]}));
        good(&execute(
            "task export",
            &f.record,
            Some(&p),
            None,
            None,
            None,
            None,
        ));
    }
}

#[test]
fn new_artifact_invalidates_binding_and_later_review_extension_never_downgrades_format() {
    let (mut f, a) = staged_review(false);
    git(&f.repo, &["commit", "-qm", "reviewed"]);
    f.apply("task accept-commit", accept_spec(&f, &a));
    let bindings = f.show()["commit_acceptances"].clone();
    fs::write(f.repo.join("file.txt"), "new work\n").unwrap();
    let next = f.freeze();
    assert_ne!(next, a);
    assert!(f.show()["current_commit_acceptance"].is_null());
    assert_eq!(f.show()["commit_acceptances"], bindings);
    f.reject(
        "task complete",
        completion_spec(&next),
        "completion blocked",
    );
    let p = passing_pair(&mut f, &next, 1);
    f.apply("task extend-review", extension(&p, &next, 1));
    assert_eq!(f.show()["schema_version"], 4);
    let db = rusqlite::Connection::open(f.record.join("state.sqlite3")).unwrap();
    let v: i64 = db
        .query_row("SELECT schema_version FROM state", [], |r| r.get(0))
        .unwrap();
    assert_eq!(v, 4);
    assert_eq!(f.complete(&next)["state"], "completed");
}

#[test]
fn acceptance_double_scan_rejects_concurrent_omitted_worktree_change() {
    use std::io::{BufRead, BufReader};
    let (mut f, a) = staged_review(true);
    git(&f.repo, &["commit", "-qm", "reviewed"]);
    let before = f.show();
    let input = f.file(accept_spec(&f, &a));
    let mut child = Command::new(env!("CARGO_BIN_EXE_agents-collab"))
        .args(["task", "accept-commit", "--json", "--record"])
        .arg(&f.record)
        .arg("--input")
        .arg(input)
        .args([
            "--key",
            "concurrent-accept",
            "--actor",
            "owner",
            "--expect",
            &f.rev.to_string(),
        ])
        .env("AGENTS_COLLAB_ACCEPT_COMMIT_PAUSE", "test")
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap();
    let mut line = String::new();
    BufReader::new(child.stderr.take().unwrap())
        .read_line(&mut line)
        .unwrap();
    assert!(line.contains("accept-commit-scanned-test-gate"));
    fs::write(f.repo.join("deleted.txt"), "concurrent omitted change\n").unwrap();
    let out = child.wait_with_output().unwrap();
    assert!(!out.status.success());
    assert!(
        body(&out)["error"]["message"]
            .as_str()
            .unwrap()
            .contains("tracked working bytes")
    );
    assert_eq!(f.show(), before);
}

#[test]
fn acceptance_rejects_head_tree_mismatch_unstaged_only_evidence_and_filesystem_aliases() {
    for scenario in ["tree", "unstaged-only", "ignored", "hardlink"] {
        let (mut f, a) = if scenario == "tree" {
            staged_review(true)
        } else {
            let mut f = Fixture::new();
            f.create();
            f.apply("task activate", json!({"reason":"start"}));
            if scenario == "unstaged-only" {
                fs::write(f.repo.join("file.txt"), "unstaged evidence\n").unwrap();
            } else if scenario == "ignored" {
                fs::write(f.repo.join("ignored.txt"), "ignored evidence\n").unwrap();
            } else {
                fs::remove_file(f.repo.join("deleted.txt")).unwrap();
                fs::hard_link(f.repo.join("file.txt"), f.repo.join("deleted.txt")).unwrap();
                git(&f.repo, &["add", "deleted.txt"]);
            }
            let a = if scenario == "ignored" {
                f.apply("artifact freeze", json!({"paths":[".gitignore","deleted.txt","file.txt","ignored.txt"],"omissions":{},"acknowledged_sensitive":[],"quiescence":"writer stopped","atomic_required":false,"base":"HEAD"}))["artifact"].as_str().unwrap().to_owned()
            } else {
                f.freeze()
            };
            passing_pair(&mut f, &a, 0);
            (f, a)
        };
        let expected = if scenario == "tree" {
            let reviewed_index = f.inputs.join("reviewed-index");
            fs::copy(f.repo.join(".git/index"), &reviewed_index).unwrap();
            fs::write(f.repo.join("deleted.txt"), "unreviewed tree content\n").unwrap();
            git(&f.repo, &["add", "deleted.txt"]);
            git(&f.repo, &["commit", "-qm", "different tree"]);
            fs::copy(reviewed_index, f.repo.join(".git/index")).unwrap();
            fs::write(f.repo.join("deleted.txt"), "old\n").unwrap();
            "entire committed tree differs"
        } else {
            if scenario == "unstaged-only" {
                git(&f.repo, &["restore", "file.txt"]);
            }
            git(&f.repo, &["commit", "--allow-empty", "-qm", "descendant"]);
            match scenario {
                "unstaged-only" => "selected reviewed working bytes",
                "ignored" => "selected reviewed work was not staged",
                "hardlink" => "unsafe filesystem path alias",
                _ => unreachable!(),
            }
        };
        let before = f.show();
        f.reject("task accept-commit", accept_spec(&f, &a), expected);
        assert_eq!(before, f.show());
    }
}
