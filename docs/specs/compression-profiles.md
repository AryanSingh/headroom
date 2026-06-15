# Cross-Session Compression Profiles

## Problem Statement

Headroom starts cold every session. After 10 sessions in the same codebase, it has learned:
- Which file types compress safely without losing critical information
- Which content always gets retrieved via CCR (Compress-Cache-Retrieve) — a signal that it was over-compressed
- Which tool outputs are almost always irrelevant to the task
- Optimal compression ratio targets per content type

Currently, this learning is lost between sessions. Each new session must re-learn these patterns from scratch, resulting in:
- Suboptimal compression decisions in early sessions
- Unnecessary CCR retrievals (costly token usage)
- Inability to personalize compression to a specific codebase's characteristics

## Motivation

A compression profile stores observed patterns and applies them automatically to future sessions — making each session better than the last. After 5-10 sessions in a codebase, compression quality should be noticeably better due to:
- Smarter compression targets per file type
- Reduced CCR retrieval rates (content is not over-compressed)
- Context-aware decisions based on what worked in the past

## User Stories

**Story 1: Automatic Profile Loading**
As a user working in a large monorepo, I want Headroom to automatically load my codebase's compression profile from the previous 10 sessions so that compression is better-tuned from the start, without any manual configuration.

**Story 2: Profile Learning from CCR Signals**
As a developer, I want Headroom to track when I retrieve compressed content via CCR (indicating over-compression) and use that signal to adjust future compression targets, so that fewer retrievals are needed in future sessions.

**Story 3: Performance Monitoring**
As an ops engineer, I want to see a summary of my codebase's compression profile to understand: "Which file types are most likely to be over-compressed? What is the typical retrieval rate?" This helps me understand where compression is struggling.

**Story 4: Multi-Workspace Independence**
As a developer working in multiple codebases, I want each codebase to maintain its own compression profile based on the workspace's git remote URL and root path, so compression tuning for one project does not affect another.

## Technical Design

### Profile Data Model

A compression profile contains per-content-type statistics:

```
ContentTypeStats:
  - content_type: str (e.g., "python_file", "json_api_response")
  - sessions_seen: int (number of sessions this type was compressed)
  - avg_compression_ratio: float (average ratio of original items to compressed items)
  - retrieval_rate: float (fraction of compressions that triggered CCR retrieval)
  - recommended_ratio: float (recommended target compression ratio for future sessions)
```

Example:
```
{
  "json_search_results": {
    "sessions_seen": 5,
    "avg_compression_ratio": 0.3,      # Down to 30% of original
    "retrieval_rate": 0.15,             # 15% of compressions triggered retrieval
    "recommended_ratio": 0.4             # Next session: target 40% (less aggressive)
  },
  "python_source": {
    "sessions_seen": 8,
    "avg_compression_ratio": 0.8,
    "retrieval_rate": 0.05,             # Low retrieval rate = compression working
    "recommended_ratio": 0.8
  }
}
```

### Learning Signal: Retrieval Events

After each session, the profile updates with:
- Observed compression ratios (how much was actually compressed)
- CCR retrieval rates (content that was retrieved = was over-compressed)
- Session count

**Retrieval Rate Interpretation**:
- **Retrieval rate > 50%**: Content is being over-compressed. Increase target ratio (compress less).
- **Retrieval rate 20-50%**: Marginal compression quality. Keep current target or adjust slightly.
- **Retrieval rate < 20%**: Compression is working well. Current target is good.

### Profile Storage

Profiles are stored locally in `~/.headroom/profiles/{workspace_hash}.json`, where `workspace_hash` is derived from:

```
SHA-256(git_remote_url + ":" + repo_root_path)[:16]
```

Example path:
```
~/.headroom/profiles/a1b2c3d4e5f6g7h8.json
```

**Privacy**: Profiles are local-only. Workspace hashes are salted and truncated. No data leaves the machine.

### Profile Application

