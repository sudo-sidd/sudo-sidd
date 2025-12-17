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

# Users to hide from the displayed leaderboard (still tracked in state)
LEADERBOARD_EXCLUDE_USERS = {"sudo-sidd"}

# Configuration
# Rates per hour (approximate)
HUNGER_INC_PER_HOUR = 2.5
MOOD_DEC_PER_HOUR = 1.8
ENERGY_DEC_PER_HOUR = 1.6
ENERGY_REC_PER_HOUR = 4.5

# Extra mood drain when very hungry
HUNGER_MOOD_PENALTY_PER_HOUR = 1.2

# Energy behavior thresholds
ENERGY_REC_MOOD_THRESHOLD = 75
ENERGY_REC_HUNGER_MAX = 75
ENERGY_STABLE_MOOD_THRESHOLD = 45
ENERGY_DECAY_HUNGER_THRESHOLD = 80

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

def _ensure_decay_carry(state):
    # Tracks fractional decay so small time steps still accumulate smoothly.
    carry = state.get('decayCarry')
    if not isinstance(carry, dict):
        carry = {}
    carry.setdefault('hunger', 0.0)
    carry.setdefault('mood', 0.0)
    carry.setdefault('energy', 0.0)
    state['decayCarry'] = carry
    return state

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

def get_action_hint(state, action):
    timestamps = state['timestamps']
    stats = state['stats']
    now = get_utc_now()

    action = action.lower().strip()

    if action == 'feed':
        last_fed = parse_time(timestamps['lastFedAt']) if timestamps.get('lastFedAt') else None
        if last_fed and COOLDOWN_FEED and (now - last_fed).total_seconds() < COOLDOWN_FEED:
            return "He just ate — maybe later"
        return "Feed him"

    if action == 'play':
        if stats.get('energy', 0) < 15:
            return "Too tired"
        if stats.get('hunger', 0) >= 80:
            return "Too hungry"
        return "Play with him"

    if action == 'pet':
        last_petted = parse_time(timestamps['lastPettedAt']) if timestamps.get('lastPettedAt') else None
        if last_petted and (now - last_petted).total_seconds() < 120:
            return "He feels loved"
        return "Pet him"

    return ""

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
        if user in LEADERBOARD_EXCLUDE_USERS:
            continue
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
    
    # Button hints (human-friendly)
    status_feed = get_action_hint(state, 'feed')
    status_play = get_action_hint(state, 'play')
    status_pet = get_action_hint(state, 'pet')

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
| `/feed` | Fills his tummy a lot, boosts Mood, and restores Energy. | **20 mins** |
| `/play` | Boosts Mood a lot, costs Energy, and makes him hungrier. Requires Energy. | **None** |
| `/pet` | Cheers him up! A quick way to boost Mood. | **None** |

**States & Rules**:
- **Happy States**: Keep Mood high to make {state['name']} Playful or Excited!
- **Warning Signs**: 
  - Low Fullness makes Woop Hungry.
  - Low Energy makes Woop Sleepy.
  - Low Mood makes Woop Cry.
- **Critical Conditions**:
  - **Game Over**: If he gets too hungry and tired, {state['name']} will Faint.

The system updates every 6 hours automatically. After you take an action (e.g. `/feed`, `/play`, `/pet`), wait for the GitHub Action to finish and refresh this page to see the changes.
</details>

<details>
<summary><strong>How this game works</strong></summary>

This is a fully automated creature living in the repository.
- **Time**: It ages and stats decay in real-time (updated every 6 hours).
- **Memory**: It remembers who interacted with it and when.
- **Persistence**: All state is saved in `state/creature.json`.
- **Interaction**: You can influence its mood and health by clicking the buttons above, which open issues that trigger a GitHub Action to update the pet. After you take an action, wait for the GitHub Action to finish and refresh this page to see the updated pet.
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
    if hunger >= 100 and energy <= 15:
        state['state']['currentAnimation'] = "wooper_fainted.gif"
        state['state']['status'] = "Fainted"
        return state

    # Crying (rare)
    if mood < 18:
        state['state']['currentAnimation'] = "wooper_crying.gif"
        state['state']['status'] = "Crying"
        return state

    # Sad (common)
    if hunger >= 85 or energy < 18 or mood < 38:
        state['state']['currentAnimation'] = "wooper_sad.gif"
        state['state']['status'] = "Sad"
        return state

    # Positive states
    if mood >= 82 and energy >= 55 and hunger <= 55:
        state['state']['currentAnimation'] = "wooper_idle.gif"
        state['state']['status'] = "Excited"
        return state

    if mood >= 62 and energy >= 32:
        state['state']['currentAnimation'] = "wooper_idle.gif"
        state['state']['status'] = "Happy"
        return state

    # Neutral
    state['state']['currentAnimation'] = "wooper_idle.gif"
    state['state']['status'] = "Idle"
    return state

