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
# Rates per hour (approximate)
HUNGER_INC_PER_HOUR = 4.0
MOOD_DEC_PER_HOUR = 3.0
ENERGY_DEC_PER_HOUR = 3.0
ENERGY_REC_PER_HOUR = 6.0

COOLDOWN_FEED = 1200  # 20 minutes in seconds
COOLDOWN_PLAY = 0  # No cooldown, limited by energy
# Petting has no cooldown (always allowed)
COOLDOWN_PET = 0

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
    if not cooldown_seconds or cooldown_seconds <= 0:
        return "Ready"
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

<div align="center" style="max-width: 600px; margin: 20px auto; font-family: monospace;">
  <p>
    He's <strong>Woop</strong> the Wooper. He's my pet and yes you can pet him.
  </p>
</div>

<!-- Sprite & Stats Section -->
<div align="center">
  <table border="0" style="border: none; background: transparent;">
    <tr>
      <td align="center" style="border: none; padding: 20px;">
        <img src="{SPRITES_DIR}/{sprite_file}" alt="{state['name']}" width="256" style="image-rendering: pixelated;" />
        <br>
        <strong>Status: {status_text}</strong>
      </td>
      <td align="left" style="border: none; padding: 20px; vertical-align: middle;">
        <strong>🍖 </strong>
        {render_stat_bar(100 - stats['hunger'])}<br><br>
        <strong>❤️ </strong>
        {render_stat_bar(stats['mood'])}<br><br>
        <strong>⚡ </strong>
        {render_stat_bar(stats['energy'])}
      </td>
    </tr>
  </table>
</div>

<!-- Controls Section -->
<div align="center">
  <table border="0" style="border: none; background: transparent;">
    <tr>
      <td style="border: none; padding: 5px;">{make_issue_button('Feed', 'feed')}</td>
      <td style="border: none; padding: 5px;">{make_issue_button('Play', 'play')}</td>
      <td style="border: none; padding: 5px;">{make_issue_button('Pet', 'pet')}</td>
    </tr>
    <tr>
      <td align="center" style="border: none;"><sub>{status_feed}</sub></td>
      <td align="center" style="border: none;"><sub>{status_play}</sub></td>
      <td align="center" style="border: none;"><sub>{status_pet}</sub></td>
    </tr>
  </table>
</div>

<details open>
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
| `/feed` | Fills his tummy, boosts Mood, and restores Energy. | **30 mins** |
| `/play` | Makes him Happy, but tires him out. Requires Energy. | **None** |
| `/pet` | Cheers him up! A quick way to boost Mood. | **None** |

**States & Rules**:
- **Happy States**: Keep Mood high to make {state['name']} Playful or Excited!
- **Warning Signs**: 
  - Low Fullness makes Woop Hungry.
  - Low Energy makes Woop Sleepy.
  - Low Mood makes Woop Cry.
- **Critical Conditions**:
  - **Game Over**: If he gets too hungry and tired, {state['name']} will Faint.

The system updates every 30 minutes automatically.
</details>

<details>
<summary><strong>How this game works</strong></summary>

This is a fully automated creature living in the repository.
- **Time**: It ages and stats decay in real-time (updated every 30 mins).
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
    timestamps = state['timestamps']
    now = get_utc_now()

    # Check for recent player actions (within 2 minutes)
    # Feed
    if timestamps.get('lastFedAt'):
        last_fed = parse_time(timestamps['lastFedAt'])
        if (now - last_fed).total_seconds() < 120:
            state['state']['currentAnimation'] = "wooper_eating.gif"
            state['state']['status'] = "Eating"
            return state

    # Play
    if timestamps.get('lastPlayedAt'):
        last_played = parse_time(timestamps['lastPlayedAt'])
        if (now - last_played).total_seconds() < 120:
            state['state']['currentAnimation'] = "wooper_play.gif"
            state['state']['status'] = "Playing"
            return state

    # Pet
    if timestamps.get('lastPettedAt'):
        last_petted = parse_time(timestamps['lastPettedAt'])
        if (now - last_petted).total_seconds() < 120:
            state['state']['currentAnimation'] = "wooper_petting.gif"
            state['state']['status'] = "Being Petted"
            return state

    # Fainted (hard condition)
    if hunger >= 100 and energy <= 20:
        state['state']['currentAnimation'] = "wooper_fainted.gif"
        state['state']['status'] = "Fainted"
        return state

    # Critical thresholds
    if hunger >= 90:
        state['state']['currentAnimation'] = "wooper_sad.gif"
        state['state']['status'] = "Hungry"
        return state

    if mood < 25:
        state['state']['currentAnimation'] = "wooper_crying.gif"
        state['state']['status'] = "Crying"
        return state

    if energy < 15:
        # tired / sad
        state['state']['currentAnimation'] = "wooper_sad.gif"
        state['state']['status'] = "Sleepy"
        return state

    # Positive states
    if mood >= 75 and energy > 40:
        state['state']['currentAnimation'] = "wooper_idle.gif"
        state['state']['status'] = "Excited"
        return state

    if mood >= 60:
        state['state']['currentAnimation'] = "wooper_idle.gif"
        state['state']['status'] = "Playful"
        return state

    # Neutral / default
    state['state']['currentAnimation'] = "wooper_idle.gif"
    state['state']['status'] = "Happy"
    return state

