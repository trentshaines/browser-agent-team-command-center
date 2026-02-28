# browser-use Visual Feedback Options

browser-use has solid visual feedback support, even fully headless.

## Built-in Options

### 1. GIF Generation (post-run)

Pass `generate_gif=True` (or a path) to `Agent`:

```python
agent = Agent(
    task=task,
    llm=llm,
    browser_profile=browser_profile,
    generate_gif="output/agent_history.gif",  # saves GIF after run
)
```

Stitches screenshots from every step into an animated GIF. Works headless.

### 2. Real-time Screenshot Streaming (per-step callback)

```python
def on_step(state, output, step_num):
    # state.screenshot is a base64-encoded PNG of the current browser state
    # called after every agent action
    print(f"Step {step_num}: {output.action}")

agent = Agent(
    task=task,
    llm=llm,
    browser_profile=browser_profile,
    register_new_step_callback=on_step,
)
```

Fires after each action — you get the screenshot in real-time even in headless mode.

### 3. History Object After Run

```python
result = await agent.run()
result.screenshot_paths()   # list of paths to all step screenshots
result.action_names()       # what actions were taken
result.final_result()       # text result
```

## Current State of browser_agent.py

`browser_agent.py` uses none of these — it only returns `final_result()`.

**Potential additions:**
- `generate_gif` → get a replay GIF back with the result
- `register_new_step_callback` → stream step-by-step screenshots (useful for command center UI)
- Return GIF path in the JSON result

## Sources

- https://docs.browser-use.com/customize/agent-settings
- https://github.com/browser-use/browser-use/discussions/604
- https://github.com/browser-use/browser-use/issues/647
