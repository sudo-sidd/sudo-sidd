import json
import os
import datetime
import argparse
import random

STATE_FILE = 'state/creature.json'
README_FILE = 'README.md'
SPRITES_DIR = 'sprites'

def load_state():
    with open(STATE_FILE, 'r') as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

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

    # Construct new content
    new_section = f"{start_marker}\n"
    new_section += "## My GitHub Pet\n\n"
    new_section += f"![Pet Status]({SPRITES_DIR}/{state['mood']}.svg)\n\n"
    new_section += "**Stats**\n"
    new_section += f"- **Mood**: {state['mood'].title()}\n"
    new_section += f"- **Hunger**: {state['hunger']:.1f}\n"
    new_section += f"- **Energy**: {state['energy']:.1f}\n"
    new_section += f"- **Happiness**: {state['happiness']:.1f}\n"
    new_section += f"- **Age**: {state['age']:.1f} days\n\n"
    new_section += "<details>\n<summary>How to interact</summary>\n\n"
    new_section += "This pet lives in my GitHub repo! You can interact with it by opening an issue with one of the following titles:\n"
    new_section += "- `feed`: Decreases hunger.\n"
    new_section += "- `play`: Increases happiness.\n"
    new_section += "- `rest`: Restores energy.\n\n"
    new_section += "The workflow runs periodically to update the pet's status.\n"
    new_section += "</details>\n"
    new_section += end_marker

    new_content = content[:start_idx] + new_section + content[end_idx + len(end_marker):]
    
    with open(README_FILE, 'w') as f:
        f.write(new_content)

def calculate_decay(state):
    now = datetime.datetime.utcnow()
    if not state['last_update']:
        state['last_update'] = now.isoformat()
        return state

    last_update = datetime.datetime.fromisoformat(state['last_update'])
    hours_passed = (now - last_update).total_seconds() / 3600.0
    
    # Decay rates per hour
    hunger_increase = 2 * hours_passed
    energy_decrease = 1.5 * hours_passed
    happiness_decrease = 1 * hours_passed
    age_increase = hours_passed / 24.0

    state['hunger'] = min(100, state['hunger'] + hunger_increase)
    state['energy'] = max(0, state['energy'] - energy_decrease)
    state['happiness'] = max(0, state['happiness'] - happiness_decrease)
    state['age'] += age_increase
    
    state['last_update'] = now.isoformat()
    return state

def apply_action(state, action):
    if not action:
        return state
    
    action = action.lower().strip()
    
    if 'feed' in action:
        state['hunger'] = max(0, state['hunger'] - 20)
        state['happiness'] += 5
    elif 'play' in action:
        state['happiness'] = min(100, state['happiness'] + 15)
        state['energy'] -= 10
        state['hunger'] += 5
    elif 'rest' in action or 'sleep' in action:
        state['energy'] = min(100, state['energy'] + 40)
        state['hunger'] += 5
    
    # Clamp values
    state['hunger'] = max(0, min(100, state['hunger']))
    state['energy'] = max(0, min(100, state['energy']))
    state['happiness'] = max(0, min(100, state['happiness']))
    
    return state

def determine_mood(state):
    if state['hunger'] > 80:
        return 'hungry'
    if state['energy'] < 20:
        return 'sleepy'
    if state['happiness'] < 30:
        return 'dead' # Or sad
    if state['happiness'] > 80:
        return 'happy'
    return 'neutral'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Action to perform (feed, play, rest)')
    args = parser.parse_args()

    state = load_state()
    state = calculate_decay(state)
    state = apply_action(state, args.action)
    state['mood'] = determine_mood(state)
    
    save_state(state)
    update_readme(state)
    print(f"Pet updated. Mood: {state['mood']}")

if __name__ == '__main__':
    main()
