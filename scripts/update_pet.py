import argparse
import datetime
import json
import os
import urllib.parse
import math

STATE_FILE = 'state/creature.json'
README_FILE = 'README.md'
SPRITES_DIR = 'sprites'
REPO_SLUG = os.environ.get('GITHUB_REPOSITORY', 'sudo-sidd/sudo-sidd')

# Configuration
HUNGER_RATE = 4  # +1 every 4 hours
MOOD_DECAY_RATE = 6  # -1 every 6 hours
ENERGY_DECAY_RATE = 8  # -1 every 8 hours
AGE_INCREMENT = 6  # +6 hours per cron run

COOLDOWN_FEED = 3600  # 1 hour in seconds
COOLDOWN_PLAY = 10800  # 3 hours in seconds
COOLDOWN_PET = 1800  # 30 minutes in seconds

def load_state():
    with open(STATE_FILE, 'r') as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def get_utc_now():
    return datetime.datetime.now(datetime.timezone.utc)

def parse_time(iso_str):
    return datetime.datetime.fromisoformat(iso_str)

def clamp(value, min_val=0, max_val=100):
    return max(min_val, min(max_val, value))

def render_stat_bar(value, total_blocks=20):
    percent = clamp(value)
    filled = int(round((percent / 100) * total_blocks))
    filled = min(total_blocks, filled)
    bar = '█' * filled + '░' * (total_blocks - filled)
    return f"`{bar}` {percent}%"

def make_issue_button(label, action, color):
    issue_title = urllib.parse.quote_plus(f"/{action}")
    issue_body = urllib.parse.quote_plus(f"/{action}")
    badge_label = urllib.parse.quote(label)
    badge_url = (
        f"https://img.shields.io/badge/-{badge_label}-{color}?"
        "style=for-the-badge"
    )
    issue_url = (
        f"https://github.com/{REPO_SLUG}/issues/new?title={issue_title}&body={issue_body}"
    )
    return (
        f'<a href="{issue_url}" target="_blank">'
        f'<img src="{badge_url}" alt="{label}" /></a>'
    )

def update_readme(state):
    with open(README_FILE, 'r') as f:
        content = f.read()

    start_marker = '<!-- PET-START -->'
    end_marker = '<!-- PET-END -->'
    
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    
    if start_idx == -1 or end_idx == -1:
        print("Error: Could not find PET markers in README.")
        return

    stats = state['stats']
    
    # Leaderboard
    sorted_users = sorted(state['interactions']['byUser'].items(), key=lambda x: x[1], reverse=True)
    leaderboard_rows = []
    for i, (user, count) in enumerate(sorted_users[:5], 1):
        leaderboard_rows.append(f"{i}. @{user} – {count}")
    
    leaderboard_text = "\n".join(leaderboard_rows) if leaderboard_rows else "No interactions yet."

    # Status Text
    status_text = state['state']['status'].title()
    
    # Sprite
    sprite_file = state['state']['currentAnimation']
    
    new_section = f"""{start_marker}
<div align="center" id="github-tamagotchi">

### {state['name']} (Age: {state['ageHours'] // 24} days, {state['ageHours'] % 24} hours)

<table role="presentation">
  <tr>
    <td align="center" width="300">
      <img src="{SPRITES_DIR}/{sprite_file}" alt="{state['name']}" width="200" style="image-rendering: pixelated;" />
      <br />
      <p><strong>Status</strong>: {status_text}</p>
    </td>
    <td width="300" valign="middle">
      <strong>Vital Stats</strong>
      <br/>
      Hunger: {render_stat_bar(stats['hunger'])}<br/>
      Mood:   {render_stat_bar(stats['mood'])}<br/>
      Energy: {render_stat_bar(stats['energy'])}
    </td>
  </tr>
</table>

<div align="center">
    {make_issue_button('Feed', 'feed', 'FFD166')}
    {make_issue_button('Play', 'play', '06D6A0')}
    {make_issue_button('Pet', 'pet', '118AB2')}
</div>

<details>
<summary><strong>Top Caretakers</strong></summary>

```
{leaderboard_text}
```
</details>

<details>
<summary><strong>How to interact</strong></summary>

Use these commands in an issue or comment:
- `/feed`: Decreases hunger, improves mood.
- `/play`: Improves mood, uses energy.
- `/pet`: Improves mood slightly.

The system updates every 6 hours automatically.
</details>

</div>
{end_marker}"""

    new_content = content[:start_idx] + new_section + content[end_idx + len(end_marker):]
    
    with open(README_FILE, 'w') as f:
        f.write(new_content)

def determine_state(state):
    stats = state['stats']
    hunger = stats['hunger']
    mood = stats['mood']
    energy = stats['energy']
    
    # Default
    animation = "tamogachi_happy.gif"
    status = "Feeling good"
    
    # Rules
    if hunger >= 100:
        animation = "tamogachi_fainted.png"
        status = "Fainted"
    elif hunger > 80:
        animation = "tamogachi_fainted.png" # User requested fainted sprite for hungry
        status = "Starving"
    elif energy < 20:
        animation = "sleepy.svg"
        status = "Sleepy"
    elif mood < 40:
        animation = "tamogachi_sad.gif"
        status = "Feeling down"
    elif mood > 70:
        animation = "tamogachi_excited.gif"
        status = "Excited!"
    elif hunger > 60:
        animation = "tamogachi_sad.gif" # Or maybe neutral?
        status = "Hungry"
    
    state['state']['currentAnimation'] = animation
    state['state']['status'] = status
    return state

