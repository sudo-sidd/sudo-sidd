import argparse
import datetime
import json
import math
import os
import urllib.parse
import urllib.request

# Configuration & Paths
STATE_FILE = 'state/creature.json'
README_FILE = 'README.md'
SPRITES_DIR = 'sprites'
REPO_SLUG = os.environ.get('GITHUB_REPOSITORY', 'sudo-sidd/sudo-sidd')

# Users to hide from the displayed leaderboard (still tracked in state)
LEADERBOARD_EXCLUDE_USERS = {"testbot", "sudo-sidd"}

# Game Mechanics Settings
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

# Cooldowns (in seconds)
COOLDOWN_FEED = 7200  # 2 hours
COOLDOWN_PLAY = 2700  # 45 minutes
COOLDOWN_PET = 900    # 15 minutes

# The scheduled automatic update interval for the repository (minutes)
SCHEDULE_STEP_MINUTES = 15


# ==========================================
# Helpers & Utilities
# ==========================================

def load_state():
    """Loads the pet's current state from the JSON file."""
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def save_state(state):
    """Saves the pet's current state to the JSON file."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_utc_now():
    """Returns the current UTC datetime."""
    return datetime.datetime.now(datetime.timezone.utc)


def parse_time(iso_str):
    """Parses an ISO 8601 datetime string, handling the Z suffix for UTC."""
    if iso_str.endswith('Z'):
        iso_str = iso_str[:-1] + '+00:00'
    return datetime.datetime.fromisoformat(iso_str)


def clamp(value, min_val=0, max_val=100):
    """Clamps a numeric value between a minimum and maximum range."""
    return max(min_val, min(max_val, value))


def _ensure_decay_carry(state):
    """Ensures decay carry-over structures exist in the state for smooth accumulation."""
    carry = state.setdefault('decayCarry', {})
    carry.setdefault('hunger', 0.0)
    carry.setdefault('mood', 0.0)
    carry.setdefault('energy', 0.0)
    return state


# ==========================================
# GitHub Activity & Streak Checking
# ==========================================

def check_github_activity(username, last_update_str):
    """
    Fetches the public GitHub events for the specified username
    and returns events that occurred after last_update_str.
    """
    if not username:
        return []
    
    url = f"https://api.github.com/users/{username}/events/public"
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'GitHub-Pet-Action')
    
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
        
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                events = json.loads(response.read().decode('utf-8'))
                last_update = parse_time(last_update_str)
                new_events = []
                for event in events:
                    created_at_str = event.get('created_at')
                    if not created_at_str:
                        continue
                    event_time = parse_time(created_at_str)
                    if event_time > last_update:
                        new_events.append(event)
                # Reverse to process events chronologically
                new_events.reverse()
                return new_events
    except Exception as e:
        print(f"Warning: Could not fetch GitHub activity: {e}")
    return []


def update_github_activity(state):
    """
    Checks the user's GitHub activity, updates streaks, and rewards the pet
    with stats (Mood, Food/Fullness, and Energy) scaled by streak bonuses.
    """
    owner = REPO_SLUG.split('/')[0]
    last_update_str = state.get('timestamps', {}).get('lastAutoUpdate') or state.get('createdAt')
    if not last_update_str:
        return state
        
    # Load or initialize owner data
    user_data = state['interactions']['byUser'].setdefault(owner, {
        'count': 0,
        'lastInteractionAt': None,
        'lastAction': None,
        'streakDays': 0,
        'lastActiveDay': None
    })
    if isinstance(user_data, int):
        user_data = {
            'count': user_data,
            'lastInteractionAt': None,
            'lastAction': None,
            'streakDays': 0,
            'lastActiveDay': None
        }
        state['interactions']['byUser'][owner] = user_data
        
    user_data.setdefault('streakDays', 0)
    user_data.setdefault('lastActiveDay', None)
    
    current_date = get_utc_now().date()
    
    # Check if the streak is broken due to inactivity
    last_active_day_str = user_data.get('lastActiveDay')
    if last_active_day_str:
        try:
            last_active_date = datetime.date.fromisoformat(last_active_day_str)
            if (current_date - last_active_date).days > 1:
                user_data['streakDays'] = 0
                user_data['lastActiveDay'] = None
        except Exception:
            pass

    new_events = check_github_activity(owner, last_update_str)
    if not new_events:
        return state
        
    stats = state['stats']
    push_count = 0
    other_count = 0
    latest_event = None
    
    # Process events and recalculate streak progression chronologically
    streak = user_data.get('streakDays', 0)
    last_active_day_str = user_data.get('lastActiveDay')
    
    for event in new_events:
        latest_event = event
        event_time = parse_time(event.get('created_at'))
        event_date = event_time.date()
        
        # Calculate daily streak progression
        if not last_active_day_str:
            streak = 1
            last_active_day_str = event_date.isoformat()
        else:
            try:
                last_active_date = datetime.date.fromisoformat(last_active_day_str)
                diff = (event_date - last_active_date).days
                if diff == 1:
                    streak += 1
                    last_active_day_str = event_date.isoformat()
                elif diff > 1:
                    streak = 1
                    last_active_day_str = event_date.isoformat()
                elif diff == 0:
                    # Same day activity, maintain streak
                    last_active_day_str = event_date.isoformat()
            except Exception:
                streak = 1
                last_active_day_str = event_date.isoformat()
                
        # Stat multiplier: +10% per day of streak, capped at 2.0x (11-day streak)
        multiplier = min(2.0, 1.0 + 0.1 * (max(1, streak) - 1))
        
        event_type = event.get('type')
        if event_type == 'PushEvent':
            push_count += 1
            stats['hunger'] = clamp(stats['hunger'] - int(15 * multiplier))
            stats['mood'] = clamp(stats['mood'] + int(15 * multiplier))
            stats['energy'] = clamp(stats['energy'] + int(15 * multiplier))
        else:
            other_count += 1
            stats['hunger'] = clamp(stats['hunger'] - int(10 * multiplier))
            stats['mood'] = clamp(stats['mood'] + int(10 * multiplier))
            stats['energy'] = clamp(stats['energy'] + int(10 * multiplier))

    user_data['streakDays'] = streak
    user_data['lastActiveDay'] = last_active_day_str

    final_multiplier = min(2.0, 1.0 + 0.1 * (max(1, streak) - 1))
    pet_name = state.get('name', 'cron')
    print(f"Processed GitHub activity for @{owner}: {push_count} pushes, {other_count} other events. Streak: 🔥 {streak} days ({final_multiplier:.1f}x bonus). Updated {pet_name}'s stats.")
    
    if latest_event:
        latest_event_time = parse_time(latest_event.get('created_at'))
        action_name = "pushed_code" if push_count > 0 else "github_activity"
        
        # Log to caretaker leaderboard & total interaction stats
        state['interactions']['total'] += len(new_events)
        
        user_data['count'] += len(new_events)
        user_data['lastInteractionAt'] = latest_event_time.isoformat()
        user_data['lastAction'] = action_name
        
        # Update last interaction at the top level
        current_last_at = None
        if state.get('lastInteraction') and isinstance(state['lastInteraction'], dict):
            current_last_at_str = state['lastInteraction'].get('at')
            if current_last_at_str:
                current_last_at = parse_time(current_last_at_str)
                
        if not current_last_at or latest_event_time > current_last_at:
            state['lastInteraction'] = {
                'user': owner,
                'action': action_name,
                'at': latest_event_time.isoformat()
            }
            
        # Revive fainted state if stats recovered
        if state['state'].get('status', '').lower() == 'fainted' and stats['hunger'] < 100 and stats['energy'] >= 20:
            state['state']['status'] = 'Happy'
            state['state']['currentAnimation'] = 'wooper_idle.gif'
            print(f"{pet_name} has been revived via GitHub activity!")
            
    return state


# ==========================================
# Game Engine & State Management
# ==========================================

def apply_decay(state, now=None):
    """Applies temporal decay to stats based on time elapsed since lastAutoUpdate."""
    state = _ensure_decay_carry(state)
    now = now or get_utc_now()

    last_update_str = state.get('timestamps', {}).get('lastAutoUpdate') or state.get('createdAt')
    if not last_update_str:
        state.setdefault('timestamps', {})['lastAutoUpdate'] = now.isoformat()
        return state

    last_update = parse_time(last_update_str)
    diff = now - last_update
    hours_passed = max(0.0, diff.total_seconds() / 3600.0)
    if hours_passed <= 0.0:
        return state

    carry = state['decayCarry']

    # 1. Hunger Increase
    hunger_delta = (hours_passed * HUNGER_INC_PER_HOUR) + float(carry.get('hunger', 0.0))
    hunger_inc = int(math.floor(hunger_delta))
    carry['hunger'] = hunger_delta - hunger_inc
    if hunger_inc:
        state['stats']['hunger'] = clamp(state['stats']['hunger'] + hunger_inc)

    # 2. Mood Decay (penalized if starving)
    mood_rate = MOOD_DEC_PER_HOUR
    if state['stats']['hunger'] >= 80:
        mood_rate += HUNGER_MOOD_PENALTY_PER_HOUR

    mood_delta = (hours_passed * mood_rate) + float(carry.get('mood', 0.0))
    mood_dec = int(math.floor(mood_delta))
    carry['mood'] = mood_delta - mood_dec
    if mood_dec:
        state['stats']['mood'] = clamp(state['stats']['mood'] - mood_dec)

    # 3. Energy Recovery / Decay
    mood = state['stats']['mood']
    hunger = state['stats']['hunger']

    energy_rate = 0.0
    if mood >= ENERGY_REC_MOOD_THRESHOLD and hunger <= ENERGY_REC_HUNGER_MAX:
        energy_rate = ENERGY_REC_PER_HOUR
    elif mood < ENERGY_STABLE_MOOD_THRESHOLD or hunger >= ENERGY_DECAY_HUNGER_THRESHOLD:
        energy_rate = -ENERGY_DEC_PER_HOUR

    if energy_rate == 0.0:
        carry['energy'] = 0.0
    else:
        # Soft caps/tapering for energy decay/recovery
        energy = state['stats']['energy']
        mult = 1.0
        if energy_rate < 0:
            if energy <= 20:
                mult = 0.1
            elif energy <= 30:
                t = (30 - energy) / 10.0
                mult = 1.0 - (0.9 * t)
        else:
            if energy >= 85:
                mult = 0.1
            elif energy >= 75:
                t = (energy - 75) / 10.0
                mult = 1.0 - (0.9 * t)

        effective_rate = abs(energy_rate) * mult
        energy_delta = (hours_passed * effective_rate) + float(carry.get('energy', 0.0))
        energy_mag = int(math.floor(energy_delta))
        carry['energy'] = energy_delta - energy_mag
        if energy_mag:
            state['stats']['energy'] = clamp(
                state['stats']['energy'] + (energy_mag if energy_rate > 0 else -energy_mag)
            )

    return state


def handle_action(state, action, user):
    """Processes user action commands (/feed, /play, /pet) and applies cooldowns/rewards."""
    now = get_utc_now()
    timestamps = state['timestamps']
    stats = state['stats']
    pet_name = state.get('name', 'cron')
    
    action = action.lower().replace('/', '').strip()
    
    # --- Feed ---
    if action == 'feed':
        last_fed = parse_time(timestamps['lastFedAt']) if timestamps.get('lastFedAt') else None
        if last_fed and COOLDOWN_FEED and (now - last_fed).total_seconds() < COOLDOWN_FEED:
            rem = int((COOLDOWN_FEED - (now - last_fed).total_seconds()) / 60)
            print(f"Cooldown active. You can feed again in {rem} minutes.")
            return state

        stats['hunger'] = clamp(stats['hunger'] - 70)
        stats['mood'] = clamp(stats['mood'] + 35)
        stats['energy'] = clamp(stats['energy'] + 45)
        timestamps['lastFedAt'] = now.isoformat()
        print(f"@{user} fed {pet_name}!")

        if state['state'].get('status', '').lower() == 'fainted' and stats['hunger'] < 100 and stats['energy'] >= 20:
            state['state']['status'] = 'Happy'
            state['state']['currentAnimation'] = 'wooper_idle.gif'
            print(f"{pet_name} has been revived via feeding.")

    # --- Play ---
    elif action == 'play':
        last_played = parse_time(timestamps['lastPlayedAt']) if timestamps.get('lastPlayedAt') else None
        if last_played and COOLDOWN_PLAY and (now - last_played).total_seconds() < COOLDOWN_PLAY:
            rem = int((COOLDOWN_PLAY - (now - last_played).total_seconds()) / 60)
            print(f"Cooldown active. You can play again in {rem} minutes.")
            return state

        if stats['energy'] < 20:
            print("Too tired to play.")
            return state

        if stats['hunger'] >= 85:
            print("Too hungry to play.")
            stats['energy'] = clamp(stats['energy'] - 5)
            return state

        energy_pct = stats['energy'] / 100.0
        mood_gain = int(65 * max(0.70, energy_pct))
        energy_cost = int(18 + (6 * (1 - energy_pct)))
        hunger_cost = 10

        stats['mood'] = clamp(stats['mood'] + mood_gain)
        stats['energy'] = clamp(stats['energy'] - energy_cost)
        stats['hunger'] = clamp(stats['hunger'] + hunger_cost)
        timestamps['lastPlayedAt'] = now.isoformat()
        print(f"@{user} played with {pet_name}! Mood +{mood_gain}, Energy -{energy_cost}")

    # --- Pet ---
    elif action == 'pet':
        last_petted = parse_time(timestamps['lastPettedAt']) if timestamps.get('lastPettedAt') else None
        if last_petted and COOLDOWN_PET and (now - last_petted).total_seconds() < COOLDOWN_PET:
            rem = int((COOLDOWN_PET - (now - last_petted).total_seconds()) / 60)
            print(f"Cooldown active. You can pet again in {rem} minutes.")
            return state

        stats['mood'] = clamp(stats['mood'] + 25)
        stats['energy'] = clamp(stats['energy'] + 8)
        timestamps['lastPettedAt'] = now.isoformat()
        print(f"@{user} petted {pet_name}! (mood +25, energy +8)")

        if stats['mood'] < 35:
            stats['mood'] = clamp(stats['mood'] + 20)
            print(f"Pet calmed {pet_name}.")
    
    else:
        print(f"Unknown command: {action}")
        return state

    # Record User Interactions
    state['interactions']['total'] += 1
    user_data = state['interactions']['byUser'].setdefault(user, {
        'count': 0,
        'lastInteractionAt': None,
        'lastAction': None
    })
    if isinstance(user_data, int):
        user_data = {
            'count': user_data,
            'lastInteractionAt': None,
            'lastAction': None
        }
        state['interactions']['byUser'][user] = user_data

    user_data['count'] += 1
    user_data['lastInteractionAt'] = now.isoformat()
    user_data['lastAction'] = action

    state['lastInteraction'] = {
        'user': user,
        'action': action,
        'at': now.isoformat()
    }

    return state


def determine_state(state):
    """Calculates status states and assigns corresponding sprite animation."""
    stats = state['stats']
    hunger = stats['hunger']
    mood = stats['mood']
    energy = stats['energy']
    timestamps = state['timestamps']
    now = get_utc_now()

    # 1. Action Animation Overrides (2 minutes window after action)
    for trigger, anim, status in [
        ('lastFedAt', 'wooper_eating.gif', 'Eating'),
        ('lastPlayedAt', 'wooper_play.gif', 'Playing'),
        ('lastPettedAt', 'wooper_petting.gif', 'Being Petted')
    ]:
        if timestamps.get(trigger):
            last_action_time = parse_time(timestamps[trigger])
            if (now - last_action_time).total_seconds() < 120:
                state['state']['currentAnimation'] = anim
                state['state']['status'] = status
                return state

    # 2. Post-action Happiness Window (120-150s after action)
    most_recent_action_time = None
    for action_key in ['lastFedAt', 'lastPlayedAt', 'lastPettedAt']:
        if timestamps.get(action_key):
            action_time = parse_time(timestamps[action_key])
            if most_recent_action_time is None or action_time > most_recent_action_time:
                most_recent_action_time = action_time
    
    if most_recent_action_time:
        seconds_since_action = (now - most_recent_action_time).total_seconds()
        if 120 <= seconds_since_action < 150:
            if mood >= 70 and energy >= 50 and hunger <= 60:
                state['state']['currentAnimation'] = "wooper_idle.gif"
                state['state']['status'] = "Excited"
            else:
                state['state']['currentAnimation'] = "wooper_idle.gif"
                state['state']['status'] = "Happy"
            return state

    # 3. Game Over / Fainted State
    if hunger >= 100 and energy <= 15:
        state['state']['currentAnimation'] = "wooper_fainted.gif"
        state['state']['status'] = "Fainted"
        return state

    # 4. Cry State
    if mood < 18:
        state['state']['currentAnimation'] = "wooper_crying.gif"
        state['state']['status'] = "Crying"
        return state

    # 5. Sad State
    if hunger >= 85 or energy < 18 or mood < 38:
        state['state']['currentAnimation'] = "wooper_sad.gif"
        state['state']['status'] = "Sad"
        return state

    # 6. Excited State
    if mood >= 82 and energy >= 55 and hunger <= 55:
        state['state']['currentAnimation'] = "wooper_idle.gif"
        state['state']['status'] = "Excited"
        return state

    # 7. Happy State
    if mood >= 62 and energy >= 32:
        state['state']['currentAnimation'] = "wooper_idle.gif"
        state['state']['status'] = "Happy"
        return state

    # 8. Idle State
    state['state']['currentAnimation'] = "wooper_idle.gif"
    state['state']['status'] = "Idle"
    return state


def simulate_distribution(seed_state, days=7, step_minutes=30, start_hunger=10, start_mood=80, start_energy=60):
    """Simulates automatic update decay cycles over days to test stability distributions."""
    sim_state = json.loads(json.dumps(seed_state))
    sim_state = _ensure_decay_carry(sim_state)
    created_at = parse_time(sim_state['createdAt']) if sim_state.get('createdAt') else get_utc_now()

    sim_state['stats']['hunger'] = clamp(start_hunger)
    sim_state['stats']['mood'] = clamp(start_mood)
    sim_state['stats']['energy'] = clamp(start_energy)
    sim_state['decayCarry'] = {'hunger': 0.0, 'mood': 0.0, 'energy': 0.0}

    sim_state.setdefault('timestamps', {})
    for k in ('lastFedAt', 'lastPlayedAt', 'lastPettedAt'):
        sim_state['timestamps'].pop(k, None)

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
        sim_state['ageHours'] = int((now - created_at).total_seconds() / 3600)
        sim_state = determine_state(sim_state)
        status = sim_state['state']['status']
        counts[status] = counts.get(status, 0) + 1
        total += 1

    return counts, total


# ==========================================
# README Generator
# ==========================================

def render_stat_bar(value, total_blocks=15):
    """Creates a stylized monospace stat bar with percentages."""
    percent = clamp(value)
    filled = int(round((percent / 100) * total_blocks))
    filled = min(total_blocks, filled)
    bar = '█' * filled + '░' * (total_blocks - filled)
    return f"`{bar}`&nbsp;{percent}%"


def make_issue_button(label, action):
    """Builds the HTML badge button leading to issue creation links."""
    issue_title = urllib.parse.quote_plus(f"/{action}")
    issue_body = urllib.parse.quote_plus(f"/{action}")
    badge_label = urllib.parse.quote(label)
    
    color = 'FF8C00'        # Dark Orange
    label_color = 'A0522D'  # Sienna
    
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
    """Checks the time since last_time_str and formats remaining cooldown status."""
    if not last_time_str:
        return "Ready"
    last_time = parse_time(last_time_str)
    now = get_utc_now()
    diff = (now - last_time).total_seconds()
    if not cooldown_seconds or cooldown_seconds <= 0 or diff >= cooldown_seconds:
        return "Ready"
    
    remaining = int((cooldown_seconds - diff) / 60)
    return f"Wait {remaining}m"


def get_action_hint(state, action):
    """Calculates human-readable warnings or tips for UI interaction buttons."""
    timestamps = state['timestamps']
    stats = state['stats']
    now = get_utc_now()
    action = action.lower().strip()

    if action == 'feed':
        last_fed = parse_time(timestamps['lastFedAt']) if timestamps.get('lastFedAt') else None
        if last_fed and COOLDOWN_FEED and (now - last_fed).total_seconds() < COOLDOWN_FEED:
            return f"He just ate — maybe later"
        return "Feed him"

    if action == 'play':
        last_played = parse_time(timestamps['lastPlayedAt']) if timestamps.get('lastPlayedAt') else None
        if last_played and COOLDOWN_PLAY and (now - last_played).total_seconds() < COOLDOWN_PLAY:
            remaining = int((COOLDOWN_PLAY - (now - last_played).total_seconds()) / 60)
            return f"Wait {max(1, remaining)}m"
        if stats.get('energy', 0) < 20:
            return "Too tired"
        if stats.get('hunger', 0) >= 85:
            return "Too hungry"
        return "Play with him"

    if action == 'pet':
        last_petted = parse_time(timestamps['lastPettedAt']) if timestamps.get('lastPettedAt') else None
        if last_petted and COOLDOWN_PET and (now - last_petted).total_seconds() < COOLDOWN_PET:
            remaining = int((COOLDOWN_PET - (now - last_petted).total_seconds()) / 60)
            return f"Wait {max(1, remaining)}m"
        return "Pet him"

    return ""


def update_readme(state):
    """Renders all updated status data, leaderboard entries, and animations into the README."""
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
    
    # Leaderboard rows builder
    users_list = []
    for user, data in state['interactions']['byUser'].items():
        if user in LEADERBOARD_EXCLUDE_USERS:
            continue
        count = data['count'] if isinstance(data, dict) else data
        users_list.append((user, count))
        
    sorted_users = sorted(users_list, key=lambda x: x[1], reverse=True)
    leaderboard_rows = [f"{i}. @{user} – {count}" for i, (user, count) in enumerate(sorted_users[:5], 1)]
    leaderboard_text = "\n".join(leaderboard_rows) if leaderboard_rows else "No interactions yet."

    status_text = state['state']['status'].title()
    sprite_file = state['state']['currentAnimation']
    
    status_feed = get_action_hint(state, 'feed')
    status_play = get_action_hint(state, 'play')
    status_pet = get_action_hint(state, 'pet')

    # Resolve last interaction text safely
    last = state.get('lastInteraction')
    if last and isinstance(last, dict):
        try:
            last_time = parse_time(last.get('at'))
            action_desc = last.get('action', '').replace('_', ' ')
            last_interaction_text = f"Last interaction: @{last.get('user')} — {action_desc} at {last_time.astimezone(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        except Exception:
            last_interaction_text = "Last interaction: data unavailable"
    else:
        # Scanning per-user data as a fallback
        last_user, last_time, last_action = None, None, None
        for user, data in state['interactions']['byUser'].items():
            if user in LEADERBOARD_EXCLUDE_USERS:
                continue
            if isinstance(data, dict) and data.get('lastInteractionAt'):
                try:
                    t = parse_time(data['lastInteractionAt'])
                except Exception:
                    continue
                if last_time is None or t > last_time:
                    last_time = t
                    last_user = user
                    last_action = data.get('lastAction')

        if last_user:
            action_desc = last_action.replace('_', ' ') if last_action else "interacted"
            last_interaction_text = f"Last interaction: @{last_user} — {action_desc} at {last_time.astimezone(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        else:
            last_interaction_text = "No interactions yet."

    # Retrieve owner's active streak if present
    owner = REPO_SLUG.split('/')[0]
    owner_data = state['interactions']['byUser'].get(owner, {})
    streak = 0
    if isinstance(owner_data, dict):
        streak = owner_data.get('streakDays', 0)
        
    streak_text = ""
    if streak > 0:
        multiplier = min(2.0, 1.0 + 0.1 * (max(1, streak) - 1))
        streak_text = f"\n    <p>🔥 <strong>Developer Streak:</strong> {streak} days ({multiplier:.1f}x activity boost!)</p>"

    new_section = f"""{start_marker}