Before compression in a session:
1. Load profile for current workspace
2. For each content type being compressed:
   - Look up the recommended compression ratio
   - Pass to UniversalCompressor as `compression_ratio_target`
3. Compressor uses profile hint to make smarter decisions

### Profile Update

After each session:
1. Collect session statistics: list of (content_type, original_count, compressed_count) tuples
2. If content was retrieved via CCR, record `retrieval_event(content_type)`
3. Update profile:
   - `sessions_seen += 1`
   - `avg_compression_ratio = (avg * (sessions_seen - 1) + current) / sessions_seen`
   - `retrieval_rate = (retrievals / compressions)`
   - `recommended_ratio = adjust based on retrieval_rate thresholds`
4. Save profile to disk

### Workspace Identity

Two heuristics identify a workspace:
1. **Git remote URL** (if available): `git remote get-url origin`
2. **Repository root path**: Canonical path of current working directory

Combined hash (SHA-256, truncated to 16 hex chars):
```python
workspace_hash = SHA256(f"{git_remote}:{repo_root}".encode())[:16]
```

If not in a git repository, fall back to repository root path alone.

## API Design

### CompressionProfile Class

```python
class CompressionProfile:
    """Manages per-workspace compression profiles."""
    
    @classmethod
    def load(workspace_dir: Path | None = None) -> CompressionProfile:
        """Load profile for current workspace.
        
        Args:
            workspace_dir: Override workspace directory. Defaults to cwd.
            
        Returns:
            Profile (empty if first session).
        """
    
    def save() -> None:
        """Save profile to disk at ~/.headroom/profiles/{workspace_hash}.json"""
    
    def record_session(session_id: str, stats: list[dict]) -> None:
        """Update profile from session statistics.
        
        Args:
            session_id: Unique session identifier.
            stats: List of dicts with keys:
                - content_type: str
                - original_count: int
                - compressed_count: int
        """
    
    def get_compression_target(content_type: str) -> float:
        """Get recommended compression ratio for content type.
        
        Returns:
            Compression ratio in [0.0, 1.0] where 0 = fully compressed.
        """
    
    def update_from_ccr_retrieval(content_type: str) -> None:
        """Signal that content was retrieved via CCR (was over-compressed)."""
    
    def _workspace_hash() -> str:
        """Compute workspace identity hash."""
    
    def summary() -> dict:
        """Human-readable profile summary for monitoring."""
```

### ProfileManager Class

Singleton for managing profiles across sessions:

```python
class ProfileManager:
    """Manages compression profile lifecycle."""
    
    @classmethod
    def get_profile(workspace_dir: Path | None = None) -> CompressionProfile:
        """Get or load profile, with caching."""
    
    @classmethod
    def clear_cache() -> None:
        """Clear cached profiles (testing)."""
```

## Success Metrics

1. **Session-over-session improvement**: CCR retrieval rate should decrease over time as the profile learns what not to over-compress.
   - Session 1: baseline
   - Session 5: retrieval rate should drop 10-30%
   - Session 10: retrieval rate should drop 20-50%

2. **Content-type accuracy**: Per-content-type retrieval rates should stabilize, indicating the profile has learned each type's characteristics.

3. **Workspace stability**: Same workspace should have consistent retrieval patterns across sessions, showing the profile is being applied correctly.

## Privacy & Security

- **Local-only**: Profiles never leave the machine. No network communication.
- **Salted hashes**: Workspace hashes use SHA-256 truncated to 16 hex chars, salted by git remote URL or repo path.
- **No PII**: Profiles contain only compression statistics, no file contents or names.
- **User control**: Profiles stored in `~/.headroom/profiles/` (user's home directory).

## Future Enhancements

1. **Cross-workspace patterns** (TOIN): Share anonymized patterns across users to learn universal compression characteristics for Python, JSON, etc.
2. **Field-level profiles**: Track which fields are most commonly searched, recommend field preservation strategies.
3. **Temporal profiles**: Track if compression quality varies by time of day or file size.
4. **Profile merging**: Combine profiles from related workspaces (monorepos with shared compression characteristics).