def apply_decay(state, now=None):
    state = _ensure_decay_carry(state)
    now = now or get_utc_now()
    last_update = parse_time(state['timestamps']['lastAutoUpdate'])

    # Calculate hours passed
    diff = now - last_update
    hours_passed = max(0.0, diff.total_seconds() / 3600.0)
    if hours_passed <= 0.0:
        return state

    carry = state['decayCarry']

    # Hunger increases over time
    hunger_delta = (hours_passed * HUNGER_INC_PER_HOUR) + float(carry.get('hunger', 0.0))
    hunger_inc = int(math.floor(hunger_delta))
    carry['hunger'] = hunger_delta - hunger_inc
    if hunger_inc:
        state['stats']['hunger'] = clamp(state['stats']['hunger'] + hunger_inc)

    # Mood decreases over time, with a penalty when very hungry
    mood_rate = MOOD_DEC_PER_HOUR
    if state['stats']['hunger'] >= 80:
        mood_rate += HUNGER_MOOD_PENALTY_PER_HOUR

    mood_delta = (hours_passed * mood_rate) + float(carry.get('mood', 0.0))
    mood_dec = int(math.floor(mood_delta))
    carry['mood'] = mood_delta - mood_dec
    if mood_dec:
        state['stats']['mood'] = clamp(state['stats']['mood'] - mood_dec)

    # Energy rules:
    # - Recovers only when mood is high AND hunger isn't too high
    # - Stays constant under normal/idle conditions
    # - Decays only when mood is low OR hunger is high
    mood = state['stats']['mood']
    hunger = state['stats']['hunger']

    energy_rate = 0.0
    if mood >= ENERGY_REC_MOOD_THRESHOLD and hunger <= ENERGY_REC_HUNGER_MAX:
        energy_rate = ENERGY_REC_PER_HOUR
    elif mood < ENERGY_STABLE_MOOD_THRESHOLD or hunger >= ENERGY_DECAY_HUNGER_THRESHOLD:
        energy_rate = -ENERGY_DEC_PER_HOUR

    if energy_rate == 0.0:
        # Don't accumulate carry while stable; keeps behavior predictable.
        carry['energy'] = 0.0
    else:
        # Soft caps:
        # - Below ~20, energy should be very hard to drain further.
        # - Above ~85, energy should be very hard to recover further.
        energy = state['stats']['energy']
        mult = 1.0
        if energy_rate < 0:
            # Taper drain between 30 -> 20, then keep very slow below 20.
            if energy <= 20:
                mult = 0.1
            elif energy <= 30:
                t = (30 - energy) / 10.0  # 0..1
                mult = 1.0 - (0.9 * t)  # 1.0 -> 0.1
        else:
            # Taper recovery between 75 -> 85, then keep very slow above 85.
            if energy >= 85:
                mult = 0.1
            elif energy >= 75:
                t = (energy - 75) / 10.0  # 0..1
                mult = 1.0 - (0.9 * t)  # 1.0 -> 0.1

        effective_rate = abs(energy_rate) * mult

        energy_delta = (hours_passed * effective_rate) + float(carry.get('energy', 0.0))
        energy_mag = int(math.floor(energy_delta))
        carry['energy'] = energy_delta - energy_mag
        if energy_mag:
            state['stats']['energy'] = clamp(
                state['stats']['energy'] + (energy_mag if energy_rate > 0 else -energy_mag)
            )

    return state

