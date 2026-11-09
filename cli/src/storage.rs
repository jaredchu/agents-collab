use anyhow::{Context, Result, bail, ensure};
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    os::unix::fs::{OpenOptionsExt, PermissionsExt},
    path::{Component, Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

pub fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}
pub fn hash(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}
pub fn encoded<T: Serialize>(v: &T) -> Result<Vec<u8>> {
    Ok(serde_json::to_vec(v)?)
}
// Unlike Value's default deserializer, this rejects duplicate keys at every depth.
struct Unique(Value);
impl<'de> Deserialize<'de> for Unique {
    fn deserialize<D: Deserializer<'de>>(d: D) -> std::result::Result<Self, D::Error> {
        struct Visitor;
        impl<'de> serde::de::Visitor<'de> for Visitor {
            type Value = Unique;
            fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
                f.write_str("JSON without duplicate keys")
            }
            fn visit_map<A: serde::de::MapAccess<'de>>(
                self,
                mut a: A,
            ) -> std::result::Result<Unique, A::Error> {
                let mut m = serde_json::Map::new();
                while let Some((k, v)) = a.next_entry::<String, Unique>()? {
                    if m.insert(k, v.0).is_some() {
                        return Err(serde::de::Error::custom("duplicate JSON key"));
                    }
                }
                Ok(Unique(Value::Object(m)))
            }
            fn visit_seq<A: serde::de::SeqAccess<'de>>(
                self,
                mut a: A,
            ) -> std::result::Result<Unique, A::Error> {
                let mut v = Vec::new();
                while let Some(x) = a.next_element::<Unique>()? {
                    v.push(x.0);
                }
                Ok(Unique(Value::Array(v)))
            }
            fn visit_str<E: serde::de::Error>(self, v: &str) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::String(v.into())))
            }
            fn visit_string<E: serde::de::Error>(
                self,
                v: String,
            ) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::String(v)))
            }
            fn visit_bool<E: serde::de::Error>(self, v: bool) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::Bool(v)))
            }
            fn visit_u64<E: serde::de::Error>(self, v: u64) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::from(v)))
            }
            fn visit_i64<E: serde::de::Error>(self, v: i64) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::from(v)))
            }
            fn visit_f64<E: serde::de::Error>(self, v: f64) -> std::result::Result<Unique, E> {
                Ok(Unique(
                    serde_json::Number::from_f64(v)
                        .map(Value::Number)
                        .ok_or_else(|| E::custom("nonfinite number"))?,
                ))
            }
            fn visit_unit<E: serde::de::Error>(self) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::Null))
            }
        }
        d.deserialize_any(Visitor)
    }
}
pub fn parse<T: serde::de::DeserializeOwned>(b: &[u8]) -> Result<T> {
    let mut de = serde_json::Deserializer::from_slice(b);
    let v = Unique::deserialize(&mut de)?.0;
    de.end()?;
    Ok(serde_json::from_value(v)?)
}
pub fn read(path: &Path, limit: u64) -> Result<Vec<u8>> {
    let mut f = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NONBLOCK | libc::O_NOCTTY)
        .open(path)
        .context("input unavailable")?;
    ensure!(f.metadata()?.is_file(), "input is not a regular file");
    let mut b = Vec::new();
    (&mut f).take(limit + 1).read_to_end(&mut b)?;
    ensure!(b.len() as u64 <= limit, "input exceeds size limit");
    Ok(b)
}
pub fn component(s: &str) -> Result<()> {
    ensure!(crate::profile::name(s), "unsafe project/task component");
    Ok(())
}
pub fn relative(s: &str) -> Result<()> {
    ensure!(
        !s.is_empty() && !s.contains('\\') && !s.chars().any(|c| c.is_control()),
        "invalid relative path"
    );
    ensure!(
        Path::new(s)
            .components()
            .all(|c| matches!(c, Component::Normal(_))),
        "path traversal/absolute path rejected"
    );
    ensure!(
        s.split('/').all(|x| !x.is_empty()),
        "non-normalized path rejected"
    );
    ensure!(
        !s.split('/').any(|x| x == ".git"),
        "Git metadata cannot be selected"
    );
    Ok(())
}
pub fn no_links(path: &Path) -> Result<()> {
    let mut p = PathBuf::new();
    for c in path.components() {
        p.push(c);
        if let Ok(m) = fs::symlink_metadata(&p) {
            ensure!(
                !m.file_type().is_symlink(),
                "symlink in storage/path ancestry"
            );
        }
    }
    Ok(())
}
pub fn overlap(a: &Path, b: &Path) -> bool {
    a.starts_with(b) || b.starts_with(a)
}
pub fn dir(path: &Path) -> Result<()> {
    no_links(path)?;
    if !path.exists() {
        match fs::create_dir(path) {
            Ok(()) => (),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => (),
            Err(e) => return Err(e.into()),
        };
        fs::set_permissions(path, fs::Permissions::from_mode(0o700))?;
        File::open(path.parent().unwrap())?.sync_all()?;
    }
    ensure!(path.is_dir(), "storage path is not directory");
    Ok(())
}
pub fn fault(label: &str) -> Result<()> {
    let setting = std::env::var("AGENTS_COLLAB_FAULT").unwrap_or_default();
    if setting == format!("crash:{label}") {
        unsafe { libc::_exit(86) }
    }
    if setting == label {
        bail!("injected fault: {label}");
    }
    if label == "object-written" && setting == "no-space" {
        return Err(std::io::Error::from_raw_os_error(libc::ENOSPC).into());
    }
    Ok(())
}
#[cfg(target_os = "macos")]
pub fn supported_storage(path: &Path) -> Result<()> {
    use std::{
        ffi::{CStr, CString},
        mem::MaybeUninit,
        os::unix::ffi::OsStrExt,
    };
    let p = CString::new(path.as_os_str().as_bytes())?;
    let mut stat = MaybeUninit::<libc::statfs>::uninit();
    ensure!(
        unsafe { libc::statfs(p.as_ptr(), stat.as_mut_ptr()) } == 0,
        "cannot inspect storage filesystem"
    );
    let stat = unsafe { stat.assume_init() };
    let kind = unsafe { CStr::from_ptr(stat.f_fstypename.as_ptr()) }.to_str()?;
    ensure!(
        kind == "apfs" && stat.f_flags & (libc::MNT_LOCAL as u32) != 0,
        "prototype supports local APFS storage only; no network volume fallback"
    );
    Ok(())
}
#[cfg(not(target_os = "macos"))]
pub fn supported_storage(_path: &Path) -> Result<()> {
    bail!(
        "prototype storage support is currently limited to local APFS on macOS; other platforms unvalidated"
    )
}

