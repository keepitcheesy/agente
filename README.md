# Agente - 24/7 Morning Show Broadcast Pipeline

A Python-based broadcast pipeline that implements a 24/7 "morning show" style news broadcast with event-driven segment logic, anchor persona cycling, and CNN-style visual stack.

## Features

### Event-Driven Segment Logic
- **No Fixed Duration**: Story segments only advance when a new RSS item arrives
- **RSS Polling**: Continuously monitors an RSS feed for new content
- **Debouncing**: Prevents rapid story switching with configurable timeout
- **Breaking News Transitions**: Smooth transitions when new stories arrive

### Anchor Persona Cycling
- **Three Perspectives**: Each story is covered by three anchors with unique viewpoints:
  - **Anchor A**: Headlines and facts (What happened and when)
  - **Anchor B**: Implications (Why it matters and what comes next)
  - **Anchor C**: Context (Background and historical perspective)
- **Continuous Rotation**: Anchors cycle through their perspectives until a new story arrives
- **Configurable Timing**: Adjust how long each anchor speaks

### CNN-Style Visual Stack
- **Lower Thirds**: Dynamic graphics that update per anchor perspective
- **Scrolling Ticker**: Continuous news ticker at bottom of screen
- **LIVE Tag**: Always visible with timestamp and episode ID
- **Story Image**: Slow pan/zoom effects on story images
- **All Elements**: Rendered simultaneously in a complete visual stack

## Installation

1. Clone the repository:
```bash
git clone https://github.com/keepitcheesy/agente.git
cd agente
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Edit `config.yaml` to customize the broadcast:

### RSS Feed Settings
```yaml
rss:
  url: "https://your-rss-feed-url.com/feed.xml"
  polling_interval: 60  # Seconds between feed checks
  debounce_timeout: 5   # Minimum seconds between story transitions
```

**Tuning Guide**:
- `polling_interval`: Lower values (e.g., 30s) = more responsive to updates, higher server load
- `debounce_timeout`: Higher values (e.g., 10s) = prevents rapid switching but delays urgent updates

### Anchor Configuration
```yaml
anchors:
  cycle_order:
    - name: "Anchor A"
      focus: "headline/facts"
      perspective: "What happened and when"
      color: "#FF0000"
  rotation_interval: 30  # Seconds each anchor speaks
```

**Tuning Guide**:
- `rotation_interval`: Adjust based on story complexity (15-60 seconds typical)

### Visual Effects
```yaml
visuals:
  lower_third:
    enabled: true
    update_per_anchor: true  # Update graphics when anchor changes
  
  ticker:
    enabled: true
    speed: 2  # Pixels per frame
  
  live_tag:
    enabled: true
    show_timestamp: true
    show_episode_id: true
  
  story_image:
    pan_zoom_enabled: true
    pan_speed: 0.5
    zoom_factor: 1.1
```

## Usage

### Start the Broadcast

```bash
python main.py
```

The broadcast will:
1. Load configuration from `config.yaml`
2. Start polling the RSS feed
3. Begin 24/7 continuous broadcast
4. Display status updates every 10 seconds
5. Log all activity to `agente.log`

### Stop the Broadcast

Press `Ctrl+C` to gracefully shut down the broadcast.

## Architecture

### Core Components

1. **RSS Monitor** (`rss_monitor.py`)
   - Polls RSS feed at configured intervals
   - Detects new stories
   - Implements debouncing logic
   - Handles story parsing and metadata extraction

2. **Anchor Cycler** (`anchor_cycler.py`)
   - Manages three anchor personas
   - Cycles through perspectives (A → B → C → A...)
   - Generates perspective-specific content
   - Resets when new story arrives

3. **Visual Renderer** (`visual_renderer.py`)
   - Renders lower third graphics
   - Animates scrolling ticker
   - Displays LIVE tag with timestamp
   - Applies pan/zoom to story images
   - Composes complete visual stack

4. **Broadcast Pipeline** (`broadcast_pipeline.py`)
   - Orchestrates all components
   - Manages broadcast state
   - Handles breaking news transitions
   - Tracks statistics and performance
   - Generates unique episode IDs

### Data Flow

```
RSS Feed → RSS Monitor → New Story Detected
                ↓
         Debounce Check
                ↓
    Breaking News Transition
                ↓
    Anchor Cycler Reset (Start with A)
                ↓
    Visual Stack Updated
                ↓
  Continuous Anchor Rotation (A→B→C→A...)
                ↓
    [Wait for Next RSS Update]
```

## Testing

Run the test suite:

```bash
python test_agente.py
```

Tests cover:
- RSS monitoring and debouncing
- Anchor persona cycling
- Visual rendering components
- Complete pipeline integration

## Event-Driven Behavior

The pipeline is **completely event-driven**:

1. **Story Duration**: Stories have **no fixed duration** - they continue until a new RSS item arrives
2. **Anchor Cycling**: Anchors rotate continuously (A→B→C→A...) while covering the same story
3. **Update Detection**: RSS feed is polled at regular intervals to detect new content
4. **Debouncing**: New stories must wait a minimum time before triggering a transition
5. **Breaking Updates**: When a new story arrives, the system immediately transitions with a "breaking news" effect

## Output

The pipeline generates:
- **Frame Data**: Complete visual frame information (JSON format)
- **Console Status**: Real-time status updates every 10 seconds
- **Log File**: Detailed activity log (`agente.log`)
- **Statistics**: Story count, rotation count, uptime, FPS

Example status output:
```
[STATUS] Episode: 20260218-145030
  State: running
  Story: Breaking: Major Event Happens
  Anchor: Anchor B
  Frames: 1847
  Uptime: 61.6s
  Rotations: 2
```

## Advanced Configuration

### Multiple RSS Feeds

To monitor multiple feeds, you would extend `rss_monitor.py` to support multiple feed URLs and merge their items.

### Custom Anchor Perspectives

Add or modify anchor personas in `config.yaml` to match your editorial style:

```yaml
anchors:
  cycle_order:
    - name: "Economics Desk"
      focus: "financial impact"
      perspective: "Market implications"
      color: "#FFD700"
```

### Visual Customization

Adjust visual parameters in `config.yaml`:
- Font sizes, colors, positions
- Animation speeds and durations
- Enable/disable individual elements

## Logging

Logs are written to:
- **Console**: INFO level and above
- **File** (`agente.log`): DEBUG level and above

Configure logging in `config.yaml`:
```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: "agente.log"
```

## Requirements

- Python 3.8+
- feedparser 6.0.11
- PyYAML 6.0.1
- requests 2.31.0
- Pillow 10.3.0

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.