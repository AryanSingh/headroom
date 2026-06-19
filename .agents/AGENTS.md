
## Model Delegation Rule
When executing complex workflows:
- **Planning and Verification**: Must be performed by **Gemini** models (the main agent).
- **Implementation**: Must be delegated to subagents explicitly configured to use the **opencode go** and **Mimo v 2.5** models. Do not implement code directly with Gemini if a multi-step implementation is required; instead, spawn these specific subagents to execute the coding tasks.
- **Fallback Mechanism**: If the 'opencode go' or 'Mimo v 2.5' subagents are unable to fix or implement the code after a certain number of attempts (e.g. 3 tries), the Gemini model (main agent) should take over implementation to unblock the task.