<div align="center" id="github-tamagotchi">

### {state['name']} (Age: {state['ageHours'] // 24} days, {state['ageHours'] % 24} hours)

<div align="center" style="max-width: 600px; margin: 20px auto; font-family: monospace;">
        <p>
        He's <strong>cron</strong> the Wooper. He's my pet (yes, you can pet him!) and was the starter for my first successful randomized SoulSilver Nuzlocke.
    </p>{streak_text}
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
        <strong>[HUN] </strong>
        {render_stat_bar(100 - stats['hunger'])}<br><br>
        <strong>[MOD] </strong>
        {render_stat_bar(stats['mood'])}<br><br>
        <strong>[ENG] </strong>
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

  <div style="margin-top:8px;">
    <small><em>{last_interaction_text}</em></small>
  </div>


<details>
<summary><strong>Top Caretakers</strong></summary>

```
{leaderboard_text}
```
</details>

<details open>
<summary><strong>How to interact</strong></summary>
The system updates every 15 minutes automatically. After you take an action (e.g. `/feed`, `/play`, `/pet`), wait for the GitHub Action to finish and refresh this page to see the changes.

Use the buttons above or comment commands in an issue:

| Command | Effect | Cooldown |
| :--- | :--- | :--- |
| `/feed` | Massive refill: strongly restores Fullness, Mood, and Energy. | **2 hours** |
| `/play` | Big Mood boost, costs Energy, and increases Hunger. Requires Energy. | **45 mins** |
| `/pet` | Strong comfort boost to Mood with a short cooldown. | **15 mins** |

