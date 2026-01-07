# Agentic Data Curator 

**A Model Context Protocol (MCP) Server for Semantically Valid Dataset Generation.**

This tool allows CLI Agents (like Claude Code, Codex, Aider, OpenInterpreter) to build high-quality, semantically unique datasets. The meta layer applies a **Validation Loop** at generation time.

If an Agent tries to write a row that is semantically similar to an existing row, this tool rejects the write and forces the Agent to generate a new, unique variant.

## The Framework 

1.  **Plan:** Agent generates a row (e.g., a logical fallacy).
2.  **Guard:** Agent attempts to write. The tool runs `difflib` & Jaccard similarity checks against the CSV.
3.  **Feedback:** 
    *   If **Unique**: Write is successful.
    *   If **Duplicate**: Tool raises an error with the similar row found.
4.  **Correct:** The Agent reads the error, understands *why* it failed, and generates a better example immediately.

## Components

*   `dataset_guard.py`: Fuzzy-logic validator. Checks token similarity and character distance.
*   `dataset_append.py`: Schema-aware CSV writer. Handles new columns, timestamps, and file creation.
*   `dataset_server.py`: The MCP wrapper that exposes these as a single tool (`save_generated_data`).

## Installation

This project uses **uv** for dependency management. You do not need to manually create virtual environments.

**Prerequisites:**
*   [uv](https://github.com/astral-sh/uv) (`brew install uv` or `pip install uv`)

## Configuration

Add this to your Claude Desktop config (or any MCP-compliant client).

**File:**
*   **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
*   **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Config JSON:**
```json
{
  "mcpServers": {
    "data-curator": {
      "command": "uv",
      "args": [
        "run",
        "/ABSOLUTE/PATH/TO/dataset_server.py"
      ]
    }
  }
}
```

*(Note: Replace `/ABSOLUTE/PATH/TO/` with the actual file path. `uv` will automatically read the script headers and install the necessary dependencies.)*

## Usage

Once connected, the Agent will see a tool named `save_generated_data`. You don't need to explain the scripts to the Agent. Simply prompt it with the columns you want your final output to be and how many generations to make.

### Tool Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `target_file` | string | Yes | Full path to the CSV (e.g., `/Users/you/data/fallacies.csv`) |
| `check_col` | string | Yes | Column name to check for duplicates (e.g., `text`) |
| `data` | dict | Yes | Dictionary of column values (e.g., `{'text': '...', 'label': '...'}`) |
| `threshold` | float | No | Character similarity threshold (0.0–1.0). Default `0.78` |

### File Behavior

- If the target CSV doesn't exist, a new one is created with a UTC-timestamped filename (e.g., `dataset_20260107T235119Z.csv`).
- A `timestamp` column is automatically added to each row.
- New columns are automatically added to the schema if your `data` dict includes keys not yet in the CSV.

**Example Prompt:**

Please build a dataset of logical fallacies (and non-fallacies) using the `save_generated_data` tool.

Generate 50 unique rows of data. Iterate through the list of 11 types below to ensure a balanced distribution.

For every row, pass the following dictionary to the tool:
- `fallacy_type`: The name of the fallacy (from the list below).
- `is_sound`: "yes" or "no".
- `is_valid`: "yes" or "no".
- `text`: The actual example sentence or argument.

- If `fallacy_type` is "No fallacy", then `is_sound` and `is_valid` MUST both be yes".
- For all other fallacies, determine soundness and validity logically based on the error.


Fallacies to use

1. **Ad hominem:** Attacking the person instead of the argument.
2. **Straw man:** Misrepresenting someone's view to make it easier to refute.
3. **False dilemma:** Presenting only two options when more exist.
4. **Slippery slope:** Claiming a small step will inevitably lead to extreme outcomes.
5. **Hasty generalization:** Drawing a broad conclusion from too little evidence.
6. **Post hoc:** Assuming "after" means "because of."
7. **Circular reasoning:** The conclusion is assumed in the premises.
8. **Appeal to authority:** Treating an authority's claim as proof (especially outside expertise).
9. **Appeal to emotion:** Using feelings (fear, pity, outrage) in place of reasons.
10. **Red herring:** Distracting with an irrelevant point to avoid the real issue.
11. **No fallacy:** A valid and true statement (sound argument).


### How the Rejection Loop Works

Since the validation script outputs the existing text, the Agent acts on specific feedback:

### Example Agent Behavior 

1.  **Agent:** Decides to generate a "Straw Man" fallacy.
    *   *Action:* Calls `save_generated_data` with `text="You hate animals"`.
2.  **Tool:** Returns: `"Success. Appended row."`
3.  **Agent:** Gets lazy and tries a slight variation.
    *   *Action:* Calls `save_generated_data` with `text="You just hate animals"`.
4.  **Tool Error:** 
    ```text
    VALIDATION FAILED:
    REJECTED: Similar to existing row
    Row: 2
    Char-sim: 0.94 (threshold 0.78)
    Token-Jaccard: 0.85 (threshold 0.60)
    Existing: You hate animals
    Proposed: You just hate animals
    Instruction: Generate a significantly different example.
    ```
5.  **Agent:** *Internal Monologue:* "My previous attempt was rejected because it was 94% similar to the 'animals' argument. I need to change the topic completely."
6.  **Agent:** Generates a new variant.
    *   *Action:* Calls `save_generated_data` with `text="So you want to fire the analyst because of one bad budget report?"`.
7.  **Tool:** Returns: `"Success. Appended row."`


## License

MIT# Genguard
