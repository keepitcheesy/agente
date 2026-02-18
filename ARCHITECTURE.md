# Architecture Documentation

## System Overview

The Agente 24/7 Morning Show Broadcast is an event-driven pipeline that continuously monitors an RSS feed and presents news stories with rotating anchor perspectives and CNN-style visual effects.

## Core Principles

### 1. Event-Driven Segments
Stories have **no fixed duration**. The system only advances to a new story when:
- A new RSS item is detected
- The debounce timeout has elapsed since the last story change

### 2. Continuous Anchor Rotation
While covering a single story, the system continuously cycles through three anchor personas:
- **Anchor A**: Headlines and facts
- **Anchor B**: Implications and analysis
- **Anchor C**: Context and background

The cycle repeats indefinitely (A → B → C → A → B → C...) until a new story arrives.

### 3. CNN-Style Visual Stack
All visual elements render simultaneously:
- Lower third (updates per anchor)
- Scrolling ticker (continuous)
- LIVE tag with timestamp and episode ID (always visible)
- Story image with slow pan/zoom effects

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Broadcast Pipeline                       │
│                    (broadcast_pipeline.py)                  │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ RSS Monitor  │  │Anchor Cycler │  │Visual Stack  │     │
│  │              │  │              │  │              │     │
│  │ - Poll feed  │  │ - Rotate A→B │  │ - Lower 3rd  │     │
│  │ - Detect new │  │   →C→A...    │  │ - Ticker     │     │
│  │ - Debounce   │  │ - Generate   │  │ - LIVE tag   │     │
│  │              │  │   perspective│  │ - Pan/Zoom   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                 │                  │             │
│         └─────────────────┴──────────────────┘             │
│                           │                                │
└───────────────────────────┼────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  Frame Output │
                    │  (JSON data)  │
                    └───────────────┘
```

## Data Flow Diagram

```
Start
  │
  ▼
┌─────────────────┐
│ Poll RSS Feed   │ ◄──── Every polling_interval seconds
└────────┬────────┘
         │
         ▼
    New Story?
         │
    ┌────┴────┐
    │         │
   No        Yes
    │         │
    │         ▼
    │    ┌─────────────────┐
    │    │ Check Debounce  │
    │    └────────┬────────┘
    │             │
    │        ┌────┴─────┐
    │        │          │
    │    Ready?    Pending
    │        │          │
    │       Yes         │
    │        │          │
    │        ▼          │
    │    ┌─────────────────────┐
    │    │ Breaking News       │
    │    │ Transition          │
    │    └────────┬────────────┘
    │             │
    │             ▼
    │    ┌─────────────────────┐
    │    │ Reset Anchor Cycler │
    │    │ (Start with A)      │
    │    └────────┬────────────┘
    │             │
    │             ▼
    │    ┌─────────────────────┐
    │    │ Update Visuals      │
    │    │ (Image, Ticker)     │
    │    └────────┬────────────┘
    │             │
    └─────────────┼─────────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Update Anchors │ ◄──── Every rotation_interval
         └────────┬───────┘
                  │
             ┌────┴─────┐
             │          │
        Time for    Continue
         Rotate?      Same
             │          │
            Yes         │
             │          │
             ▼          │
    ┌─────────────┐    │
    │ Rotate to   │    │
    │ Next Anchor │    │
    │ (A→B→C→A)   │    │
    └────────┬────┘    │
             │         │
             └─────────┼─────────┐
                       │         │
                       ▼         │
              ┌─────────────────┐│
              │ Update Lower    ││
              │ Third Graphics  ││
              └─────────┬───────┘│
                        │        │
                        ▼        │
               ┌─────────────────┐│
               │ Render Frame    ││
               │ - Lower Third   ││
               │ - Ticker        ││
               │ - LIVE Tag      ││
               │ - Story Image   ││
               │   (Pan/Zoom)    ││
               └────────┬────────┘│
                        │         │
                        ▼         │
               ┌─────────────────┐│
               │ Output Frame    ││
               │ (JSON + Log)    ││
               └────────┬────────┘│
                        │         │
                        └─────────┘
                        │
                        ▼
                  Loop Forever
```

## State Machine

The broadcast pipeline operates in the following states:

```
IDLE → RUNNING ⇄ BREAKING_NEWS
  ↑      ↓
  └──────┘
  (stop)