**States & Rules**:
- **Happy States**: Keep Mood high to make {state['name']} Playful or Excited!
- **Developer Streak**: Pushing code daily builds a streak (up to 2.0x bonus rewards) to help keep {state['name']} healthy and energized.
- **Warning Signs**: 
    - Low Fullness makes cron Hungry.
    - Low Energy makes cron Sleepy.
    - Low Mood makes cron Cry.
- **Critical Conditions**:
  - **Game Over**: If he gets too hungry and tired, {state['name']} will Faint.

</details>

<details>
<summary><strong>How this game works</strong></summary>

This is a fully automated creature living in the repository.
- **Time**: It ages and stats decay in real-time (updated every 15 minutes).
- **Memory**: It remembers who interacted with it and when.
- **Persistence**: All state is saved in `state/creature.json`.
- **Interaction**: You can influence its mood and health by clicking the buttons above, which open issues that trigger a GitHub Action to update the pet. After you take an action, wait for the GitHub Action to finish and refresh this page to see the updated pet.
</details>

</div>
{end_marker}"""

    new_content = content[:start_idx] + new_section + content[end_idx + len(end_marker):]
    with open(README_FILE, 'w') as f:
        f.write(new_content)


# ==========================================
# CLI Execution Entry Point
# ==========================================

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

    # 1. Handle Simulation Mode
    if args.simulate_days and args.simulate_days > 0:
        counts, total = simulate_distribution(
            state,
            days=args.simulate_days,
            step_minutes=SCHEDULE_STEP_MINUTES,
            start_hunger=args.sim_hunger,
            start_mood=args.sim_mood,
            start_energy=args.sim_energy,
        )
        fullness = clamp(100 - args.sim_hunger)
        interval_h = SCHEDULE_STEP_MINUTES // 60
        print(f"Simulated {args.simulate_days} days ({total} ticks @{interval_h}h) from Fullness {fullness}%, Mood {clamp(args.sim_mood)}%, Energy {clamp(args.sim_energy)}%")
        for k, v in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
            pct = (v / total) * 100 if total else 0
            print(f"- {k}: {v} ({pct:.1f}%)")
        return
    
    # 2. Main Pet Loop Mode
    now = get_utc_now()
    
    if not args.action:
        # Scheduled Cron Update Cycle
        state = apply_decay(state, now=now)
        state = update_github_activity(state)
        state.setdefault('timestamps', {})['lastAutoUpdate'] = now.isoformat()
        print("Ran automatic update cycle.")
    else:
        # User Action Interaction Cycle
        if not args.user:
            print("Error: --user is required for actions.")
            return
        state = apply_decay(state, now=now)
        state = update_github_activity(state)
        state.setdefault('timestamps', {})['lastAutoUpdate'] = now.isoformat()
        state = handle_action(state, args.action, args.user)

    # Calculate Age Dynamically
    if 'createdAt' in state:
        created_at = parse_time(state['createdAt'])
        age_hours = int((now - created_at).total_seconds() / 3600)
        state['ageHours'] = age_hours

    state = determine_state(state)
    save_state(state)
    update_readme(state)


if __name__ == '__main__':
    main()