def simulate_distribution(
    seed_state,
    days=7,
    step_minutes=30,
    start_hunger=10,
    start_mood=80,
    start_energy=60,
):
    # Simulate scheduled updates only (no actions) and return status distribution.
    # Defaults are a "healthy" starting point: fullness ~90% => hunger=10.
    sim_state = json.loads(json.dumps(seed_state))
    sim_state = _ensure_decay_carry(sim_state)
    created_at = parse_time(sim_state['createdAt']) if sim_state.get('createdAt') else get_utc_now()

    # Reset stats to a believable baseline (so distributions are meaningful)
    sim_state['stats']['hunger'] = clamp(start_hunger)
    sim_state['stats']['mood'] = clamp(start_mood)
    sim_state['stats']['energy'] = clamp(start_energy)
    sim_state['decayCarry'] = {'hunger': 0.0, 'mood': 0.0, 'energy': 0.0}

    # Clear action timestamps so we don't begin inside an action animation window
    sim_state.setdefault('timestamps', {})
    for k in ('lastFedAt', 'lastPlayedAt', 'lastPettedAt'):
        if k in sim_state['timestamps']:
            sim_state['timestamps'].pop(k, None)

    # Start from "now" to avoid depending on whatever the repo state currently contains.
    now = get_utc_now()
    sim_state['timestamps']['lastAutoUpdate'] = now.isoformat()
    end = now + datetime.timedelta(days=days)
    step = datetime.timedelta(minutes=step_minutes)

    counts = {}
    total = 0
    while now < end:
        now = now + step
        sim_state = apply_decay(sim_state, now=now)
        sim_state['timestamps']['lastAutoUpdate'] = now.isoformat()

        # Keep age consistent for realism.
        sim_state['ageHours'] = int((now - created_at).total_seconds() / 3600)

        sim_state = determine_state(sim_state)
        status = sim_state['state']['status']
        counts[status] = counts.get(status, 0) + 1
        total += 1

    return counts, total

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

        # Feed: strong on fullness, solid on mood/energy
        stats['hunger'] = clamp(stats['hunger'] - 35)
        stats['mood'] = clamp(stats['mood'] + 10)
        stats['energy'] = clamp(stats['energy'] + 25)
        timestamps['lastFedAt'] = now.isoformat()
        print(f"@{user} fed Woop!")

        # Can revive fainted state if conditions improved
        if state['state'].get('status', '').lower() == 'fainted' and stats['hunger'] < 100 and stats['energy'] >= 20:
            state['state']['status'] = 'Happy'
            state['state']['currentAnimation'] = 'wooper_idle.gif'
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

        # Play effectiveness scales with energy, but always has a meaningful cost
        energy_pct = stats['energy'] / 100.0
        mood_gain = int(24 * max(0.4, energy_pct))  # 9..24
        energy_cost = int(18 + (8 * (1 - energy_pct)))  # 18..26
        hunger_cost = 6

        stats['mood'] = clamp(stats['mood'] + mood_gain)
        stats['energy'] = clamp(stats['energy'] - energy_cost)
        stats['hunger'] = clamp(stats['hunger'] + hunger_cost)
        timestamps['lastPlayedAt'] = now.isoformat()
        print(f"@{user} played with Woop! Mood +{mood_gain}, Energy -{energy_cost}")

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
    parser.add_argument('--simulate-days', type=int, default=0, help='Simulate scheduled updates for N days and print state distribution')
    parser.add_argument('--sim-hunger', type=int, default=10, help='Simulation start hunger (default: 10 = fullness 90)')
    parser.add_argument('--sim-mood', type=int, default=80, help='Simulation start mood (default: 80)')
    parser.add_argument('--sim-energy', type=int, default=60, help='Simulation start energy (default: 60)')
    args = parser.parse_args()

    state = load_state()

    if args.simulate_days and args.simulate_days > 0:
        counts, total = simulate_distribution(
            state,
            days=args.simulate_days,
            step_minutes=30,
            start_hunger=args.sim_hunger,
            start_mood=args.sim_mood,
            start_energy=args.sim_energy,
        )
        fullness = clamp(100 - args.sim_hunger)
        print(f"Simulated {args.simulate_days} days ({total} ticks @30m) from Fullness {fullness}%, Mood {clamp(args.sim_mood)}%, Energy {clamp(args.sim_energy)}%")
        for k, v in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
            pct = (v / total) * 100 if total else 0
            print(f"- {k}: {v} ({pct:.1f}%)")
        return
    
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