def apply_decay(state):
    now = get_utc_now()
    last_update = parse_time(state['timestamps']['lastAutoUpdate'])
    
    # Calculate hours passed
    diff = now - last_update
    hours_passed = diff.total_seconds() / 3600.0
    
    # Allow updates if at least 5 minutes passed (0.08 hours)
    if hours_passed < 0.08:
        return state

    # Apply time-based updates
    # Hunger increases over time
    hunger_inc = int(hours_passed * HUNGER_INC_PER_HOUR)
    # Ensure at least 1 unit if significant time passed (e.g. > 20 mins) to avoid stagnation
    if hunger_inc == 0 and hours_passed > 0.4:
        hunger_inc = 1
        
    state['stats']['hunger'] = clamp(state['stats']['hunger'] + hunger_inc)

    # Hunger affects mood: high hunger drains mood over time
    mood_dec = int(hours_passed * MOOD_DEC_PER_HOUR)
    if state['stats']['hunger'] >= 60:
        mood_dec += int(hours_passed * 2)  # extra drain
        
    if mood_dec == 0 and hours_passed > 0.4:
        mood_dec = 1

    state['stats']['mood'] = clamp(state['stats']['mood'] - mood_dec)

    # Mood affects energy recovery: good mood slowly restores energy
    energy_change = 0
    if state['stats']['mood'] >= 70:
        energy_change = int(hours_passed * ENERGY_REC_PER_HOUR)
        if energy_change == 0 and hours_passed > 0.4:
            energy_change = 1
    else:
        energy_change = -int(hours_passed * ENERGY_DEC_PER_HOUR)
        if energy_change == 0 and hours_passed > 0.4:
            energy_change = -1
            
    state['stats']['energy'] = clamp(state['stats']['energy'] + energy_change)
    
    return state

def handle_action(state, action, user):
    now = get_utc_now()
    timestamps = state['timestamps']
    stats = state['stats']
    
    action = action.lower().replace('/', '').strip()
    
    # --- Feed ---
    if action == 'feed':
        last_fed = parse_time(timestamps['lastFedAt']) if timestamps.get('lastFedAt') else None
        if last_fed and COOLDOWN_FEED and (now - last_fed).total_seconds() < COOLDOWN_FEED:
            print(f"Cooldown active. You can feed again in {int((COOLDOWN_FEED - (now - last_fed).total_seconds())/60)} minutes.")
            return state

        # Feed reduces hunger, small mood boost, small energy recovery
        stats['hunger'] = clamp(stats['hunger'] - 35)
        stats['mood'] = clamp(stats['mood'] + 8)
        stats['energy'] = clamp(stats['energy'] + 25)
        timestamps['lastFedAt'] = now.isoformat()
        print(f"@{user} fed Wisphe!")

        # Can revive fainted state if conditions improved
        if state['state'].get('status', '').lower() == 'fainted' and stats['hunger'] < 100 and stats['energy'] >= 20:
            # revive to sleepy/content
            state['state']['status'] = 'Content'
            state['state']['currentAnimation'] = 'tamogachi_happy.gif'
            print("Wisphe has been revived via feeding.")

    # --- Play ---
    elif action == 'play':
        last_played = parse_time(timestamps['lastPlayedAt']) if timestamps.get('lastPlayedAt') else None
        if last_played and COOLDOWN_PLAY and (now - last_played).total_seconds() < COOLDOWN_PLAY:
            print(f"Cooldown active. You can play again in {int((COOLDOWN_PLAY - (now - last_played).total_seconds())/60)} minutes.")
            return state

        # Play requirement: Energy
        if stats['energy'] < 15:
            print("Too tired to play.")
            return state

        # Play only allowed if hunger less than 80
        if stats['hunger'] >= 80:
            print("Too hungry to play.")
            # playing while hungry does nothing but maybe reduce energy
            stats['energy'] = clamp(stats['energy'] - 5)
            return state

        # Play effectiveness scales with energy
        energy_pct = stats['energy'] / 100.0
        mood_gain = int(20 * max(0.2, energy_pct))  # at least 20% effectiveness
        energy_cost = int(20 + (10 * (1 - energy_pct)))  # lower energy => slightly higher cost

        stats['mood'] = clamp(stats['mood'] + mood_gain)
        stats['energy'] = clamp(stats['energy'] - energy_cost)
        timestamps['lastPlayedAt'] = now.isoformat()
        print(f"@{user} played with Wisphe! Mood +{mood_gain}, Energy -{energy_cost}")

    # --- Pet ---
    elif action == 'pet':
        # petting always works (no cooldown)
        stats['mood'] = clamp(stats['mood'] + 6)
        timestamps['lastPettedAt'] = now.isoformat()
        print(f"@{user} petted Wisphe! (mood +6)")

        # If very sad, pet provides extra comfort
        if stats['mood'] < 30:
            stats['mood'] = clamp(stats['mood'] + 10)
            print("Pet calmed Wisphe.")
    
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
