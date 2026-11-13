#![cfg(unix)]
mod profile;
mod snapshot;
mod storage;
use anyhow::{Context, Result, bail, ensure};
use profile::Profile;
use rusqlite::{Connection, OptionalExtension, TransactionBehavior, params};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File},
    os::unix::fs::PermissionsExt,
    path::{Path, PathBuf},
    time::Duration,
};
use storage::*;

pub struct Request {
    pub command: String,
    pub record: Option<PathBuf>,
    pub input: Option<PathBuf>,
    pub profile: Option<PathBuf>,
    pub key: Option<String>,
    pub expect: Option<u64>,
    pub actor: Option<String>,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Requirement {
    id: String,
    text: String,
    source: String,
    kind: String,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct TaskSpec {
    schema_version: u64,
    project: String,
    task: String,
    repository: PathBuf,
    requirements: Vec<Requirement>,
    authority_boundaries: Vec<String>,
    writer: String,
    editable_scope: Vec<String>,
    reviewers: Vec<String>,
    required_checks: Vec<String>,
    required_approvals: Vec<String>,
    decision_authorities: Vec<String>,
}
#[derive(Clone, Serialize, Deserialize)]
struct Artifact {
    id: String,
    created_at: u64,
    actor: String,
    manifest: snapshot::Manifest,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Evidence {
    category: String,
    description: String,
    object: String,
}
fn review_purpose() -> String {
    "review".into()
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PacketSpec {
    #[serde(default = "review_purpose")]
    purpose: String,
    artifact: String,
    round: u64,
    instructions: String,
    access_policy: String,
    coverage: BTreeMap<String, Vec<String>>,
    evidence: Vec<Evidence>,
    neutral_initial: bool,
}
#[derive(Clone, Serialize, Deserialize)]
struct Packet {
    id: String,
    created_at: u64,
    actor: String,
    spec: PacketSpec,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AssignmentSpec {
    id: String,
    packet: String,
    agent: String,
    role: String,
    editable_scope: Vec<String>,
    output_destination: String,
}
#[derive(Clone, Serialize, Deserialize)]
struct Observation {
    at: u64,
    receipt: Receipt,
    raw: String,
}
#[derive(Clone, Serialize, Deserialize)]
struct Assignment {
    spec: AssignmentSpec,
    created_at: u64,
    actor: String,
    requested: profile::Agent,
    state: String,
    launch_at: Option<u64>,
    deadline: Option<u64>,
    observations: Vec<Observation>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    continuation: Option<Continuation>,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct HandoffSpec {
    assignment: String,
    replacement: String,
    packet: String,
    agent: String,
    // Only a missing frozen-profile identity may be explicitly selected locally.
    selection: Option<profile::Agent>,
    output_destination: String,
    decision: String,
    authority: String,
    decision_evidence: Vec<String>,
    reason: String,
    previous_invocation: String,
    timing: String,
    instructions: String,
    partial_work: Option<snapshot::Selection>,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ReviewExtensionSpec {
    packet: String,
    previous_limit: u64,
    new_limit: u64,
    authority: String,
    decision_evidence: Vec<String>,
    reason: String,
}
#[derive(Clone, Serialize, Deserialize)]
struct ReviewExtension {
    spec: ReviewExtensionSpec,
    at: u64,
    actor: String,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct CommitAcceptanceSpec {
    artifact: String,
    commit: String,
    authority: String,
    decision_evidence: Vec<String>,
    reason: String,
}
#[derive(Clone, Serialize, Deserialize)]
struct CommitAcceptance {
    id: String,
    spec: CommitAcceptanceSpec,
    at: u64,
    actor: String,
    manifest: snapshot::Manifest,
}
#[derive(Clone, Serialize, Deserialize)]
struct Continuation {
    handoff: HandoffSpec,
    original_requested: profile::Agent,
    preserved_work: Option<String>,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Receipt {
    schema_version: u64,
    assignment: String,
    state: String,
    invocation: Option<String>,
    process_start: Option<String>,
    interface_model: Option<String>,
    interface_effort: Option<String>,
    observed_model: Option<String>,
    observed_effort: Option<String>,
    boundary_observations: String,
    exit_code: Option<i64>,
    reason: String,
    reconciled: bool,
    absence_established: bool,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct FindingSpec {
    id: String,
    location: String,
    scenario: String,
    evidence: String,
    uncertainty: String,
    material: bool,
    recommendation: String,
}
#[derive(Clone, Serialize, Deserialize)]
struct Finding {
    spec: FindingSpec,
    review: String,
    artifact: String,
    disposition: Option<Disposition>,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ReviewSpec {
    schema_version: u64,
    assignment: String,
    artifact: String,
    packet: String,
    verdict: String,
    verification: Vec<Evidence>,
    limits: String,
    findings: Vec<FindingSpec>,
    fresh_session: String,
    automatic_context: String,
    tool_boundary: String,
}
#[derive(Clone, Serialize, Deserialize)]
struct Review {
    id: String,
    at: u64,
    actor: String,
    spec: ReviewSpec,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Disposition {
    finding: String,
    decision: String,
    reason: String,
    evidence: Vec<String>,
    authority: String,
    criterion_compatible: bool,
}
#[derive(Clone, Serialize, Deserialize)]
struct Attempt {
    object: String,
    assignment: Option<String>,
    at: u64,
    error: String,
}
#[derive(Clone, Serialize, Deserialize)]
struct Event {
    operation: String,
    command: String,
    actor: String,
    at: u64,
    previous_revision: u64,
    revision: u64,
    input_hash: String,
}
#[derive(Clone, Serialize, Deserialize)]
struct State {
    schema_version: u64,
    spec: TaskSpec,
    profile: Profile,
    profile_hash: String,
    created_at: u64,
    state: String,
    revision: u64,
    reason: String,
    artifacts: Vec<Artifact>,
    current_artifact: Option<String>,
    packets: Vec<Packet>,
    assignments: Vec<Assignment>,
    reviews: Vec<Review>,
    findings: Vec<Finding>,
    invalid_results: Vec<Attempt>,
    objects: BTreeMap<String, String>,
    events: Vec<Event>,
    completion: Option<Value>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    review_extensions: Vec<ReviewExtension>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    commit_acceptances: Vec<CommitAcceptance>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    current_commit_acceptance: Option<String>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Lifecycle {
    reason: String,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Completion {
    artifact: String,
    criteria: BTreeMap<String, Vec<String>>,
    checks: BTreeMap<String, Vec<String>>,
    approvals: BTreeMap<String, Vec<String>>,
    reason: String,
}
fn nonempty(s: &str, label: &str) -> Result<()> {
    ensure!(!s.trim().is_empty(), "{label} must be nonempty");
    Ok(())
}
fn decode<T: serde::de::DeserializeOwned>(v: &Value) -> Result<T> {
    Ok(serde_json::from_value(v.clone())?)
}
fn register(s: &mut State, id: String, kind: &str) {
    s.objects.entry(id).or_insert_with(|| kind.into());
}
fn list_unique(v: &[String], label: &str) -> Result<()> {
    ensure!(
        v.iter().all(|x| !x.trim().is_empty())
            && v.iter().collect::<BTreeSet<_>>().len() == v.len(),
        "{label}: empty or duplicate value"
    );
    Ok(())
}
fn validate_task(t: &TaskSpec, p: &Profile) -> Result<()> {
    ensure!(t.schema_version == 1, "unsupported task schema");
    project_component(&t.project)?;
    component(&t.task)?;
    snapshot::repository(&t.repository)?;
    ensure!(
        !t.requirements.is_empty()
            && !t.authority_boundaries.is_empty()
            && !t.decision_authorities.is_empty(),
        "requirements, authority boundaries and decision authorities required"
    );
    let mut ids = BTreeSet::new();
    for r in &t.requirements {
        component(&r.id)?;
        ensure!(ids.insert(&r.id), "duplicate requirement");
        nonempty(&r.text, "requirement text")?;
        nonempty(&r.source, "requirement source")?;
        ensure!(
            ["requirement", "criterion", "safeguard"].contains(&r.kind.as_str()),
            "invalid requirement category"
        );
    }
    p.agent(&t.writer)?;
    list_unique(&t.editable_scope, "writer scope")?;
    for x in &t.editable_scope {
        relative(x)?;
    }
    list_unique(&t.reviewers, "reviewers")?;
    for n in &t.reviewers {
        let a = p.agent(n)?;
        ensure!(
            a.transport != "host" && n != &t.writer,
            "writer/host cannot be independent reviewer"
        );
    }
    if p.review.on_consequential_work == "single" {
        ensure!(
            !t.reviewers.is_empty(),
            "configured review requires reviewer"
        );
    }
    list_unique(&t.required_checks, "checks")?;
    list_unique(&t.required_approvals, "approvals")?;
    list_unique(&t.decision_authorities, "authorities")?;
    Ok(())
}
fn connection(root: &Path, create: bool) -> Result<Connection> {
    ensure!(root.is_absolute(), "record path must be absolute");
    no_links(root)?;
    outside_repository(root)?;
    ensure!(
        root.canonicalize()? == root,
        "record path must be canonical"
    );
    ensure!(root.is_dir(), "record directory unavailable");
    supported_storage(root)?;
    ensure!(
        fs::metadata(root)?.permissions().mode() & 0o077 == 0,
        "record directory must have private permissions (0700)"
    );
    // Resolve and check the project again on every open; no silently redirected records.
    let db = root.join("state.sqlite3");
    no_links(&db)?;
    ensure!(
        create || db.is_file(),
        "task database unavailable; no fallback"
    );
    let flags = rusqlite::OpenFlags::SQLITE_OPEN_READ_WRITE
        | if create {
            rusqlite::OpenFlags::SQLITE_OPEN_CREATE
        } else {
            rusqlite::OpenFlags::empty()
        };
    let c = Connection::open_with_flags(&db, flags)?;
    if !create {
        let version: i64 = c
            .query_row(
                "SELECT schema_version FROM state WHERE singleton=1",
                [],
                |r| r.get(0),
            )
            .context(
                "task missing or unsupported schema; preserve originals for explicit migration",
            )?;
        ensure!(
            matches!(version, 1..=4),
            "unsupported schema; explicit migration required"
        );
    }
    fs::set_permissions(&db, fs::Permissions::from_mode(0o600))?;
    c.busy_timeout(Duration::from_secs(5))?;
    c.pragma_update(None, "foreign_keys", "ON")?;
    c.pragma_update(None, "journal_mode", "DELETE")?;
    c.pragma_update(None, "synchronous", "FULL")?;
    if create {
        c.execute_batch("CREATE TABLE IF NOT EXISTS state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema_version INTEGER NOT NULL CHECK(schema_version IN (1,2,3,4)), revision INTEGER NOT NULL, body TEXT NOT NULL); CREATE TABLE IF NOT EXISTS operations (key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, response TEXT NOT NULL, revision INTEGER NOT NULL);")?;
    }
    Ok(c)
}
fn load(c: &Connection) -> Result<State> {
    let (version, body): (i64, String) = c
        .query_row(
            "SELECT schema_version, body FROM state WHERE singleton=1",
            [],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )
        .context("task missing or unsupported schema; explicit migration required")?;
    ensure!(
        matches!(version, 1..=4),
        "unsupported schema; explicit migration required"
    );
    let s: State = parse(body.as_bytes())?;
    ensure!(
        matches!(s.schema_version, 1..=4) && s.schema_version == version as u64,
        "unsupported state schema"
    );
    Ok(s)
}
fn outside_repository(root: &Path) -> Result<()> {
    for p in root.ancestors() {
        ensure!(
            !p.join(".git").exists(),
            "records cannot be inside any Git repository/worktree"
        );
    }
    Ok(())
}
fn validate_root(root: &Path, s: &State) -> Result<()> {
    outside_repository(root)?;
    let actual = root.canonicalize()?;
    ensure!(actual == root, "record path must be canonical");
    ensure!(
        !overlap(&actual, &s.spec.repository),
        "record/repository overlap"
    );
    if let Ok(live) = s.spec.repository.canonicalize() {
        ensure!(
            !overlap(&actual, &live),
            "record/repository overlap through current source alias"
        );
    }
    ensure!(
        root.file_name().is_some_and(|x| x == "collaboration")
            && root
                .parent()
                .and_then(Path::file_name)
                .is_some_and(|x| x == s.spec.task.as_str())
            && root
                .parent()
                .and_then(Path::parent)
                .and_then(Path::file_name)
                .is_some_and(|x| x == s.spec.project.as_str()),
        "record layout mismatch"
    );
    Ok(())
}
fn live_source(s: &State) -> Value {
    match s.spec.repository.canonicalize() {
        Ok(p) => json!({"status":"available","path":p,"live_identity_verified":false}),
        Err(e) => {
            json!({"status":"unavailable","reason":e.to_string(),"frozen_records":"retained; completion and capture require the live source"})
        }
    }
}
fn latest_review_packet(s: &State) -> Option<&Packet> {
    s.packets.iter().rev().find(|p| p.spec.purpose == "review")
}
fn refs(s: &State, v: &[String]) -> Result<()> {
    ensure!(!v.is_empty(), "evidence references required");
    for id in v {
        ensure!(s.objects.contains_key(id), "unknown evidence object");
    }
    Ok(())
}
fn terminal(a: &Assignment) -> bool {
    matches!(
        a.state.as_str(),
        "completed" | "interrupted" | "blocked" | "superseded"
    )
}
fn round_complete(s: &State, p: &Packet) -> bool {
    s.spec.reviewers.iter().all(|n| {
        s.reviews.iter().any(|r| {
            r.spec.packet == p.id
                && s.assignments
                    .iter()
                    .any(|a| a.spec.id == r.spec.assignment && a.spec.agent == *n)
        })
    })
}
fn blockers(s: &State) -> Vec<String> {
    let mut b = Vec::new();
    let current = s.current_artifact.as_deref().unwrap_or("");
    if current.is_empty() {
        b.push("no frozen artifact".into());
    }
    if !s.spec.reviewers.is_empty() {
        match latest_review_packet(s) {
            Some(p) if p.spec.artifact == current && round_complete(s, p) => {
                for r in s.reviews.iter().filter(|r| r.spec.packet == p.id) {
                    if r.spec.verdict != "pass" {
                        b.push(format!("review {} did not approve current artifact", r.id));
                    }
                }
            }
            _ => b.push("required reviewers have not completed same current identity".into()),
        }
    }
    for a in &s.assignments {
        if !terminal(a) {
            b.push(format!(
                "assignment {} invocation {} requires reconciliation",
                a.spec.id, a.state
            ));
        } else if a.state == "blocked" || a.state == "interrupted" {
            b.push(format!(
                "assignment {} blocked; authorized continuation/result required",
                a.spec.id
            ));
        }
    }
    for f in &s.findings {
        if f.spec.material
            && f.disposition
                .as_ref()
                .is_none_or(|d| d.decision == "unresolved" || !d.criterion_compatible)
        {
            b.push(format!(
                "material finding {} unresolved/incompatible",
                f.spec.id
            ));
        }
        if f.spec.material
            && f.disposition
                .as_ref()
                .is_some_and(|d| d.decision == "addressed")
            && f.artifact == current
        {
            b.push(format!(
                "finding {} needs repaired artifact and follow-up review",
                f.spec.id
            ));
        }
    }
    if s.state == "blocked" || s.state == "cancelled" {
        b.push(format!("task is {}", s.state));
    }
    b
}
fn effective_review_limit(s: &State) -> u64 {
    s.review_extensions
        .last()
        .map_or(s.profile.review.max_followup_rounds, |e| e.spec.new_limit)
}
fn extend_review(s: &mut State, input: &Value, actor: &str) -> Result<Value> {
    let extension: ReviewExtensionSpec = decode(input)?;
    ensure!(
        s.spec.decision_authorities.contains(&extension.authority) && actor == extension.authority,
        "declared decision authority/actor required; not authentication"
    );
    refs(s, &extension.decision_evidence)?;
    nonempty(&extension.reason, "review extension reason")?;
    let previous = effective_review_limit(s);
    ensure!(
        extension.previous_limit == previous,
        "stale previous review limit"
    );
    ensure!(
        previous.checked_add(1) == Some(extension.new_limit),
        "new review limit must be exactly previous + 1"
    );
    let packet = latest_review_packet(s).context("latest reviewed packet required")?;
    ensure!(
        extension.packet == packet.id,
        "stale latest reviewed packet"
    );
    ensure!(
        packet.spec.round == previous,
        "latest reviewed round must be at effective cap"
    );
    ensure!(
        round_complete(s, packet),
        "finish every required reviewer before extending review"
    );
    ensure!(
        s.assignments.iter().all(terminal),
        "nonterminal invocation blocks review extension"
    );
    s.review_extensions.push(ReviewExtension {
        spec: extension,
        at: now(),
        actor: actor.into(),
    });
    s.schema_version = s.schema_version.max(3);
    Ok(
        json!({"baseline_review_limit":s.profile.review.max_followup_rounds,
        "effective_review_limit":effective_review_limit(s), "amendment":s.review_extensions.last(),
        "authority_limit":"host declaration only; no review pass, implementation, release, waiver or policy approval"}),
    )
}
fn current_source(s: &State, artifact: &Artifact) -> Result<()> {
    if let Some(id) = &s.current_commit_acceptance {
        let binding = s
            .commit_acceptances
            .iter()
            .find(|b| &b.id == id)
            .context("missing commit acceptance binding")?;
        ensure!(
            binding.spec.artifact == artifact.id,
            "commit acceptance artifact mismatch"
        );
        let current =
            snapshot::accept_commit(&s.spec.repository, &artifact.manifest, &binding.spec.commit)?;
        ensure!(
            current == binding.manifest,
            "bound post-commit source identity changed"
        );
        Ok(())
    } else {
        snapshot::unchanged(&s.spec.repository, &artifact.manifest)
    }
}
fn check_bound_source(s: &State) -> Result<()> {
    if s.current_commit_acceptance.is_some() {
        let artifact = s
            .artifacts
            .iter()
            .find(|a| s.current_artifact.as_deref() == Some(&a.id))
            .context("missing bound artifact")?;
        current_source(s, artifact)?;
    }
    Ok(())
}
fn accept_commit(s: &mut State, root: &Path, input: &Value, actor: &str) -> Result<Value> {
    let spec: CommitAcceptanceSpec = decode(input)?;
    ensure!(
        ["active", "blocked"].contains(&s.state.as_str()),
        "only active/blocked task can accept commit"
    );
    ensure!(
        s.current_commit_acceptance.is_none(),
        "current artifact already has a commit acceptance"
    );
    ensure!(
        s.spec.decision_authorities.contains(&spec.authority) && actor == spec.authority,
        "declared decision authority/actor required; not authentication"
    );
    nonempty(&spec.reason, "commit acceptance reason")?;
    refs(s, &spec.decision_evidence)?;
    ensure!(
        s.current_artifact.as_deref() == Some(&spec.artifact),
        "commit acceptance artifact mismatch"
    );
    let gates: Vec<_> = blockers(s)
        .into_iter()
        .filter(|b| b != "task is blocked")
        .collect();
    ensure!(
        gates.is_empty(),
        "commit acceptance blocked: {}",
        gates.join("; ")
    );
    let artifact = s
        .artifacts
        .iter()
        .find(|a| a.id == spec.artifact)
        .context("missing frozen artifact")?;
    let manifest = snapshot::accept_commit(&s.spec.repository, &artifact.manifest, &spec.commit)?;
    // Retain the only new source object referenced by the post-commit manifest:
    // all selected content and index/base objects already belong to the artifact.
    let status = put(root, b"")?;
    ensure!(status == manifest.status, "accepted status must be clean");
    register(s, status, "task/accepted-clean-status");
    let at = now();
    let id = put(
        root,
        &encoded(&json!({"spec":spec,"at":at,"actor":actor,"manifest":manifest}))?,
    )?;
    register(s, id.clone(), "task/commit-acceptance");
    s.commit_acceptances.push(CommitAcceptance {
        id: id.clone(),
        spec,
        at,
        actor: actor.into(),
        manifest,
    });
    s.current_commit_acceptance = Some(id.clone());
    s.schema_version = s.schema_version.max(4);
    Ok(
        json!({"commit_acceptance":id,"binding":s.commit_acceptances.last(),
        "validation":"coordinated repeated source verification; declared authority only; no automatic activation or completion"}),
    )
}
fn summary(s: &State) -> Value {
    json!({"schema_version":1,"task":s.spec.task,"revision":s.revision,"state":s.state,"blockers":blockers(s),"next_permitted_operations":if s.state=="completed"||s.state=="cancelled"{vec!["task show","task export","task check","task reconcile"]}else{vec!["task show","task check","task reconcile","artifact freeze","packet preview","packet seal","assignment prepare","assignment handoff","assignment observe","review import","finding resolve","task extend-review","task accept-commit","task block","task activate","task cancel","task complete"]},"baseline_review_limit":s.profile.review.max_followup_rounds,"effective_review_limit":effective_review_limit(s),"review_extensions":s.review_extensions,"record":s,"live_source":live_source(s)})
}
fn packet_validate(s: &State, p: &PacketSpec) -> Result<()> {
    ensure!(
        s.current_artifact.as_deref() == Some(&p.artifact),
        "packet artifact is stale"
    );
    nonempty(&p.instructions, "instructions")?;
    nonempty(&p.access_policy, "access policy")?;
    ensure!(
        p.round <= effective_review_limit(s),
        "follow-up round cap reached"
    );
    ensure!(
        p.coverage.len() == s.spec.requirements.len(),
        "coverage must map every requirement/safeguard/criterion"
    );
    for r in &s.spec.requirements {
        refs(
            s,
            p.coverage
                .get(&r.id)
                .ok_or_else(|| anyhow::anyhow!("missing requirement coverage"))?,
        )?;
    }
    for e in &p.evidence {
        evidence(s, e)?;
    }
    ensure!(
        ["writer_context", "review"].contains(&p.purpose.as_str()),
        "unknown packet purpose"
    );
    let previous = latest_review_packet(s);
    if p.purpose == "writer_context" {
        match previous {
            None => ensure!(
                p.round == 0,
                "initial writer context precedes review round zero"
            ),
            Some(prev) => {
                ensure!(
                    round_complete(s, prev),
                    "finish every required reviewer before preparing repair writing"
                );
                ensure!(
                    p.round == prev.spec.round + 1,
                    "writer context must target next review round"
                );
            }
        }
    } else if p.round == 0 {
        ensure!(
            p.neutral_initial,
            "initial packet requires neutral-input declaration"
        );
        ensure!(
            previous.is_none(),
            "initial packet already sealed; immutable identity cannot be replaced"
        );
    } else {
        let prev = previous.context("initial review packet required")?;
        ensure!(p.round == prev.spec.round + 1, "rounds must be sequential");
        ensure!(
            round_complete(s, prev),
            "finish every required reviewer on same prior identity before repair/follow-up"
        );
        ensure!(
            prev.spec.artifact != p.artifact,
            "follow-up must name changed artifact"
        );
    }
    ensure!(
        s.assignments.iter().all(terminal),
        "active/unknown/prepared invocations block new packet"
    );
    Ok(())
}
fn evidence(s: &State, e: &Evidence) -> Result<()> {
    ensure!(
        [
            "source_claim",
            "verified_observation",
            "interpretation",
            "reviewer_opinion",
            "unknown",
            "unavailable"
        ]
        .contains(&e.category.as_str()),
        "unknown evidence category"
    );
    nonempty(&e.description, "evidence description")?;
    ensure!(
        s.objects.contains_key(&e.object),
        "evidence object not frozen"
    );
    Ok(())
}
fn observe(s: &mut State, r: Receipt, raw: String) -> Result<()> {
    ensure!(r.schema_version == 1, "unsupported receipt schema");
    nonempty(&r.reason, "receipt reason")?;
    nonempty(&r.boundary_observations, "boundary observations")?;
    ensure!(
        [
            "launching",
            "running",
            "completed",
            "interrupted",
            "blocked",
            "unknown"
        ]
        .contains(&r.state.as_str()),
        "invalid invocation state"
    );
    let assignment_index = s
        .assignments
        .iter()
        .position(|a| a.spec.id == r.assignment)
        .ok_or_else(|| anyhow::anyhow!("unknown assignment"))?;
    // Preparation is historical: reconciliation may have reattached another
    // writer since then. Recheck immediately before persisting a new intent,
    // inside the caller's serialized mutation transaction. Observations of an
    // existing worker remain recordable even when they reveal conflicting work.
    if r.state == "launching" && s.assignments[assignment_index].spec.role == "writer" {
        ensure!(
            s.assignments
                .iter()
                .enumerate()
                .all(|(index, other)| index == assignment_index
                    || other.spec.role != "writer"
                    || terminal(other)),
            "writer launch blocked: another writer is prepared/active/unknown; reconcile existing writers before new launch intent"
        );
    }
    ensure!(
        s.assignments[assignment_index].state != "superseded",
        "superseded invocation cannot resume or produce a second result slot"
    );
    if let Some(invocation) = &r.invocation {
        // A continuation's invocation is distinct from every other assignment,
        // whichever side records it first. Repeated observations within the
        // same assignment are allowed; ordinary-only records keep their rules.
        ensure!(
            !s.assignments
                .iter()
                .enumerate()
                .any(|(i, other)| i != assignment_index
                    && (s.assignments[assignment_index].continuation.is_some()
                        || other.continuation.is_some())
                    && other
                        .observations
                        .iter()
                        .any(|o| o.receipt.invocation.as_ref() == Some(invocation))),
            "continuation requires a fresh session, distinct from writer and previous invocations"
        );
    }
    let a = &mut s.assignments[assignment_index];
    ensure!(
        !s.reviews.iter().any(|v| v.spec.assignment == a.spec.id),
        "valid result already imported; no redispatch/rewrite"
    );
    if r.state == "launching" {
        ensure!(
            a.state == "prepared",
            "no retry/duplicate launch: reconcile existing intent; no automatic redispatch"
        );
        ensure!(
            s.profile.bounds.enforcement != "required",
            "record-only CLI cannot validate a deadline supervisor; required timing blocks launch"
        );
        ensure!(
            s.profile.effort_check != "runtime-attestation",
            "record-only CLI cannot validate independent runtime effort attestation"
        );
        ensure!(
            r.invocation.is_none(),
            "persist launch intent before attaching host invocation"
        );
        let start = now();
        let minutes = if a.spec.role == "writer" {
            s.profile.bounds.writer_minutes
        } else {
            s.profile.bounds.reviewer_minutes
        };
        a.launch_at = Some(start);
        if a.continuation.is_none() {
            a.deadline = Some(
                start
                    .checked_add(minutes.checked_mul(60).context("deadline overflow")?)
                    .context("deadline overflow")?,
            );
        }
    } else {
        ensure!(
            a.launch_at.is_some(),
            "launch intent must be durably recorded first"
        );
        if matches!(a.state.as_str(), "unknown" | "blocked" | "interrupted") {
            ensure!(
                r.reconciled,
                "uncertain/interrupted invocation requires explicit host reconciliation"
            );
        }
        if r.state == "running" || r.state == "completed" {
            ensure!(
                r.invocation.as_ref().is_some_and(|x| !x.trim().is_empty()),
                "session/invocation identity required; PID alone insufficient"
            );
        }
        if let Some(prev) = a
            .observations
            .iter()
            .rev()
            .find_map(|o| o.receipt.invocation.as_ref())
        {
            ensure!(
                r.invocation.as_ref() == Some(prev) || r.absence_established && r.reconciled,
                "invocation identity mismatch without reconciled absence"
            );
        }
        if terminal(a) {
            ensure!(
                r.reconciled,
                "terminal observation cannot be replaced without reconciliation"
            );
        }
    }
    a.state = r.state.clone();
    a.observations.push(Observation {
        at: now(),
        receipt: r,
        raw,
    });
    Ok(())
}
fn review_validate(s: &State, r: &ReviewSpec) -> Result<()> {
    ensure!(r.schema_version == 1, "unsupported review schema");
    let a = s
        .assignments
        .iter()
        .find(|a| a.spec.id == r.assignment)
        .ok_or_else(|| anyhow::anyhow!("unknown assignment"))?;
    ensure!(
        a.spec.role == "reviewer" && a.state == "completed",
        "completed reviewer invocation required; exit success alone is insufficient"
    );
    ensure!(a.spec.packet == r.packet, "review packet mismatch");
    let p = s
        .packets
        .iter()
        .find(|p| p.id == r.packet)
        .context("unknown packet")?;
    ensure!(
        p.spec.artifact == r.artifact && s.current_artifact.as_deref() == Some(&r.artifact),
        "stale/mismatched artifact review refused"
    );
    ensure!(
        !s.reviews.iter().any(|v| v.spec.assignment == r.assignment),
        "assignment already has valid review"
    );
    ensure!(
        ["pass", "changes_required", "blocked"].contains(&r.verdict.as_str()),
        "invalid review verdict"
    );
    nonempty(&r.limits, "verification limits")?;
    nonempty(&r.fresh_session, "fresh-session observation")?;
    if a.continuation.is_some() {
        ensure!(
            a.observations
                .last()
                .and_then(|o| o.receipt.invocation.as_ref())
                == Some(&r.fresh_session),
            "continuation review fresh_session must name the completed invocation"
        );
    }
    nonempty(&r.automatic_context, "automatic context observation")?;
    nonempty(&r.tool_boundary, "tool boundary observation")?;
    ensure!(
        !r.verification.is_empty(),
        "verification evidence required (may be explicitly unknown)"
    );
    for e in &r.verification {
        evidence(s, e)?;
    }
    let mut ids = BTreeSet::new();
    for f in &r.findings {
        component(&f.id)?;
        ensure!(
            ids.insert(&f.id) && !s.findings.iter().any(|x| x.spec.id == f.id),
            "duplicate finding identity"
        );
        for (v, label) in [
            (&f.location, "location/requirement"),
            (&f.scenario, "scenario"),
            (&f.evidence, "evidence/reasoning"),
            (&f.uncertainty, "uncertainty"),
            (&f.recommendation, "recommendation"),
        ] {
            nonempty(v, label)?;
        }
    }
    ensure!(
        r.verdict != "pass" || !r.findings.iter().any(|f| f.material),
        "pass conflicts with material findings"
    );
    Ok(())
}
fn handoff(s: &mut State, root: &Path, input: &Value, actor: &str) -> Result<Value> {
    let h: HandoffSpec = decode(input)?;
    component(&h.replacement)?;
    ensure!(
        profile::name(&h.agent) && h.agent != "current-session",
        "explicit replacement agent identity required"
    );
    ensure!(
        h.decision == "continue_with_codex",
        "explicit owner choice continue_with_codex required; waiting retains interruption"
    );
    ensure!(
        s.spec.decision_authorities.contains(&h.authority) && actor == h.authority,
        "declared decision authority/actor required; not authentication"
    );
    refs(s, &h.decision_evidence)?;
    nonempty(&h.reason, "handoff reason")?;
    nonempty(&h.instructions, "continuation instructions")?;
    nonempty(&h.output_destination, "replacement output destination")?;
    nonempty(&h.previous_invocation, "original invocation identity")?;
    ensure!(
        h.timing == "preserve_deadline",
        "explicit preserve_deadline timing treatment required; no extension supported"
    );
    ensure!(
        !s.assignments.iter().any(|a| a.spec.id == h.replacement),
        "replacement identity already used"
    );
    let index = s
        .assignments
        .iter()
        .position(|a| a.spec.id == h.assignment)
        .context("unknown original assignment")?;
    let old = s.assignments[index].clone();
    ensure!(
        h.output_destination != old.spec.output_destination,
        "replacement needs a distinct output destination; preserve original partial outputs"
    );
    ensure!(
        old.state == "interrupted",
        "only an interrupted incomplete assignment can be handed off"
    );
    ensure!(
        !s.reviews.iter().any(|r| r.spec.assignment == old.spec.id),
        "valid review cannot be replaced, regardless of verdict"
    );
    ensure!(
        old.requested.transport == "claude-cli",
        "quota handoff requires a Claude collaborator; unavailable Codex lead checkpoints and stops"
    );
    let last = old
        .observations
        .last()
        .context("host reconciliation required")?;
    ensure!(
        last.receipt.state == "interrupted"
            && last.receipt.reconciled
            && last.receipt.absence_established,
        "latest interruption must explicitly reconcile original invocation absence; unknown liveness fails closed"
    );
    ensure!(
        last.receipt.invocation.as_deref() == Some(&h.previous_invocation),
        "original invocation identity mismatch"
    );
    ensure!(old.deadline.is_some(), "original timing required");
    ensure!(
        s.profile.bounds.enforcement != "required",
        "record-only engine cannot validate required timing supervisor"
    );
    let packet = s
        .packets
        .iter()
        .find(|p| p.id == h.packet)
        .context("sealed handoff packet required")?;
    ensure!(
        old.spec.packet == h.packet && s.current_artifact.as_deref() == Some(&packet.spec.artifact),
        "stale/mismatched handoff packet"
    );
    ensure!(
        s.packets.last().is_some_and(|p| p.id == h.packet),
        "handoff must continue the current sealed stage"
    );
    let requested = match &h.selection {
        Some(selection) => {
            ensure!(
                !s.profile.agents.contains_key(&h.agent),
                "task-local selection cannot redefine a frozen profile alias"
            );
            ensure!(
                !s.assignments.iter().any(|a| a
                    .continuation
                    .as_ref()
                    .is_some_and(|c| c.handoff.agent == h.agent)),
                "task-local execution identity already used; choose a distinct identity"
            );
            let mut validation = s.profile.clone();
            validation.agents.insert(h.agent.clone(), selection.clone());
            validation.validate()?;
            selection.clone()
        }
        None => s.profile.agent(&h.agent)?,
    };
    ensure!(
        requested.transport == "codex-native",
        "explicit available Codex model required; access is host-verified"
    );
    let preserved_work = if old.spec.role == "writer" {
        ensure!(
            s.assignments
                .iter()
                .enumerate()
                .all(|(i, a)| i == index || a.spec.role != "writer" || terminal(a)),
            "one writer at a time; reconcile other writers"
        );
        let selection = h
            .partial_work
            .as_ref()
            .context("writer continuation requires a snapshot of current partial work")?;
        let (id, manifest, objects) = snapshot::capture(&s.spec.repository, root, selection)?;
        for scope in &s.spec.editable_scope {
            // Capture validates complete Git inventory coverage. A directory
            // scope covers its children; a future path need not exist yet.
            ensure!(
                !manifest
                    .omissions
                    .keys()
                    .any(|path| path == scope || path.starts_with(&format!("{scope}/"))),
                "partial work snapshot cannot omit scoped inventory"
            );
            // Ignored files are outside Git inventory. An existing exact scope
            // must still be selected, even when Git would not list that input.
            match fs::symlink_metadata(s.spec.repository.join(scope)) {
                Ok(metadata) if !metadata.is_dir() => ensure!(
                    selection.paths.contains(scope),
                    "partial work snapshot must select existing exact scoped input"
                ),
                Ok(_) => {}
                Err(error)
                    if matches!(
                        error.kind(),
                        std::io::ErrorKind::NotFound | std::io::ErrorKind::NotADirectory
                    ) => {}
                Err(error) => return Err(error).context("cannot inspect exact writer scope"),
            }
        }
        for object in objects {
            register(s, object, "continuation/partial-source");
        }
        Some(id)
    } else {
        ensure!(
            h.partial_work.is_none(),
            "reviewer continuation receives neutral packet only, no writer partial work"
        );
        None
    };
    let mut spec = old.spec.clone();
    spec.id = h.replacement.clone();
    spec.output_destination = h.output_destination.clone();
    // spec.agent remains the logical required slot, not the execution identity.
    // requested and handoff.agent record the new execution without alias mutation.
    s.assignments[index].state = "superseded".into();
    s.assignments.push(Assignment {
        spec,
        created_at: now(),
        actor: actor.into(),
        requested,
        state: "prepared".into(),
        launch_at: None,
        deadline: old.deadline,
        observations: Vec::new(),
        continuation: Some(Continuation {
            handoff: h.clone(),
            original_requested: old.requested,
            preserved_work: preserved_work.clone(),
        }),
    });
    s.schema_version = s.schema_version.max(2);
    Ok(
        json!({"assignment": h.replacement, "logical_slot": old.spec.agent, "execution_agent": h.agent,
        "packet": h.packet, "deadline": old.deadline, "preserved_work": preserved_work,
        "dispatch": "not performed; host must use retained continuation instructions and fresh session"}),
    )
}
fn mutate(
    s: &mut State,
    root: &Path,
    command: &str,
    input: &Value,
    raw: &[u8],
    actor: &str,
) -> Result<Value> {
    match command {
        "task extend-review" => extend_review(s, input, actor),
        "task accept-commit" => accept_commit(s, root, input, actor),
        "artifact freeze" => {
            if let Some(p) = latest_review_packet(s) {
                ensure!(
                    round_complete(s, p),
                    "all required initial/current reviewers must finish before review-driven repair"
                );
                ensure!(
                    s.assignments.iter().all(terminal),
                    "reconcile active/unknown invocations before repair"
                );
                ensure!(
                    p.spec.round < effective_review_limit(s),
                    "round cap reached; changed artifact cannot receive required review"
                );
            }
            ensure!(
                s.assignments.iter().all(terminal),
                "reconcile active/unknown/prepared invocations before capture"
            );
            snapshot::repository(&s.spec.repository)?;
            let selection: snapshot::Selection = decode(input)?;
            let (id, manifest, objects) = snapshot::capture(&s.spec.repository, root, &selection)?;
            for id in objects {
                register(s, id, "artifact/source");
            }
            if !s.artifacts.iter().any(|a| a.id == id) {
                s.artifacts.push(Artifact {
                    id: id.clone(),
                    created_at: now(),
                    actor: actor.into(),
                    manifest,
                });
            }
            if s.current_artifact.as_deref() != Some(&id) {
                s.current_commit_acceptance = None;
            }
            s.current_artifact = Some(id.clone());
            Ok(json!({"artifact":id}))
        }
        "packet seal" => {
            let spec: PacketSpec = decode(input)?;
            packet_validate(s, &spec)?;
            // Freeze verbatim task requirements and boundaries together with the common body.
            let bytes = encoded(
                &json!({"schema_version":1,"requirements":s.spec.requirements,"authority_boundaries":s.spec.authority_boundaries,"packet":spec}),
            )?;
            let id = put(root, &bytes)?;
            register(s, id.clone(), "packet/common-body");
            s.packets.push(Packet {
                id: id.clone(),
                created_at: now(),
                actor: actor.into(),
                spec,
            });
            Ok(json!({"packet":id}))
        }
        "assignment prepare" => {
            let spec: AssignmentSpec = decode(input)?;
            component(&spec.id)?;
            nonempty(&spec.output_destination, "recipient output destination")?;
            ensure!(
                !s.assignments.iter().any(|a| a.spec.id == spec.id),
                "assignment identity already used"
            );
            let p = s
                .packets
                .iter()
                .find(|p| p.id == spec.packet)
                .context("sealed packet required")?;
            ensure!(
                spec.packet == p.id && s.current_artifact.as_deref() == Some(&p.spec.artifact),
                "assignment must use current common sealed packet"
            );
            ensure!(
                ["writer", "reviewer"].contains(&spec.role.as_str()),
                "unknown assignment role"
            );
            if spec.role == "reviewer" {
                ensure!(
                    p.spec.purpose == "review"
                        && latest_review_packet(s).is_some_and(|latest| latest.id == p.id),
                    "reviewer requires the current review common packet"
                );
                ensure!(
                    s.spec.reviewers.contains(&spec.agent),
                    "reviewer not in fixed required set; replacement cannot reset rounds"
                );
                ensure!(
                    spec.editable_scope.is_empty(),
                    "reviewer must have empty source edit scope"
                );
            } else {
                ensure!(
                    p.spec.purpose == "writer_context",
                    "writer requires a writer_context packet, not a review round"
                );
                if let Some(review) = latest_review_packet(s) {
                    ensure!(
                        round_complete(s, review) && p.spec.round == review.spec.round + 1,
                        "all required reviews must finish before repair writing; old writer context cannot reset rounds"
                    );
                }
                ensure!(
                    spec.agent == s.spec.writer && spec.editable_scope == s.spec.editable_scope,
                    "only registered writer with exact scope permitted"
                );
                ensure!(
                    !s.assignments
                        .iter()
                        .any(|a| a.spec.role == "writer" && !terminal(a)),
                    "one active writer only"
                );
            }
            ensure!(
                !s.assignments
                    .iter()
                    .any(|a| a.spec.packet == spec.packet && a.spec.agent == spec.agent),
                "reviewer/writer slot already prepared; reconcile it instead of duplicate"
            );
            let requested = s.profile.agent(&spec.agent)?;
            let id = spec.id.clone();
            s.assignments.push(Assignment {
                spec,
                created_at: now(),
                actor: actor.into(),
                requested,
                state: "prepared".into(),
                launch_at: None,
                deadline: None,
                observations: Vec::new(),
                continuation: None,
            });
            Ok(
                json!({"assignment":id,"state":"prepared","timing":s.profile.bounds.enforcement,"observed_effort":"unknown"}),
            )
        }
        "assignment handoff" => handoff(s, root, input, actor),
        "assignment observe" => {
            let receipt: Receipt = decode(input)?;
            let id = put(root, raw)?;
            register(s, id.clone(), "invocation-receipt");
            observe(s, receipt, id)?;
            Ok(json!({"recorded":true}))
        }
        "review import" => {
            let id = put(root, raw)?;
            register(s, id.clone(), "review/raw-original");
            let result = parse::<ReviewSpec>(raw).and_then(|r| {
                review_validate(s, &r)?;
                Ok(r)
            });
            match result {
                Ok(spec) if spec.verdict == "blocked" => {
                    let error="review explicitly blocked/incomplete; reconcile existing assignment after restored access".to_string();
                    s.invalid_results.push(Attempt {
                        object: id.clone(),
                        assignment: Some(spec.assignment.clone()),
                        at: now(),
                        error: error.clone(),
                    });
                    s.assignments
                        .iter_mut()
                        .find(|a| a.spec.id == spec.assignment)
                        .unwrap()
                        .state = "blocked".into();
                    Ok(json!({"validation":"incomplete","original":id,"reason":error}))
                }
                Ok(spec) => {
                    for f in &spec.findings {
                        s.findings.push(Finding {
                            spec: f.clone(),
                            review: id.clone(),
                            artifact: spec.artifact.clone(),
                            disposition: None,
                        });
                    }
                    s.reviews.push(Review {
                        id: id.clone(),
                        at: now(),
                        actor: actor.into(),
                        spec,
                    });
                    Ok(
                        json!({"validation":"valid_structure_only","review":id,"truth_and_authority":"not_attested"}),
                    )
                }
                Err(e) => {
                    let assignment = input
                        .get("assignment")
                        .and_then(Value::as_str)
                        .map(String::from);
                    let error = e.to_string();
                    s.invalid_results.push(Attempt {
                        object: id.clone(),
                        assignment,
                        at: now(),
                        error: error.clone(),
                    });
                    Ok(json!({"validation":"rejected","original":id,"reason":error}))
                }
            }
        }
        "finding resolve" => {
            let d: Disposition = decode(input)?;
            nonempty(&d.reason, "disposition reason")?;
            refs(s, &d.evidence)?;
            ensure!(
                ["addressed", "rejected", "deferred", "unresolved"].contains(&d.decision.as_str()),
                "unknown disposition"
            );
            ensure!(
                s.spec.decision_authorities.contains(&d.authority) && actor == d.authority,
                "decision authority/actor is not declared; declaration is not independent authorization proof"
            );
            let f = s
                .findings
                .iter_mut()
                .find(|f| f.spec.id == d.finding)
                .context("unknown finding")?;
            f.disposition = Some(d);
            Ok(json!({"recorded":true}))
        }
        "task activate" => {
            check_bound_source(s)?;
            let reason: Lifecycle = decode(input)?;
            nonempty(&reason.reason, "reason")?;
            ensure!(
                s.state == "prepared" || s.state == "blocked",
                "only prepared/blocked task can activate"
            );
            s.state = "active".into();
            s.reason = reason.reason;
            Ok(json!({"state":s.state}))
        }
        "task block" | "task cancel" => {
            let reason: Lifecycle = decode(input)?;
            nonempty(&reason.reason, "reason")?;
            s.state = if command == "task block" {
                "blocked"
            } else {
                "cancelled"
            }
            .into();
            s.reason = reason.reason;
            Ok(json!({"state":s.state}))
        }
        "task complete" => {
            let completion: Completion = decode(input)?;
            ensure!(s.state == "active", "only active task can complete");
            let b = blockers(s);
            ensure!(b.is_empty(), "completion blocked: {}", b.join("; "));
            ensure!(
                s.current_artifact.as_deref() == Some(&completion.artifact),
                "completion identity mismatch"
            );
            nonempty(&completion.reason, "completion reason")?;
            let criteria: Vec<_> = s
                .spec
                .requirements
                .iter()
                .filter(|r| r.kind == "criterion")
                .map(|r| r.id.clone())
                .collect();
            for (required, got) in [
                (&criteria, &completion.criteria),
                (&s.spec.required_checks, &completion.checks),
                (&s.spec.required_approvals, &completion.approvals),
            ] {
                ensure!(
                    required.len() == got.len() && required.iter().all(|r| got.contains_key(r)),
                    "completion requires exact criterion/check/approval evidence coverage"
                );
                for v in got.values() {
                    refs(s, v)?;
                }
            }
            let a = s
                .artifacts
                .iter()
                .find(|a| a.id == completion.artifact)
                .context("missing completion artifact")?;
            current_source(s, a)?;
            let v = serde_json::to_value(&completion)?;
            s.completion = Some(v.clone());
            s.state = "completed".into();
            Ok(
                json!({"state":"completed","evidence":v,"validation":"structural evidence only; truth and authority not attested"}),
            )
        }
        "task reconcile" => {
            check_bound_source(s)?;
            let reason: Lifecycle = decode(input)?;
            nonempty(&reason.reason, "reconciliation reason")?;
            for a in &mut s.assignments {
                if a.state == "launching" {
                    a.state = "unknown".into();
                }
            }
            let q = root.join("quarantine");
            dir(&q)?;
            let mut quarantined = Vec::new();
            for e in fs::read_dir(root.join("staging"))? {
                let e = e?;
                ensure!(
                    e.file_type()?.is_file(),
                    "unexpected staging entry; inspect manually"
                );
                let name = e.file_name();
                let dest = q.join(&name);
                ensure!(
                    !dest.exists(),
                    "quarantine destination already exists; preserve and inspect"
                );
                fs::rename(e.path(), &dest)?;
                quarantined.push(name.to_string_lossy().to_string());
            }
            File::open(&q)?.sync_all()?;
            File::open(root.join("staging"))?.sync_all()?;
            Ok(
                json!({"quarantined":quarantined,"reason":reason.reason,"note":"running observations are historical, not liveness; reconcile with authorized host; unreferenced objects retained"}),
            )
        }
        _ => bail!("unknown mutation command; see docs/cli.md"),
    }
}
fn create(req: &Request, raw: &[u8], actor: &str, key: &str, expected: u64) -> Result<Value> {
    nonempty(key, "idempotency key")?;
    ensure!(expected == 0, "task create expects revision zero");
    let spec: TaskSpec = parse(raw)?;
    let profile_raw = read(
        req.profile
            .as_deref()
            .context("--profile required for task create")?,
        256 * 1024,
    )?;
    let profile: Profile = parse(&profile_raw)?;
    profile.validate()?;
    validate_task(&spec, &profile)?;
    let expanded = if let Some(t) = profile.records_root.strip_prefix("~/") {
        PathBuf::from(std::env::var_os("HOME").context("cannot expand owner home")?).join(t)
    } else {
        PathBuf::from(&profile.records_root)
    };
    // Require the configured volume/root to exist. Never create a missing volume or fallback.
    let base = expanded
        .canonicalize()
        .context("configured records root unavailable; create/verify it explicitly")?;
    ensure!(base.is_dir(), "records root not directory");
    supported_storage(&base)?;
    if let Some(home) = std::env::var_os("HOME")
        && let Ok(home) = PathBuf::from(home).canonicalize()
    {
        ensure!(
            base != home,
            "records root must not be the owner home directory"
        );
    }
    let root = base
        .join(&spec.project)
        .join(&spec.task)
        .join("collaboration");
    no_links(&root)?;
    outside_repository(&root)?;
    ensure!(
        !overlap(&root, &spec.repository),
        "record/repository overlap"
    );
    if let Some(p) = &req.record {
        ensure!(p == &root, "supplied record disagrees with profile layout");
    }
    for p in [
        base.join(&spec.project),
        base.join(&spec.project).join(&spec.task),
        root.clone(),
    ] {
        dir(&p)?;
    }
    for n in ["objects", "staging", "quarantine"] {
        dir(&root.join(n))?;
    }
    let mut c = connection(&root, true)?;
    let tx = c.transaction_with_behavior(TransactionBehavior::Immediate)?;
    let fingerprint = hash(&encoded(
        &json!({"command":req.command,"input":hash(raw),"profile":hash(&profile_raw),"actor":actor,"expected":expected}),
    )?);
    if let Some((old, response)) = tx
        .query_row(
            "SELECT fingerprint,response FROM operations WHERE key=?",
            [key],
            |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)),
        )
        .optional()?
    {
        ensure!(
            old == fingerprint,
            "idempotency key conflicts with different request"
        );
        let existing = load(&tx)?;
        validate_root(&root, &existing)?;
        verify(&root, &existing.objects)?;
        return parse(response.as_bytes());
    }
    ensure!(
        tx.query_row("SELECT COUNT(*) FROM state", [], |r| r.get::<_, i64>(0))? == 0,
        "task already exists; preserve its records"
    );
    let mut s = State {
        schema_version: 1,
        spec,
        profile,
        profile_hash: hash(&profile_raw),
        created_at: now(),
        state: "prepared".into(),
        revision: 1,
        reason: "created; host dispatch not started".into(),
        artifacts: vec![],
        current_artifact: None,
        packets: vec![],
        assignments: vec![],
        reviews: vec![],
        findings: vec![],
        invalid_results: vec![],
        objects: BTreeMap::new(),
        events: vec![],
        completion: None,
        review_extensions: vec![],
        commit_acceptances: vec![],
        current_commit_acceptance: None,
    };
    let id = put(&root, &profile_raw)?;
    register(&mut s, id, "profile/private-resolved-preferences");
    let id = put(&root, raw)?;
    register(&mut s, id, "task/spec-original");
    s.events.push(Event {
        operation: key.into(),
        command: req.command.clone(),
        actor: actor.into(),
        at: now(),
        previous_revision: 0,
        revision: 1,
        input_hash: hash(raw),
    });
    let response = json!({"record":root,"task":s.spec.task,"revision":1,"state":s.state,"blockers":blockers(&s)});
    tx.execute(
        "INSERT INTO state VALUES(1,1,1,?)",
        [serde_json::to_string(&s)?],
    )?;
    tx.execute(
        "INSERT INTO operations VALUES(?,?,?,1)",
        params![key, fingerprint, serde_json::to_string(&response)?],
    )?;
    fault("before-commit")?;
    tx.commit()?;
    File::open(&root)?.sync_all()?;
    fault("after-commit")?;
    Ok(response)
}
pub fn run(req: Request) -> Result<Value> {
    let read_only = matches!(
        req.command.as_str(),
        "task show" | "task export" | "task check" | "packet show" | "packet preview"
    );
    let raw = match &req.input {
        Some(p) => read(p, 16 * 1024 * 1024)?,
        None => b"{}".to_vec(),
    };
    let input: Value = if req.command == "review import" {
        parse(&raw).unwrap_or(Value::Null)
    } else {
        parse(&raw)?
    };
    if req.command == "task create" {
        let actor = req.actor.as_deref().context("--actor required")?;
        nonempty(actor, "actor")?;
        return create(
            &req,
            &raw,
            actor,
            req.key.as_deref().context("--key required")?,
            req.expect.context("--expect required")?,
        );
    }
    ensure!(
        req.profile.is_none(),
        "profile is fixed at creation; no implicit profile replacement"
    );
    let root = req.record.as_deref().context("--record required")?;
    let mut c = connection(root, false)?;
    if read_only {
        let s = load(&c)?;
        validate_root(root, &s)?;
        verify(root, &s.objects)?;
        return match req.command.as_str() {
            "task show" => Ok(summary(&s)),
            "task check" => {
                let mut b = blockers(&s);
                if let Some(a) = s
                    .artifacts
                    .iter()
                    .find(|a| s.current_artifact.as_deref() == Some(&a.id))
                    && let Err(e) = current_source(&s, a)
                {
                    b.push(format!("live source verification: {e}"));
                }
                Ok(
                    json!({"revision":s.revision,"state":s.state,"integrity":"verified","completion_blockers":b,"live_source":live_source(&s),"evidence_limit":"structure and hashes cannot attest truth, authority, runtime effort or worker liveness"}),
                )
            }
            "task export" => {
                #[derive(Deserialize)]
                #[serde(deny_unknown_fields)]
                struct Export {
                    fields: Vec<String>,
                }
                let e: Export = decode(&input)?;
                list_unique(&e.fields, "export fields")?;
                ensure!(!e.fields.is_empty(), "explicit export selection required");
                let all = serde_json::to_value(&s)?;
                let mut out = serde_json::Map::new();
                for f in e.fields {
                    ensure!(
                        [
                            "spec",
                            "state",
                            "revision",
                            "artifacts",
                            "current_artifact",
                            "packets",
                            "assignments",
                            "reviews",
                            "findings",
                            "invalid_results",
                            "events",
                            "completion",
                            "review_extensions",
                            "commit_acceptances",
                            "current_commit_acceptance"
                        ]
                        .contains(&f.as_str()),
                        "export field not allowed; profile/raw storage exports unavailable"
                    );
                    out.insert(f.clone(), all[&f].clone());
                }
                Ok(
                    json!({"schema_version":1,"selected_private_records":out,"live_source":live_source(&s),"sanitization":"caller must inspect selected records before sharing; no automatic redaction"}),
                )
            }
            "packet show" => {
                #[derive(Deserialize)]
                #[serde(deny_unknown_fields)]
                struct Show {
                    packet: String,
                }
                let p: Show = decode(&input)?;
                ensure!(
                    s.packets.iter().any(|x| x.id == p.packet),
                    "unknown sealed packet"
                );
                Ok(
                    json!({"sealed_packet":parse::<Value>(&object(root,&p.packet)?)?,"live_source":live_source(&s)}),
                )
            }
            "packet preview" => {
                let p: PacketSpec = decode(&input)?;
                packet_validate(&s, &p)?;
                Ok(
                    json!({"schema_version":1,"requirements":s.spec.requirements,"authority_boundaries":s.spec.authority_boundaries,"packet":p,"sealed":false}),
                )
            }
            _ => unreachable!(),
        };
    }
    let actor = req.actor.as_deref().context("--actor required")?;
    nonempty(actor, "actor")?;
    let key = req.key.as_deref().context("--key required")?;
    nonempty(key, "idempotency key")?;
    let expected = req.expect.context("--expect required")?;
    let tx = c.transaction_with_behavior(TransactionBehavior::Immediate)?;
    let fingerprint = hash(&encoded(
        &json!({"command":req.command,"input":hash(&raw),"actor":actor,"expected":expected}),
    )?);
    let mut s = load(&tx)?;
    validate_root(root, &s)?;
    verify(root, &s.objects)?;
    if let Some((old, response)) = tx
        .query_row(
            "SELECT fingerprint,response FROM operations WHERE key=?",
            [key],
            |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)),
        )
        .optional()?
    {
        ensure!(
            old == fingerprint,
            "idempotency key conflicts with different request"
        );
        return parse(response.as_bytes());
    }
    ensure!(
        s.revision == expected,
        "stale revision: expected {expected}, current {}",
        s.revision
    );
    verify(root, &s.objects)?;
    ensure!(
        !matches!(s.state.as_str(), "completed" | "cancelled") || req.command == "task reconcile",
        "terminal task is immutable except reconciliation; no round reset"
    );
    let result = mutate(&mut s, root, &req.command, &input, &raw, actor)?;
    let id = put(root, &raw)?;
    register(&mut s, id, "operation/input-original");
    s.revision += 1;
    s.events.push(Event {
        operation: key.into(),
        command: req.command.clone(),
        actor: actor.into(),
        at: now(),
        previous_revision: expected,
        revision: s.revision,
        input_hash: hash(&raw),
    });
    let response = json!({"revision":s.revision,"state":s.state,"result":result,"blockers":blockers(&s),"live_source":live_source(&s)});
    let stored_version: i64 = tx.query_row(
        "SELECT schema_version FROM state WHERE singleton=1",
        [],
        |r| r.get(0),
    )?;
    ensure!(
        i64::try_from(s.schema_version)? >= stored_version,
        "record format cannot downgrade"
    );
    if i64::try_from(s.schema_version)? > stored_version {
        // Rebuild historical CHECK constraints transactionally. Keep the old
        // row intact until the final update; rollback preserves its marker/body.
        tx.execute_batch("ALTER TABLE state RENAME TO state_previous_format;
            CREATE TABLE state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema_version INTEGER NOT NULL CHECK(schema_version IN (1,2,3,4)), revision INTEGER NOT NULL, body TEXT NOT NULL);
            INSERT INTO state SELECT * FROM state_previous_format;
            DROP TABLE state_previous_format;")?;
    }
    tx.execute(
        "UPDATE state SET schema_version=?,revision=?,body=? WHERE singleton=1 AND revision=?",
        params![
            i64::try_from(s.schema_version)?,
            i64::try_from(s.revision)?,
            serde_json::to_string(&s)?,
            i64::try_from(expected)?
        ],
    )?;
    tx.execute(
        "INSERT INTO operations VALUES(?,?,?,?)",
        params![
            key,
            fingerprint,
            serde_json::to_string(&response)?,
            i64::try_from(s.revision)?
        ],
    )?;
    fault("before-commit")?;
    tx.commit()?;
    fault("after-commit")?;
    Ok(response)
}