def apply_decay(state):
    now = get_utc_now()
    last_update = parse_time(state['timestamps']['lastAutoUpdate'])
    
    # Calculate hours passed
    diff = now - last_update
    hours_passed = diff.total_seconds() / 3600.0
    
    if hours_passed < 1:
        return state # No significant decay yet
        
    # Apply decay
    # Hunger: +1 every 4 hours
    hunger_inc = int(hours_passed / HUNGER_RATE)
    state['stats']['hunger'] = clamp(state['stats']['hunger'] + hunger_inc)
    
    # Mood: -1 every 6 hours
    mood_dec = int(hours_passed / MOOD_DECAY_RATE)
    state['stats']['mood'] = clamp(state['stats']['mood'] - mood_dec)
    
    # Energy: -1 every 8 hours
    energy_dec = int(hours_passed / ENERGY_DECAY_RATE)
    state['stats']['energy'] = clamp(state['stats']['energy'] - energy_dec)
    
    # Age
    # User said "Age increases by 6 hours every cron run". 
    # But if we run this based on time delta, we should probably just add the hours passed?
    # Or strictly follow the "every cron run" rule. 
    # Let's assume the cron runs every 6 hours, so we add 6 hours if this is a cron run.
    # But this function might be called during user interaction too?
    # The prompt says "Step 5: Update age... Increase age by 6 hours each run" under "Automatic cycle".
    # So we should only update age if it's an auto update.
    
    return state

def handle_action(state, action, user):
    now = get_utc_now()
    timestamps = state['timestamps']
    stats = state['stats']
    
    action = action.lower().replace('/', '').strip()
    
    if action == 'feed':
        last_fed = parse_time(timestamps['lastFedAt'])
        if (now - last_fed).total_seconds() < COOLDOWN_FEED:
            print(f"Cooldown active. You can feed again in {int((COOLDOWN_FEED - (now - last_fed).total_seconds())/60)} minutes.")
            return state
        
        stats['hunger'] = clamp(stats['hunger'] - 20)
        stats['mood'] = clamp(stats['mood'] + 5)
        timestamps['lastFedAt'] = now.isoformat()
        print(f"@{user} fed SudoPet!")
        
    elif action == 'play':
        last_played = parse_time(timestamps['lastPlayedAt'])
        if (now - last_played).total_seconds() < COOLDOWN_PLAY:
            print(f"Cooldown active. You can play again in {int((COOLDOWN_PLAY - (now - last_played).total_seconds())/60)} minutes.")
            return state
            
        stats['mood'] = clamp(stats['mood'] + 15)
        stats['energy'] = clamp(stats['energy'] - 10)
        timestamps['lastPlayedAt'] = now.isoformat()
        print(f"@{user} played with SudoPet!")
        
    elif action == 'pet':
        last_petted = parse_time(timestamps['lastPettedAt'])
        if (now - last_petted).total_seconds() < COOLDOWN_PET:
            print(f"Cooldown active. You can pet again in {int((COOLDOWN_PET - (now - last_petted).total_seconds())/60)} minutes.")
            return state
            
        stats['mood'] = clamp(stats['mood'] + 5)
        timestamps['lastPettedAt'] = now.isoformat()
        print(f"@{user} petted SudoPet!")
    
    else:
        print(f"Unknown command: {action}")
        return state

    # Update interactions
    state['interactions']['total'] += 1
    if user in state['interactions']['byUser']:
        state['interactions']['byUser'][user] += 1
    else:
        state['interactions']['byUser'][user] = 1
        
    return state

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Action to perform (feed, play, pet)')
    parser.add_argument('--user', help='GitHub username of the player')
    args = parser.parse_args()

    state = load_state()
    
    # Always calculate decay first? 
    # The prompt says "On user comment... 4. Update stats and timestamps". 
    # It doesn't explicitly say apply decay on user interaction, but usually you want to bring stats up to date before applying action.
    # However, the prompt separates "Automatic cycle" (decay) from "Action Handling".
    # "On scheduled run... Only decay + state update".
    # "On user comment... Update stats".
    # If we don't decay on user interaction, the pet might not age or get hungry between cron runs if people interact frequently.
    # But let's stick to the prompt: "Automatic cycle... Step 3: Apply decay".
    # I will apply decay ONLY if it's a scheduled run (no action) OR if we want to be realistic, we should apply decay based on time passed since last update regardless.
    # Let's apply decay if it's the cron job (no action provided).
    
    if not args.action:
        # Cron job mode
        state = apply_decay(state)
        state['ageHours'] += AGE_INCREMENT
        state['timestamps']['lastAutoUpdate'] = get_utc_now().isoformat()
        print("Ran automatic update cycle.")
    else:
        # User interaction mode
        if not args.user:
            print("Error: --user is required for actions.")
            return
        state = handle_action(state, args.action, args.user)

    state = determine_state(state)
    save_state(state)
    update_readme(state)

if __name__ == '__main__':
    main()
