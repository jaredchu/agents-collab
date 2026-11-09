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
    component(&t.project)?;
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
            version == 1,
            "unsupported schema; explicit migration required"
        );
    }
    fs::set_permissions(&db, fs::Permissions::from_mode(0o600))?;
    c.busy_timeout(Duration::from_secs(5))?;
    c.pragma_update(None, "foreign_keys", "ON")?;
    c.pragma_update(None, "journal_mode", "DELETE")?;
    c.pragma_update(None, "synchronous", "FULL")?;
    if create {
        c.execute_batch("CREATE TABLE IF NOT EXISTS state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema_version INTEGER NOT NULL CHECK(schema_version=1), revision INTEGER NOT NULL, body TEXT NOT NULL); CREATE TABLE IF NOT EXISTS operations (key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, response TEXT NOT NULL, revision INTEGER NOT NULL);")?;
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
        version == 1,
        "unsupported schema; explicit migration required"
    );
    let s: State = parse(body.as_bytes())?;
    ensure!(s.schema_version == 1, "unsupported state schema");
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
    matches!(a.state.as_str(), "completed" | "interrupted" | "blocked")
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
        } else if a.state == "blocked" {
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
fn summary(s: &State) -> Value {
    json!({"schema_version":1,"task":s.spec.task,"revision":s.revision,"state":s.state,"blockers":blockers(s),"next_permitted_operations":if s.state=="completed"||s.state=="cancelled"{vec!["task show","task export","task check","task reconcile"]}else{vec!["task show","task check","task reconcile","artifact freeze","packet preview","packet seal","assignment prepare","assignment observe","review import","finding resolve","task block","task activate","task cancel","task complete"]},"record":s,"live_source":live_source(s)})
}
fn packet_validate(s: &State, p: &PacketSpec) -> Result<()> {
    ensure!(
        s.current_artifact.as_deref() == Some(&p.artifact),
        "packet artifact is stale"
    );
    nonempty(&p.instructions, "instructions")?;
    nonempty(&p.access_policy, "access policy")?;
    ensure!(
        p.round <= s.profile.review.max_followup_rounds,
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
        a.deadline = Some(
            start
                .checked_add(minutes.checked_mul(60).context("deadline overflow")?)
                .context("deadline overflow")?,
        );
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
fn mutate(
    s: &mut State,
    root: &Path,
    command: &str,
    input: &Value,
    raw: &[u8],
    actor: &str,
) -> Result<Value> {
    match command {
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
                    p.spec.round < s.profile.review.max_followup_rounds,
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
            });
            Ok(
                json!({"assignment":id,"state":"prepared","timing":s.profile.bounds.enforcement,"observed_effort":"unknown"}),
            )
        }
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
            snapshot::unchanged(&s.spec.repository, &a.manifest)?;
            let v = serde_json::to_value(&completion)?;
            s.completion = Some(v.clone());
            s.state = "completed".into();
            Ok(
                json!({"state":"completed","evidence":v,"validation":"structural evidence only; truth and authority not attested"}),
            )
        }
        "task reconcile" => {
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
                    && let Err(e) = snapshot::unchanged(&s.spec.repository, &a.manifest)
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
                            "completion"
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
    tx.execute(
        "UPDATE state SET revision=?,body=? WHERE singleton=1 AND revision=?",
        params![
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
