//! Provider-neutral tool call/result integrity checks for structural strategies.

use std::collections::HashSet;

use serde_json::Value;

#[derive(Debug, Default)]
struct ToolLinks {
    calls: HashSet<String>,
    results: HashSet<String>,
    has_protocol: bool,
    has_unlinked: bool,
}

impl ToolLinks {
    fn merge(&mut self, other: Self) {
        self.calls.extend(other.calls);
        self.results.extend(other.results);
        self.has_protocol |= other.has_protocol;
        self.has_unlinked |= other.has_unlinked;
    }

    fn add_call(&mut self, id: Option<&str>) {
        self.has_protocol = true;
        if let Some(id) = id.filter(|id| !id.is_empty()) {
            self.calls.insert(id.to_string());
        } else {
            self.has_unlinked = true;
        }
    }

    fn add_result(&mut self, id: Option<&str>) {
        self.has_protocol = true;
        if let Some(id) = id.filter(|id| !id.is_empty()) {
            self.results.insert(id.to_string());
        } else {
            self.has_unlinked = true;
        }
    }
}

fn links_for_value(value: &Value) -> ToolLinks {
    let mut links = ToolLinks::default();

    if let Some(tool_calls) = value.get("tool_calls").and_then(Value::as_array) {
        for call in tool_calls {
            links.add_call(call.get("id").and_then(Value::as_str));
        }
    }

    if value.get("role").and_then(Value::as_str) == Some("tool")
        || value.get("tool_call_id").is_some()
    {
        links.add_result(value.get("tool_call_id").and_then(Value::as_str));
    }

    if let Some(item_type) = value.get("type").and_then(Value::as_str) {
        let is_result = item_type == "tool_result"
            || item_type.ends_with("_tool_result")
            || item_type.ends_with("_call_output");
        let is_call = item_type == "tool_use"
            || item_type.ends_with("_tool_use")
            || item_type.ends_with("_call");

        if is_result {
            links.add_result(
                value
                    .get("tool_use_id")
                    .or_else(|| value.get("call_id"))
                    .and_then(Value::as_str),
            );
        } else if is_call {
            links.add_call(
                value
                    .get("id")
                    .or_else(|| value.get("call_id"))
                    .and_then(Value::as_str),
            );
        } else if item_type.contains("tool") {
            links.has_protocol = true;
            links.has_unlinked = true;
        }
    }

    if let Some(content) = value.get("content").and_then(Value::as_array) {
        for block in content {
            links.merge(links_for_value(block));
        }
    }

    links
}

pub(crate) fn contains_tool_protocol(item: &Value) -> bool {
    links_for_value(item).has_protocol
}

fn links_for_items(items: &[Value]) -> ToolLinks {
    let mut links = ToolLinks::default();
    for item in items {
        links.merge(links_for_value(item));
    }
    links
}

fn intersects(left: &HashSet<String>, right: &HashSet<String>) -> bool {
    left.iter().any(|id| right.contains(id))
}

/// Return whether replacing `items[start..end]` preserves every tool call/result
/// relationship that touches the replacement boundaries.
pub(crate) fn snapshot_range_preserves_tool_pairs(
    items: &[Value],
    start: usize,
    end: usize,
) -> bool {
    if start >= end || end > items.len() {
        return false;
    }

    let left = links_for_items(&items[..start]);
    let inside = links_for_items(&items[start..end]);
    let right = links_for_items(&items[end..]);
    let crosses = |first: &ToolLinks, second: &ToolLinks| {
        intersects(&first.calls, &second.results) || intersects(&first.results, &second.calls)
    };
    if crosses(&left, &inside) || crosses(&inside, &right) || crosses(&left, &right) {
        return false;
    }

    let all = links_for_items(items);
    let boundary_indices = [
        start.checked_sub(1),
        Some(start),
        end.checked_sub(1),
        (end < items.len()).then_some(end),
    ];
    boundary_indices.into_iter().flatten().all(|index| {
        let links = links_for_value(&items[index]);
        !links.has_unlinked
            && links.calls.iter().all(|id| all.results.contains(id))
            && links.results.iter().all(|id| all.calls.contains(id))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn classifies_tool_protocol_items_across_provider_shapes() {
        let tool_items = [
            json!({
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "large explanation"},
                    {"type": "tool_use", "id": "toolu_1", "name": "search", "input": {}}
                ]
            }),
            json!({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "toolu_1", "content": "result"}
                ]
            }),
            json!({
                "role": "assistant",
                "content": "calling",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "search", "arguments": "{}"}
                    }
                ]
            }),
            json!({"role": "tool", "tool_call_id": "call_1", "content": "result"}),
            json!({
                "type": "function_call",
                "call_id": "call_2",
                "name": "search",
                "arguments": "{}"
            }),
            json!({
                "type": "function_call_output",
                "call_id": "call_2",
                "output": "result"
            }),
        ];

        for item in tool_items {
            assert!(
                contains_tool_protocol(&item),
                "expected tool protocol item: {item}"
            );
        }
        assert!(!contains_tool_protocol(
            &json!({"role": "user", "content": "ordinary text"})
        ));
    }

    #[test]
    fn snapshot_range_accepts_complete_pairs_inside_or_outside() {
        let anthropic = vec![
            json!({"role": "user", "content": "frozen"}),
            json!({"role": "assistant", "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "search", "input": {}}
            ]}),
            json!({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}
            ]}),
            json!({"role": "user", "content": "tail"}),
        ];
        assert!(snapshot_range_preserves_tool_pairs(&anthropic, 1, 3));

        let openai_chat = vec![
            json!({"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "search", "arguments": "{}"}}
            ]}),
            json!({"role": "tool", "tool_call_id": "call_1", "content": "ok"}),
            json!({"role": "user", "content": "snapshot me"}),
            json!({"role": "user", "content": "tail"}),
        ];
        assert!(snapshot_range_preserves_tool_pairs(&openai_chat, 2, 3));

        let responses = vec![
            json!({"type": "function_call", "call_id": "call_2", "name": "search", "arguments": "{}"}),
            json!({"type": "function_call_output", "call_id": "call_2", "output": "ok"}),
            json!({"type": "message", "role": "user", "content": "tail"}),
        ];
        assert!(snapshot_range_preserves_tool_pairs(&responses, 0, 2));
    }

    #[test]
    fn snapshot_range_rejects_cross_boundary_and_unlinked_tools() {
        let crossing = vec![
            json!({"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "search", "arguments": "{}"}}
            ]}),
            json!({"role": "tool", "tool_call_id": "call_1", "content": "ok"}),
            json!({"role": "user", "content": "tail"}),
        ];
        assert!(!snapshot_range_preserves_tool_pairs(&crossing, 0, 1));

        let unlinked = vec![
            json!({"role": "user", "content": "old"}),
            json!({"role": "assistant", "content": [
                {"type": "tool_use", "name": "search", "input": {}}
            ]}),
            json!({"role": "user", "content": "tail"}),
        ];
        assert!(!snapshot_range_preserves_tool_pairs(&unlinked, 0, 2));
    }
}
