#!/usr/bin/env fish
# team.fish — Spawn N Claude Code instances in parallel tmux panes
#
# Usage:
#   ./scripts/team.fish "prompt 1" "prompt 2" "prompt 3"
#
# Each prompt gets its own tmux pane running a Claude CLI instance.
# Results are written to /tmp/team-results-<RUN_ID>/result-N.json

set -l PROJECT_ROOT (cd (dirname (status filename))/..; and pwd)
set -l RUN_ID (date +%s)-(random)
set -l RESULTS_DIR /tmp/team-results-$RUN_ID
set -l WINDOW_NAME "team-$RUN_ID"

# --- Validate args ---
if test (count $argv) -lt 1
    echo "Usage: team.fish \"prompt 1\" \"prompt 2\" [\"prompt 3\" ...]"
    exit 1
end

set -l NUM_AGENTS (count $argv)

echo "=== Browser Agent Team ==="
echo "  Agents:     $NUM_AGENTS"
echo "  Results:    $RESULTS_DIR"
echo "  Run ID:     $RUN_ID"
echo ""

# --- Create results directory ---
mkdir -p $RESULTS_DIR

# --- Build the wrapper prompt for each agent ---
# Each Claude instance gets told to cd to the project, run browser_agent.py,
# and write structured output.

function build_prompt -a task_prompt agent_id results_dir project_root
    echo "You are browser agent #$agent_id in a parallel team.

Your task:
$task_prompt

## Instructions

1. cd to $project_root
2. Run the browser agent:
   \`\`\`bash
   cd $project_root && .venv/bin/python scripts/browser_agent.py --task \"$task_prompt\" --visible
   \`\`\`
3. Read the JSON output from the command.
4. Write the final result JSON to: $results_dir/result-$agent_id.json using the Write tool.
   The JSON should have this structure:
   {\"agent_id\": $agent_id, \"success\": true/false, \"task\": \"...\", \"result\": \"...\", \"error\": null}
5. If the browser agent fails, still write the result file with success=false and the error message.

IMPORTANT: You MUST write the result file before finishing. The orchestrator is waiting for it."
end

# --- Ensure we're in a tmux session ---
if not set -q TMUX
    echo "Error: Not inside a tmux session. Run this from within tmux."
    exit 1
end

# --- Create a new tmux window with the first agent ---
set -l first_prompt (build_prompt "$argv[1]" 1 $RESULTS_DIR $PROJECT_ROOT)

# Escape the prompt for shell embedding
set -l escaped_prompt (string escape -- "$first_prompt")

tmux new-window -n $WINDOW_NAME \
    "claude -p $escaped_prompt --dangerously-skip-permissions --verbose 2>&1 | tee $RESULTS_DIR/log-1.txt; echo '[Agent 1 done]'; sleep 2"

# --- Split panes for remaining agents ---
for i in (seq 2 $NUM_AGENTS)
    set -l agent_prompt (build_prompt "$argv[$i]" $i $RESULTS_DIR $PROJECT_ROOT)
    set -l escaped (string escape -- "$agent_prompt")

    tmux split-window -t $WINDOW_NAME \
        "claude -p $escaped --dangerously-skip-permissions --verbose 2>&1 | tee $RESULTS_DIR/log-$i.txt; echo '[Agent $i done]'; sleep 2"

    # Re-tile after each split to keep layout clean
    tmux select-layout -t $WINDOW_NAME tiled
end

echo "  Tmux window: $WINDOW_NAME"
echo "  All $NUM_AGENTS agents launched."
echo ""

# --- Poll for completion ---
echo "Waiting for all agents to complete..."

set -l TIMEOUT 600  # 10 minute timeout
set -l elapsed 0

while test $elapsed -lt $TIMEOUT
    set -l done_count 0
    for i in (seq 1 $NUM_AGENTS)
        if test -f $RESULTS_DIR/result-$i.json
            set done_count (math $done_count + 1)
        end
    end

    if test $done_count -eq $NUM_AGENTS
        echo ""
        echo "=== All $NUM_AGENTS agents complete! ==="
        echo ""

        # Print summary
        for i in (seq 1 $NUM_AGENTS)
            echo "--- Agent $i ---"
            if test -f $RESULTS_DIR/result-$i.json
                cat $RESULTS_DIR/result-$i.json
            else
                echo '{"error": "No result file found"}'
            end
            echo ""
        end

        echo "Results directory: $RESULTS_DIR"
        exit 0
    end

    # Progress update every 15 seconds
    if test (math $elapsed % 15) -eq 0; and test $elapsed -gt 0
        echo "  [$elapsed""s] $done_count/$NUM_AGENTS agents complete..."
    end

    sleep 3
    set elapsed (math $elapsed + 3)
end

echo ""
echo "=== TIMEOUT after $TIMEOUT seconds ==="
echo "Some agents did not complete. Partial results in: $RESULTS_DIR"

for i in (seq 1 $NUM_AGENTS)
    if test -f $RESULTS_DIR/result-$i.json
        echo "  Agent $i: DONE"
    else
        echo "  Agent $i: INCOMPLETE (check $RESULTS_DIR/log-$i.txt)"
    end
end

exit 1
