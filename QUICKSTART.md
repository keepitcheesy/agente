# Quick Start Guide

## Fastest Way to Get Started

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Demo

See the system in action with a mock RSS feed:

```bash
python demo.py 60
```

This will run a 60-second demonstration showing:
- Breaking news transitions
- Anchor perspective cycling (A → B → C → A...)
- Visual stack rendering
- Event-driven story updates

### 3. Configure Your RSS Feed

Edit `config.yaml` and update the RSS URL:

```yaml
rss:
  url: "https://your-news-feed-url.com/rss"
```

### 4. Run the Real Broadcast

```bash
python main.py
```

The broadcast will:
- Poll your RSS feed every 60 seconds (configurable)
- Display new stories as they arrive
- Cycle through anchor perspectives continuously
- Run 24/7 until you stop it with Ctrl+C

## Configuration Quick Reference

### Adjust Update Speed

```yaml
rss:
  polling_interval: 30  # Check feed every 30 seconds
  debounce_timeout: 5   # Wait 5 seconds between story switches
```

### Adjust Anchor Rotation Speed

```yaml
anchors:
  rotation_interval: 20  # Each anchor speaks for 20 seconds
```

### Customize Visual Effects

```yaml
visuals:
  ticker:
    speed: 3  # Faster scrolling
  
  story_image:
    pan_speed: 1.0  # Faster camera movement
    zoom_factor: 1.2  # More zoom
```

## Common Use Cases

### High-Frequency News Feed (Twitter/Social Media)

```yaml
rss:
  polling_interval: 10  # Check every 10 seconds
  debounce_timeout: 3   # Quick transitions
```

### Traditional News Feed (Every Few Minutes)

```yaml
rss:
  polling_interval: 180  # Check every 3 minutes
  debounce_timeout: 10   # Avoid rapid changes
```

### Deep Analysis (Long-Form Coverage)

```yaml
anchors:
  rotation_interval: 60  # Each anchor speaks for 1 minute
```

## Troubleshooting

### No Stories Appearing

1. Check your RSS feed URL is correct
2. Verify the feed has entries: `curl <your-feed-url>`
3. Check the logs: `tail -f agente.log`

### Rapid Story Switching

Increase the debounce timeout:

```yaml
rss:
  debounce_timeout: 10  # Wait 10 seconds minimum
```

### Anchors Rotating Too Fast/Slow

Adjust rotation interval:

```yaml
anchors:
  rotation_interval: 30  # Adjust as needed
```

## Next Steps

- Read the full [README.md](README.md) for complete documentation
- Customize anchor personas in `config.yaml`
- Review the code to understand the architecture
- Run tests with `python test_agente.py`