pub fn put(root: &Path, bytes: &[u8]) -> Result<String> {
    no_links(&root.join("staging"))?;
    let id = hash(bytes);
    let target = root.join("objects").join(&id);
    no_links(&target)?;
    if target.exists() {
        ensure!(
            read(&target, u64::MAX - 1)? == bytes,
            "existing object corrupted"
        );
        return Ok(id);
    }
    let stage = root
        .join("staging")
        .join(format!("{}-{}-{}", std::process::id(), now(), id));
    let mut f = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&stage)?;
    f.write_all(bytes)?;
    fault("object-written")?;
    f.sync_all()?;
    fault("object-synced")?;
    // hard_link atomically publishes without replacing a concurrently existing name.
    match fs::hard_link(&stage, &target) {
        Ok(()) => (),
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => ensure!(
            read(&target, u64::MAX - 1)? == bytes,
            "object collision/corruption"
        ),
        Err(e) => return Err(e.into()),
    };
    File::open(root.join("objects"))?.sync_all()?;
    fault("object-published")?;
    fs::remove_file(&stage)?;
    File::open(root.join("staging"))?.sync_all()?;
    Ok(id)
}
pub fn object(root: &Path, id: &str) -> Result<Vec<u8>> {
    ensure!(
        id.len() == 64
            && id
                .bytes()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()),
        "invalid object identity"
    );
    let p = root.join("objects").join(id);
    no_links(&p)?;
    let b = read(&p, u64::MAX - 1)?;
    ensure!(hash(&b) == id, "object hash mismatch");
    Ok(b)
}
pub fn verify(root: &Path, refs: &BTreeMap<String, String>) -> Result<()> {
    for id in refs.keys() {
        object(root, id)?;
    }
    Ok(())
}
