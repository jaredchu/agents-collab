use clap::Parser;
use std::path::PathBuf;

#[derive(Parser)]
#[command(
    version,
    about = "Local record-and-packet prototype. Never dispatches models."
)]
struct Args {
    /// task, artifact, packet, assignment, review, or finding
    entity: String,
    /// See docs/cli.md for the version-1 command contracts
    action: String,
    #[arg(long)]
    record: Option<PathBuf>,
    #[arg(long)]
    input: Option<PathBuf>,
    #[arg(long)]
    profile: Option<PathBuf>,
    #[arg(long)]
    key: Option<String>,
    #[arg(long)]
    expect: Option<u64>,
    #[arg(long)]
    actor: Option<String>,
    #[arg(long)]
    json: bool,
}
fn main() {
    let a = Args::parse();
    let result = agents_collab::run(agents_collab::Request {
        command: format!("{} {}", a.entity, a.action),
        record: a.record,
        input: a.input,
        profile: a.profile,
        key: a.key,
        expect: a.expect,
        actor: a.actor,
    });
    match result {
        Ok(v) => {
            if a.json {
                println!(
                    "{}",
                    serde_json::json!({"schema_version":1,"ok":true,"data":v})
                );
            } else {
                println!("{}", serde_json::to_string_pretty(&v).unwrap());
            }
        }
        Err(e) => {
            if a.json {
                println!(
                    "{}",
                    serde_json::json!({"schema_version":1,"ok":false,"error":{"kind":"operation_rejected","message":e.to_string()}})
                );
            } else {
                eprintln!("error: {e:#}");
            }
            std::process::exit(1);
        }
    }
}
