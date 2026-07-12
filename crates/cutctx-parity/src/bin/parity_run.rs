//! `parity-run` CLI: drive the parity harness from the command line.

use anyhow::Result;
use clap::{Parser, Subcommand};
use cutctx_parity::{builtin_comparators, run_comparator};
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "parity-run", about = "Run Cutctx Rust-vs-Python parity checks")]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// Run all built-in comparators against fixtures under --fixtures.
    Run {
        #[arg(long, default_value = "tests/parity/fixtures")]
        fixtures: PathBuf,
        /// Only run this comparator (by transform name).
        #[arg(long)]
        only: Option<String>,
        /// Permit skipped fixtures for this transform. Repeat for every
        /// intentionally unsupported transform; all other skips fail the run.
        #[arg(long = "allow-skipped-transform")]
        allow_skipped_transforms: Vec<String>,
    },
    /// List the transforms the harness knows about.
    List,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::List => {
            for c in builtin_comparators() {
                println!("{}", c.name());
            }
            Ok(())
        }
        Cmd::Run {
            fixtures,
            only,
            allow_skipped_transforms,
        } => {
            let mut any_diffs = false;
            let mut any_unexpected_skips = false;
            for comparator in builtin_comparators() {
                if let Some(ref filt) = only {
                    if filt != comparator.name() {
                        continue;
                    }
                }
                let report = run_comparator(&fixtures, comparator.as_ref())?;
                println!(
                    "[{:<16}] total={} matched={} skipped={} diffed={}",
                    comparator.name(),
                    report.total(),
                    report.matched,
                    report.skipped.len(),
                    report.diffed.len()
                );
                for (path, reason) in &report.skipped {
                    println!("  skipped {}: {}", path.display(), reason);
                }
                if !report.skipped.is_empty()
                    && !allow_skipped_transforms
                        .iter()
                        .any(|name| name == comparator.name())
                {
                    any_unexpected_skips = true;
                    eprintln!(
                        "  ERROR: skipped fixtures are not allowed for {}; \
                         pass --allow-skipped-transform {} only for an intentional gap",
                        comparator.name(),
                        comparator.name()
                    );
                }
                for (path, expected, actual) in &report.diffed {
                    any_diffs = true;
                    println!("  DIFF {}", path.display());
                    println!("    expected: {}", first_line(expected));
                    println!("    actual  : {}", first_line(actual));
                }
            }
            if any_diffs || any_unexpected_skips {
                std::process::exit(1);
            }
            Ok(())
        }
    }
}

fn first_line(s: &str) -> String {
    s.lines().next().unwrap_or("").to_string()
}