```

### State Descriptions

1. **IDLE**: Initial state, not broadcasting
2. **RUNNING**: Normal operation, anchors rotating on current story
3. **BREAKING_NEWS**: Transitioning to new story (brief state)

## Timing Diagrams

### Scenario: Normal Operation with Story Update

```
Time:      0s    10s   20s   30s   40s   50s   60s
Story:    [────── Story 1 ──────][──── Story 2 ────]
                                 ↑
                                RSS Update Detected
                                
Anchor:   [A ][B ][C ][A ][B ][C ][A ][B ][C ][A ]
          └─────────────────────┘ └─────────────┘
           Cycle 1 & 2 (Story 1)  Cycle 1 (Story 2)

Actions:
  10s - Rotate to B
  20s - Rotate to C
  30s - Rotate to A (cycle 2)
  35s - RSS poll finds new story
  40s - Debounce complete → Breaking transition
  40s - Story changes, anchors reset to A
  50s - Rotate to B
```

### Scenario: Debouncing Prevents Rapid Changes

```
Time:      0s    5s    10s   15s   20s
Story:    [─── Story 1 ───][────── Story 2 ──────]
                 ↑     ↑               ↑
                RSS   RSS             Debounce
                New   New             Complete
               (wait) (wait)

Debounce: [─────────────────────────][────
          └─ 5 second minimum wait ─┘

Result:   Story 1 continues for full debounce period
          before transitioning to Story 2
```

## Key Algorithms

### RSS Polling with Debounce

```python
def check_for_update():
    new_story = poll_feed()
    
    if new_story is None:
        return None
    
    time_since_last = now - last_update_time
    
    if time_since_last < debounce_timeout:
        # Store as pending
        pending_story = new_story
        return None
    
    # Update ready
    transition_to_story(new_story)
```

### Anchor Rotation Logic

```python
def update():
    if time_on_anchor >= rotation_interval:
        current_index = (current_index + 1) % 3
        # Cycles: 0→1→2→0→1→2...
        # Maps to: A→B→C→A→B→C...
```

### Visual Pan/Zoom Animation

```python
def update(delta_time):
    progress = (elapsed_time % duration) / duration
    
    # Smooth pan using sine wave
    pan_x = sin(progress * 2π) * pan_speed
    pan_y = cos(progress * 2π) * pan_speed
    
    # Smooth zoom in/out
    zoom = 1.0 + sin(progress * π) * (zoom_factor - 1.0)
```

## Configuration Tuning Guide

### For Breaking News (Rapid Updates)

```yaml
rss:
  polling_interval: 10    # Check often
  debounce_timeout: 2     # Quick transitions

anchors:
  rotation_interval: 15   # Faster rotation
```

**Effect**: Responsive to updates, fast-paced coverage

### For In-Depth Analysis (Slow Coverage)

```yaml
rss:
  polling_interval: 300   # Check every 5 minutes
  debounce_timeout: 30    # Prevent rapid changes

anchors:
  rotation_interval: 90   # Long-form analysis
```

**Effect**: Deep coverage, multiple rotation cycles per story

### For 24/7 News Channel

```yaml
rss:
  polling_interval: 60    # Hourly rhythm
  debounce_timeout: 10    # Stable transitions

anchors:
  rotation_interval: 30   # Balanced coverage
```

**Effect**: Professional pacing, continuous coverage

## Performance Characteristics

- **Target Frame Rate**: 30 FPS
- **Memory Footprint**: Low (~50 MB typical)
- **CPU Usage**: Minimal (mostly idle waiting for updates)
- **Network**: Light (only RSS polling, small XML payloads)

## Extension Points

### Adding New Anchor Personas

Extend `anchors.cycle_order` in config:

```yaml
anchors:
  cycle_order:
    - name: "Expert Panel"
      focus: "technical analysis"
      perspective: "Deep technical dive"
      color: "#FFD700"
```

### Custom Visual Elements

Extend `VisualStack` class to add new components:

```python
class CustomGraphic:
    def __init__(self, config):
        # Initialize
        
    def render(self):
        # Return render data
```

### Multiple RSS Feeds

Extend `RSSMonitor` to handle multiple feeds:

```python
class MultiRSSMonitor:
    def __init__(self, feed_urls):
        self.monitors = [RSSMonitor(url) for url in feed_urls]
    
    def poll_all(self):
        # Merge and prioritize stories
```

## Error Handling

- **RSS Feed Unavailable**: Logs warning, continues with current story
- **No Stories Available**: Waits in idle state until first story arrives
- **Network Errors**: Retries on next polling interval
- **Configuration Errors**: Fails fast on startup with clear error messages
