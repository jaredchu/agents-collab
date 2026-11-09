use anyhow::{Result, ensure};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Agent {
    pub model: String,
    pub transport: String,
    pub reasoning: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Routing {
    pub small_writer: String,
    pub substantial_writer: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Review {
    pub on_consequential_work: String,
    pub candidates: Vec<String>,
    pub prefer_different_model: bool,
    pub recipes: BTreeMap<String, Vec<String>>,
    pub max_followup_rounds: u64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Bounds {
    pub enforcement: String,
    pub writer_minutes: u64,
    pub reviewer_minutes: u64,
    pub review_output_words: u64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Profile {
    pub version: u64,
    pub name: String,
    pub agents: BTreeMap<String, Agent>,
    pub routing: Routing,
    pub review: Review,
    pub effort_check: String,
    pub access: String,
    pub bounds: Bounds,
    pub records_root: String,
}
pub fn name(s: &str) -> bool {
    !s.is_empty()
        && s.len() <= 40
        && s.as_bytes()[0].is_ascii_alphanumeric()
        && s.bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
}
fn members(p: &Profile, v: &[String], nonempty: bool) -> Result<()> {
    ensure!(!nonempty || !v.is_empty(), "review list must not be empty");
    let mut seen = BTreeSet::new();
    for n in v {
        ensure!(seen.insert(n), "duplicate reviewer");
        let a = p
            .agents
            .get(n)
            .ok_or_else(|| anyhow::anyhow!("unknown reviewer"))?;
        ensure!(a.transport != "host", "host cannot be reviewer");
    }
    Ok(())
}
impl Profile {
    pub fn validate(&self) -> Result<()> {
        ensure!(self.version == 1, "unsupported profile version");
        ensure!(
            !self.name.trim().is_empty()
                && self.name.chars().count() <= 100
                && !self
                    .name
                    .chars()
                    .any(|c| (c as u32) < 32 || c as u32 == 127),
            "invalid profile name"
        );
        ensure!(!self.agents.is_empty(), "agents cannot be empty");
        let mut hosts = 0;
        for (n, a) in &self.agents {
            ensure!(name(n) && n != "current-session", "invalid agent name");
            ensure!(
                !a.model.is_empty()
                    && a.model.len() <= 128
                    && a.model.as_bytes()[0].is_ascii_alphanumeric()
                    && a.model
                        .bytes()
                        .all(|b| b.is_ascii_alphanumeric() || b"._:/@+[]-".contains(&b)),
                "invalid model identifier"
            );
            ensure!(
                ["host", "codex-native", "claude-cli"].contains(&a.transport.as_str()),
                "invalid transport"
            );
            ensure!(
                (a.transport == "host") == (a.model == "current"),
                "host/current mismatch"
            );
            hosts += usize::from(a.transport == "host");
            ensure!(
                !a.reasoning.is_empty()
                    && a.reasoning.len() <= 32
                    && a.reasoning.as_bytes()[0].is_ascii_lowercase()
                    && a.reasoning.bytes().all(|b| b.is_ascii_lowercase()
                        || b.is_ascii_digit()
                        || b"_-".contains(&b))
                    && !["default", "current"].contains(&a.reasoning.as_str()),
                "invalid reasoning"
            );
        }
        ensure!(hosts <= 1, "multiple hosts");
        for n in [&self.routing.small_writer, &self.routing.substantial_writer] {
            ensure!(
                n == "current-session" || self.agents.contains_key(n),
                "unknown routing agent"
            );
        }
        ensure!(
            ["single", "none"].contains(&self.review.on_consequential_work.as_str()),
            "invalid review mode"
        );
        members(
            self,
            &self.review.candidates,
            self.review.on_consequential_work == "single",
        )?;
        for (n, v) in &self.review.recipes {
            ensure!(name(n), "invalid recipe name");
            members(self, v, true)?;
        }
        if self.review.on_consequential_work == "none" && self.review.candidates.is_empty() { /* allowed */
        }
        ensure!(
            ["supported-control", "runtime-attestation"].contains(&self.effort_check.as_str()),
            "invalid effort policy"
        );
        ensure!(
            ["existing-subscriptions", "existing-authorized-access"]
                .contains(&self.access.as_str()),
            "invalid access policy"
        );
        ensure!(
            ["required", "advisory"].contains(&self.bounds.enforcement.as_str())
                && self.bounds.writer_minutes > 0
                && self.bounds.reviewer_minutes > 0
                && self.bounds.review_output_words > 0,
            "invalid bounds"
        );
        let r = &self.records_root;
        ensure!(
            r.trim() == r && !r.chars().any(|c| c.is_control()),
            "invalid records root"
        );
        ensure!(
            r.starts_with('/') || r.starts_with("~/"),
            "records root must be absolute or ~/..."
        );
        let tail = if let Some(t) = r.strip_prefix("~/") {
            t
        } else {
            &r[1..]
        };
        ensure!(
            tail.split('/').any(|c| !c.is_empty())
                && !tail.split('/').any(|c| c == "." || c == ".."),
            "invalid records root components"
        );
        Ok(())
    }
    pub fn agent(&self, n: &str) -> Result<Agent> {
        if n == "current-session" {
            return Ok(Agent {
                model: "current".into(),
                transport: "host".into(),
                reasoning: "inherit".into(),
            });
        }
        self.agents
            .get(n)
            .cloned()
            .ok_or_else(|| anyhow::anyhow!("unknown agent"))
    }
}
