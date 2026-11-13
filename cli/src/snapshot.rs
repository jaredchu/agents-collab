use crate::storage::*;
use anyhow::{Result, ensure};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    os::unix::{
        ffi::OsStrExt,
        fs::{MetadataExt, PermissionsExt},
    },
    path::Path,
    process::Command,
};
#[derive(Deserialize, Serialize, Clone)]
#[serde(deny_unknown_fields)]
pub struct Selection {
    pub paths: Vec<String>,
    pub omissions: BTreeMap<String, String>,
    pub acknowledged_sensitive: Vec<String>,
    pub quiescence: String,
    pub atomic_required: bool,
    pub base: String,
}
#[derive(Deserialize, Serialize, Clone, PartialEq, Eq)]
pub struct Entry {
    pub path: String,
    pub kind: String,
    pub mode: u32,
    pub size: u64,
    pub object: Option<String>,
    pub index_object: Option<String>,
    pub index_mode: Option<String>,
    pub head_object: Option<String>,
    pub head_mode: Option<String>,
    pub base_object: Option<String>,
    pub base_mode: Option<String>,
    pub provenance: String,
}
#[derive(Deserialize, Serialize, Clone, PartialEq, Eq)]
pub struct Manifest {
    pub schema_version: u64,
    pub head: String,
    pub base: String,
    pub status: String,
    pub index: String,
    pub entries: Vec<Entry>,
    pub omissions: BTreeMap<String, String>,
    pub quiescence: String,
    pub consistency_limit: String,
}
fn git(root: &Path, args: &[&str]) -> Result<Vec<u8>> {
    let out = Command::new("git")
        .arg("-C")
        .arg(root)
        .args(args)
        .env("GIT_OPTIONAL_LOCKS", "0")
        .output()?;
    ensure!(out.status.success(), "Git inspection failed");
    Ok(out.stdout)
}
fn text(b: Vec<u8>) -> Result<String> {
    Ok(String::from_utf8(b)?.trim_end_matches('\n').into())
}
pub fn repository(root: &Path) -> Result<()> {
    ensure!(
        root.is_absolute() && root.canonicalize()? == root,
        "repository must be canonical absolute directory"
    );
    ensure!(
        text(git(root, &["rev-parse", "--show-toplevel"])?)? == root.to_string_lossy(),
        "repository must be Git root"
    );
    Ok(())
}
fn tree(repo: &Path, revision: &str) -> Result<BTreeMap<String, (String, String)>> {
    let rows = git(repo, &["ls-tree", "-r", "-z", revision])?;
    let mut out = BTreeMap::new();
    for row in rows.split(|b| *b == 0).filter(|b| !b.is_empty()) {
        let tab = row
            .iter()
            .position(|b| *b == b'\t')
            .ok_or_else(|| anyhow::anyhow!("invalid Git tree row"))?;
        let fields: Vec<_> = std::str::from_utf8(&row[..tab])?.split(' ').collect();
        ensure!(fields.len() == 3, "invalid Git tree metadata");
        out.insert(
            String::from_utf8(row[tab + 1..].to_vec())?,
            (fields[0].into(), fields[2].into()),
        );
    }
    Ok(out)
}
fn tree_blob(
    repo: &Path,
    entry: Option<&(String, String)>,
    contents: &mut BTreeMap<String, Vec<u8>>,
) -> Result<(Option<String>, Option<String>)> {
    if let Some((mode, oid)) = entry {
        ensure!(mode != "160000", "submodule unsupported");
        let bytes = git(repo, &["cat-file", "blob", oid])?;
        let id = hash(&bytes);
        contents.insert(id.clone(), bytes);
        Ok((Some(id), Some(mode.clone())))
    } else {
        Ok((None, None))
    }
}
fn scan(repo: &Path, sel: &Selection) -> Result<(Manifest, BTreeMap<String, Vec<u8>>)> {
    let head = text(git(repo, &["rev-parse", "--verify", "HEAD"])?)?;
    ensure!(!sel.base.starts_with('-'), "invalid base");
    let base = text(git(
        repo,
        &["rev-parse", "--verify", &format!("{}^{{commit}}", sel.base)],
    )?)?;
    let status = git(
        repo,
        &["status", "--porcelain=v1", "-z", "--untracked-files=all"],
    )?;
    let index = git(repo, &["ls-files", "--stage", "-z"])?;
    let all = git(
        repo,
        &[
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
    )?;
    let mut inventory: BTreeSet<String> = all
        .split(|b| *b == 0)
        .filter(|p| !p.is_empty())
        .map(|p| String::from_utf8(p.to_vec()))
        .collect::<std::result::Result<_, _>>()?;
    let head_tree = tree(repo, &head)?;
    let base_tree = tree(repo, &base)?;
    inventory.extend(head_tree.keys().cloned());
    inventory.extend(base_tree.keys().cloned());
    let selected: BTreeSet<String> = sel.paths.iter().cloned().collect();
    ensure!(
        selected.len() == sel.paths.len() && !selected.is_empty(),
        "duplicate/empty selection"
    );
    for p in inventory.iter() {
        ensure!(
            selected.contains(p) || sel.omissions.get(p).is_some_and(|x| !x.trim().is_empty()),
            "every tracked/untracked path needs selection or reasoned omission"
        );
    }
    for (p, r) in &sel.omissions {
        relative(p)?;
        ensure!(
            !selected.contains(p) && !r.trim().is_empty() && inventory.contains(p),
            "invalid/conflicting omission"
        );
    }
    let mut contents = BTreeMap::new();
    let mut entries = Vec::new();
    for p in &selected {
        relative(p)?;
        let full = repo.join(p);
        no_links(full.parent().unwrap())?;
        let sensitive = p.split('/').any(|c| {
            c.starts_with(".env")
                || ["credentials", "id_rsa", "id_ed25519"].contains(&c)
                || c.ends_with(".pem")
                || c.ends_with(".key")
        });
        ensure!(
            !sensitive || sel.acknowledged_sensitive.contains(p),
            "sensitive-looking path requires explicit acknowledgement"
        );
        let ignored = Command::new("git")
            .arg("-C")
            .arg(repo)
            .args(["check-ignore", "-q", "--", p])
            .status()?
            .success();
        ensure!(
            inventory.contains(p) || ignored,
            "selection must use exact Git inventory spelling or explicitly ignored file"
        );
        let (head_object, head_mode) = tree_blob(repo, head_tree.get(p), &mut contents)?;
        let (base_object, base_mode) = tree_blob(repo, base_tree.get(p), &mut contents)?;
        let mut index_object = None;
        let mut index_mode = None;
        for row in index.split(|b| *b == 0).filter(|b| !b.is_empty()) {
            if let Some(tab) = row.iter().position(|b| *b == b'\t')
                && &row[tab + 1..] == p.as_bytes()
            {
                let pre = std::str::from_utf8(&row[..tab])?;
                let cols: Vec<_> = pre.split(' ').collect();
                ensure!(
                    cols.len() == 3 && cols[2] == "0",
                    "unmerged index entry unsupported"
                );
                ensure!(cols[0] != "160000", "submodule unsupported");
                let bytes = git(repo, &["cat-file", "blob", cols[1]])?;
                let id = hash(&bytes);
                contents.insert(id.clone(), bytes);
                index_object = Some(id);
                index_mode = Some(cols[0].into());
            }
        }
        let provenance = if ignored {
            "explicit-ignored"
        } else if index_object.is_some() || head_object.is_some() || base_object.is_some() {
            "tracked"
        } else {
            "explicit-untracked"
        }
        .into();
        let (kind, mode, bytes) = match fs::symlink_metadata(&full) {
            Ok(m) if m.file_type().is_symlink() => (
                "symlink",
                m.permissions().mode() & 0o7777,
                Some(fs::read_link(&full)?.as_os_str().as_bytes().to_vec()),
            ),
            Ok(m) if m.is_file() => (
                "file",
                m.permissions().mode() & 0o7777,
                Some(read(&full, u64::MAX - 1)?),
            ),
            Ok(m)
                if m.is_dir()
                    && (index_object.is_some()
                        || head_object.is_some()
                        || base_object.is_some()) =>
            {
                ("deleted", 0, None)
            }
            Ok(_) => anyhow::bail!("selected path is directory or unsupported special file"),
            Err(e)
                if matches!(
                    e.kind(),
                    std::io::ErrorKind::NotFound | std::io::ErrorKind::NotADirectory
                ) =>
            {
                ensure!(
                    index_object.is_some() || head_object.is_some() || base_object.is_some(),
                    "missing untracked input"
                );
                ("deleted", 0, None)
            }
            Err(e) => return Err(e.into()),
        };
        let size = bytes.as_ref().map_or(0, |b| b.len() as u64);
        let object = bytes.map(|b| {
            let id = hash(&b);
            contents.insert(id.clone(), b);
            id
        });
        entries.push(Entry {
            path: p.clone(),
            kind: kind.into(),
            mode,
            size,
            object,
            index_object,
            index_mode,
            head_object,
            head_mode,
            base_object,
            base_mode,
            provenance,
        });
    }
    let sid = hash(&status);
    contents.insert(sid.clone(), status);
    let iid = hash(&index);
    contents.insert(iid.clone(), index);
    Ok((Manifest{schema_version:1,head,base,status:sid,index:iid,entries,omissions:sel.omissions.clone(),quiescence:sel.quiescence.clone(),consistency_limit:"coordinated quiescence; repeated scans cannot prove atomic multi-file capture against an external editor".into()},contents))
}
pub fn capture(
    repo: &Path,
    root: &Path,
    sel: &Selection,
) -> Result<(String, Manifest, Vec<String>)> {
    ensure!(
        !sel.quiescence.trim().is_empty(),
        "coordinated quiescence declaration required"
    );
    ensure!(
        !sel.atomic_required,
        "atomic multi-file guarantee unsupported: supply an immutable tree under an independently established snapshot facility"
    );
    let (before, bytes) = scan(repo, sel)?;
    fault("capture-scanned")?;
    if std::env::var("AGENTS_COLLAB_CAPTURE_PAUSE").ok().as_deref() == Some("test") {
        eprintln!("capture-scanned-test-gate");
        std::thread::sleep(std::time::Duration::from_millis(500));
    }
    let mut refs = Vec::new();
    for b in bytes.values() {
        refs.push(put(root, b)?);
    }
    let (after, _) = scan(repo, sel)?;
    ensure!(before == after, "source drift during capture");
    for (id, b) in &bytes {
        ensure!(object(root, id)? == *b, "stored copy mismatch");
    }
    let id = put(root, &encoded(&before)?)?;
    refs.push(id.clone());
    Ok((id, before, refs))
}

pub fn unchanged(repo: &Path, manifest: &Manifest) -> Result<()> {
    let sel = Selection {
        paths: manifest.entries.iter().map(|e| e.path.clone()).collect(),
        omissions: manifest.omissions.clone(),
        acknowledged_sensitive: manifest.entries.iter().map(|e| e.path.clone()).collect(),
        quiescence: manifest.quiescence.clone(),
        atomic_required: false,
        base: manifest.base.clone(),
    };
    let (current, _) = scan(repo, &sel)?;
    ensure!(
        &current == manifest,
        "live source identity changed after freeze; old review is retained only for old artifact"
    );
    Ok(())
}

// Git status alone can conceal skip-worktree/assume-unchanged files. Compare
// every index entry directly with its blob, including omitted review paths.
fn committed_tree(repo: &Path, commit: &str, frozen_index: &str) -> Result<()> {
    let index = git(repo, &["ls-files", "--stage", "-z"])?;
    ensure!(
        hash(&index) == frozen_index,
        "complete frozen index changed"
    );
    let mut staged = BTreeMap::new();
    let mut aliases = BTreeSet::new();
    let mut filesystem_names = BTreeMap::new();
    for row in index.split(|b| *b == 0).filter(|b| !b.is_empty()) {
        let tab = row
            .iter()
            .position(|b| *b == b'\t')
            .ok_or_else(|| anyhow::anyhow!("invalid Git index row"))?;
        let fields: Vec<_> = std::str::from_utf8(&row[..tab])?.split(' ').collect();
        ensure!(
            fields.len() == 3 && fields[2] == "0",
            "unmerged index unsupported"
        );
        ensure!(
            ["100644", "100755", "120000"].contains(&fields[0]),
            "submodule or unsupported index mode"
        );
        let path = std::str::from_utf8(&row[tab + 1..])?;
        relative(path)?;
        ensure!(
            aliases.insert(path.to_lowercase()),
            "unsafe case-aliased index paths"
        );
        let full = repo.join(path);
        no_links(full.parent().unwrap())?;
        // Distinct Git spellings must not resolve to one filesystem object,
        // including case/Unicode aliases in directory ancestry and hardlinks.
        let mut prefix = String::new();
        for part in path.split('/') {
            if !prefix.is_empty() {
                prefix.push('/');
            }
            prefix.push_str(part);
            let m = fs::symlink_metadata(repo.join(&prefix))?;
            if let Some(previous) = filesystem_names.insert((m.dev(), m.ino()), prefix.clone()) {
                ensure!(previous == prefix, "unsafe filesystem path alias");
            }
        }
        let meta = fs::symlink_metadata(&full)?;
        let bytes = if fields[0] == "120000" {
            ensure!(
                meta.file_type().is_symlink(),
                "tracked symlink type changed"
            );
            fs::read_link(&full)?.as_os_str().as_bytes().to_vec()
        } else {
            ensure!(
                meta.is_file() && !meta.file_type().is_symlink(),
                "tracked file type changed"
            );
            let mode = if meta.permissions().mode() & 0o100 != 0 {
                "100755"
            } else {
                "100644"
            };
            ensure!(mode == fields[0], "tracked executable mode changed");
            read(&full, u64::MAX - 1)?
        };
        ensure!(
            bytes == git(repo, &["cat-file", "blob", fields[1]])?,
            "tracked working bytes differ from committed index"
        );
        ensure!(
            staged
                .insert(
                    path.to_owned(),
                    (fields[0].to_owned(), fields[1].to_owned())
                )
                .is_none(),
            "duplicate index path"
        );
    }
    ensure!(
        staged == tree(repo, commit)?,
        "entire committed tree differs from frozen index"
    );
    ensure!(
        git(
            repo,
            &["status", "--porcelain=v1", "-z", "--untracked-files=all"]
        )?
        .is_empty(),
        "commit acceptance requires clean tracked and nonignored untracked worktree"
    );
    Ok(())
}

fn commit_scan(repo: &Path, frozen: &Manifest, commit: &str) -> Result<Manifest> {
    repository(repo)?;
    ensure!(
        commit.len() == frozen.head.len()
            && commit
                .bytes()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()),
        "exact full commit hash required"
    );
    ensure!(
        text(git(repo, &["rev-parse", "--verify", "HEAD"])?)? == commit,
        "requested commit must be current HEAD"
    );
    ensure!(
        commit != frozen.head,
        "commit must be a strict descendant of frozen HEAD"
    );
    git(repo, &["merge-base", "--is-ancestor", &frozen.head, commit])?;
    committed_tree(repo, commit, &frozen.index)?;
    let selection = Selection {
        paths: frozen.entries.iter().map(|e| e.path.clone()).collect(),
        omissions: frozen.omissions.clone(),
        acknowledged_sensitive: frozen.entries.iter().map(|e| e.path.clone()).collect(),
        quiescence: frozen.quiescence.clone(),
        atomic_required: false,
        base: frozen.base.clone(),
    };
    let (current, _) = scan(repo, &selection)?;
    ensure!(
        current.head == commit && current.index == frozen.index && current.status == hash(b""),
        "commit source changed during verification"
    );
    for (old, new) in frozen.entries.iter().zip(&current.entries) {
        ensure!(
            old.path == new.path
                && old.kind == new.kind
                && old.mode == new.mode
                && old.size == new.size
                && old.object == new.object
                && old.index_object == new.index_object
                && old.index_mode == new.index_mode,
            "selected reviewed working bytes/types/modes changed"
        );
        ensure!(
            old.object == old.index_object,
            "selected reviewed work was not staged"
        );
        let expected_mode = match old.kind.as_str() {
            "deleted" => None,
            "symlink" => Some("120000"),
            "file" if old.mode & 0o100 != 0 => Some("100755"),
            "file" => Some("100644"),
            _ => anyhow::bail!("unsupported selected working type"),
        };
        ensure!(
            old.index_mode.as_deref() == expected_mode
                && new.head_object == old.object
                && new.head_mode == old.index_mode,
            "selected working version is not represented by committed staged version"
        );
    }
    Ok(current)
}

pub fn accept_commit(repo: &Path, frozen: &Manifest, commit: &str) -> Result<Manifest> {
    let before = commit_scan(repo, frozen, commit)?;
    fault("accept-commit-scanned")?;
    if std::env::var("AGENTS_COLLAB_ACCEPT_COMMIT_PAUSE")
        .ok()
        .as_deref()
        == Some("test")
    {
        eprintln!("accept-commit-scanned-test-gate");
        std::thread::sleep(std::time::Duration::from_millis(500));
    }
    let after = commit_scan(repo, frozen, commit)?;
    ensure!(before == after, "source drift during commit acceptance");
    Ok(before)
}
