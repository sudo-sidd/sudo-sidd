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
# Aligned to 6-hour cron schedule to ensure at least 1 point of decay per run
HUNGER_RATE = 6  # +1 every 6 hours
MOOD_DECAY_RATE = 6  # -1 every 6 hours
ENERGY_DECAY_RATE = 6  # -1 every 6 hours
AGE_INCREMENT = 6  # +6 hours per cron run

COOLDOWN_FEED = 3600  # 1 hour in seconds
COOLDOWN_PLAY = 3600  # 1 hour in seconds
COOLDOWN_PET = 300  # 5 minutes in seconds

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

def render_stat_bar(value, total_blocks=15):
    percent = clamp(value)
    filled = int(round((percent / 100) * total_blocks))
    filled = min(total_blocks, filled)
    bar = '█' * filled + '░' * (total_blocks - filled)
    return f"`{bar}`&nbsp;{percent}%"

def make_issue_button(label, action):
    issue_title = urllib.parse.quote_plus(f"/{action}")
    issue_body = urllib.parse.quote_plus(f"/{action}")
    badge_label = urllib.parse.quote(label)
    # Orange button with darker orange/brown label background to simulate border/style
    color = 'FF8C00' # Dark Orange
    label_color = 'A0522D' # Sienna (Brownish)
    
    badge_url = (
        f"https://img.shields.io/badge/{badge_label}-{color}?"
        f"style=for-the-badge&labelColor={label_color}&logoColor=white"
    )
    issue_url = (
        f"https://github.com/{REPO_SLUG}/issues/new?title={issue_title}&body={issue_body}"
    )
    return (
        f'<a href="{issue_url}" target="_blank">'
        f'<img src="{badge_url}" alt="{label}" /></a>'
    )

def get_cooldown_status(last_time_str, cooldown_seconds):
    if not last_time_str:
        return "Ready"
    last_time = parse_time(last_time_str)
    now = get_utc_now()
    diff = (now - last_time).total_seconds()
    if diff >= cooldown_seconds:
        return "Ready"
    else:
        remaining = int((cooldown_seconds - diff) / 60)
        return f"Wait {remaining}m"

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
    timestamps = state['timestamps']
    
    # Leaderboard
    # Handle new user structure (dict) or old structure (int)
    users_list = []
    for user, data in state['interactions']['byUser'].items():
        count = data['count'] if isinstance(data, dict) else data
        users_list.append((user, count))
        
    sorted_users = sorted(users_list, key=lambda x: x[1], reverse=True)
    leaderboard_rows = []
    for i, (user, count) in enumerate(sorted_users[:5], 1):
        leaderboard_rows.append(f"{i}. @{user} – {count}")
    
    leaderboard_text = "\n".join(leaderboard_rows) if leaderboard_rows else "No interactions yet."

    # Status Text
    status_text = state['state']['status'].title()
    
    # Sprite
    sprite_file = state['state']['currentAnimation']
    
    # Cooldowns
    status_feed = get_cooldown_status(timestamps['lastFedAt'], COOLDOWN_FEED)
    status_play = get_cooldown_status(timestamps['lastPlayedAt'], COOLDOWN_PLAY)
    status_pet = get_cooldown_status(timestamps['lastPettedAt'], COOLDOWN_PET)

    new_section = f"""{start_marker}
<div align="center" id="github-tamagotchi">

### {state['name']} (Age: {state['ageHours'] // 24} days, {state['ageHours'] % 24} hours)

<div style="background-color: #FFF8DC; border: 4px solid #8B4513; border-radius: 10px; padding: 20px; display: inline-block;">
<table role="presentation" style="border: none; background: transparent;">
  <tr>
    <td align="center" width="300" style="border: none;">
      <img src="{SPRITES_DIR}/{sprite_file}" alt="{state['name']}" width="200" style="image-rendering: pixelated;" />
      <br />
      <br />
      <table border="0" style="border: none; background: transparent;">
        <tr>
          <td style="border: none;">{make_issue_button('Feed', 'feed')}</td>
          <td style="border: none;">{make_issue_button('Play', 'play')}</td>
          <td style="border: none;">{make_issue_button('Pet', 'pet')}</td>
        </tr>
        <tr>
          <td align="center" style="border: none;"><sub>{status_feed}</sub></td>
          <td align="center" style="border: none;"><sub>{status_play}</sub></td>
          <td align="center" style="border: none;"><sub>{status_pet}</sub></td>
        </tr>
      </table>
      <br />
    </td>
    <td width="300" valign="middle" style="border: none;">
      <h3>Pet Status : {status_text}</h3>
      <strong>Vital Stats</strong>
      <br/>
      Hunger: {render_stat_bar(stats['hunger'])}<br/>
      Mood:   {render_stat_bar(stats['mood'])}<br/>
      Energy: {render_stat_bar(stats['energy'])}
    </td>
  </tr>
</table>
</div>

<div align="center" style="max-width: 600px; margin: 20px auto; font-family: monospace;">
  <p>
    This is <strong>Wisphe</strong>. I found him inside the broken firmware of an old Tamagotchi shell that wouldn’t even boot. The code was scrambled, but he was still in there, floating around like he was waiting for someone to notice him.
  </p>
  <p>
    I patched the bits that kept him crashing and moved him into this README so he’d have a stable place to stay. He’s friendly, a little moody, and pays attention to anyone who interacts with him.
  </p>
  <p>
    If you’re here, give him a moment. He loves the company.
  </p>
</div>

<details>
<summary><strong>Top Caretakers</strong></summary>

```
{leaderboard_text}
```
</details>

<details>
<summary><strong>How to interact</strong></summary>

Use the buttons above or comment commands in an issue:

| Command | Effect | Cooldown |
| :--- | :--- | :--- |
| `/feed` | -30 Hunger, +5 Mood, +50 Energy | **1 hour** |
| `/play` | +15 Mood, -10 Energy | **1 hour** |
| `/pet` | +5 Mood | **5 minutes** |

**Reward Loop**:
- Keeping **Mood** high (>70) makes {state['name']} excited.
- Letting **Hunger** get too high (>80) or **Mood** too low (<40) makes {state['name']} sad or fainted.
- **Energy** drops over time; resting happens automatically or via play trade-offs.

The system updates every 6 hours automatically.
</details>

<details>
<summary><strong>How this game works</strong></summary>

This is a fully automated creature living in the repository.
- **Time**: It ages and stats decay in real-time (updated every 6 hours).
- **Memory**: It remembers who interacted with it and when.
- **Persistence**: All state is saved in `state/creature.json`.
- **Interaction**: You can influence its mood and health by clicking the buttons above, which open issues that trigger a GitHub Action to update the pet.
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
    # Age is now calculated dynamically in main(), so we don't need to increment it here.
    
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
        
        stats['hunger'] = clamp(stats['hunger'] - 30)
        stats['mood'] = clamp(stats['mood'] + 5)
        stats['energy'] = clamp(stats['energy'] + 50)
        timestamps['lastFedAt'] = now.isoformat()
        print(f"@{user} fed Wisphe!")
        
    elif action == 'play':
        last_played = parse_time(timestamps['lastPlayedAt'])
        if (now - last_played).total_seconds() < COOLDOWN_PLAY:
            print(f"Cooldown active. You can play again in {int((COOLDOWN_PLAY - (now - last_played).total_seconds())/60)} minutes.")
            return state
            
        stats['mood'] = clamp(stats['mood'] + 15)
        stats['energy'] = clamp(stats['energy'] - 10)
        timestamps['lastPlayedAt'] = now.isoformat()
        print(f"@{user} played with Wisphe!")
        
    elif action == 'pet':
        last_petted = parse_time(timestamps['lastPettedAt'])
        if (now - last_petted).total_seconds() < COOLDOWN_PET:
            print(f"Cooldown active. You can pet again in {int((COOLDOWN_PET - (now - last_petted).total_seconds())/60)} minutes.")
            return state
            
        stats['mood'] = clamp(stats['mood'] + 5)
        timestamps['lastPettedAt'] = now.isoformat()
        print(f"@{user} petted Wisphe!")
    
    else:
        print(f"Unknown command: {action}")
        return state

    # Update interactions
    state['interactions']['total'] += 1
    
    if user not in state['interactions']['byUser']:
        state['interactions']['byUser'][user] = {
            'count': 0,
            'lastInteractionAt': None,
            'lastAction': None
        }
    
    # Migration for old integer format if necessary
    if isinstance(state['interactions']['byUser'][user], int):
         state['interactions']['byUser'][user] = {
            'count': state['interactions']['byUser'][user],
            'lastInteractionAt': None,
            'lastAction': None
        }

    state['interactions']['byUser'][user]['count'] += 1
    state['interactions']['byUser'][user]['lastInteractionAt'] = now.isoformat()
    state['interactions']['byUser'][user]['lastAction'] = action
        
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
        # Age is now calculated dynamically based on createdAt
        state['timestamps']['lastAutoUpdate'] = get_utc_now().isoformat()
        print("Ran automatic update cycle.")
    else:
        # User interaction mode
        if not args.user:
            print("Error: --user is required for actions.")
            return
        state = handle_action(state, args.action, args.user)

    # Calculate Age Dynamically
    if 'createdAt' in state:
        created_at = parse_time(state['createdAt'])
        now = get_utc_now()
        age_hours = int((now - created_at).total_seconds() / 3600)
        state['ageHours'] = age_hours

    state = determine_state(state)
    save_state(state)
    update_readme(state)

if __name__ == '__main__':
    main()
