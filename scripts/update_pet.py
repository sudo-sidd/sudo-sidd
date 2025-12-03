import argparse
import datetime
import json
import os
import urllib.parse

STATE_FILE = 'state/creature.json'
README_FILE = 'README.md'
SPRITES_DIR = 'sprites'
REPO_SLUG = os.environ.get('GITHUB_REPOSITORY', 'sudo-sidd/sudo-sidd')


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def render_stat_row(label, value):
    percent = clamp(value)
    total_blocks = 20
    filled = int(round((percent / 100) * total_blocks))
    filled = min(total_blocks, filled)
    bar = '#' * filled + '-' * (total_blocks - filled)
    return (
        "        <tr>\n"
        f"          <td>{label}</td>\n"
        f"          <td><code>[{bar}] {percent:.0f}%</code></td>\n"
        "        </tr>"
    )


def make_issue_button(label, action, color):
    issue_title = urllib.parse.quote_plus(f"{action.title()} GitPet")
    issue_body = urllib.parse.quote_plus(f"I want to {action.lower()} GitPet!")
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

    stats_rows = "\n".join(
        [
            render_stat_row('Hunger', state['hunger']),
            render_stat_row('Energy', state['energy']),
            render_stat_row('Happiness', state['happiness'])
        ]
    )

    buttons = "\n    ".join(
        [
            make_issue_button('Feed', 'feed', 'FFD166'),
            make_issue_button('Play', 'play', '06D6A0'),
            make_issue_button('Rest', 'rest', '118AB2')
        ]
    )

    new_section = f"""{start_marker}
<div align=\"center\" id=\"github-tamagotchi\">

### My GitHub Tamagotchi

<table role=\"presentation\">
  <tr>
    <td align=\"center\" width=\"320\">
      <img src=\"{SPRITES_DIR}/egg.svg\" alt=\"GitPet egg\" width=\"120\" />
      <br />
      <img src=\"{SPRITES_DIR}/{state['mood']}.svg\" alt=\"{state['name']} is {state['mood']}\" width=\"180\" />
      <p><strong>{state['name']}</strong> · Mood: {state['mood'].title()}</p>
      <p>Age: {state['age']:.1f} days</p>
    </td>
    <td width=\"320\" valign=\"middle\">
      <strong>Live Stats</strong>
      <table>
{stats_rows}
      </table>
    </td>
  </tr>
</table>

<div>
    {buttons}
</div>

<sub>Swap <code>sprites/egg.svg</code> or mood sprites in <code>sprites/</code> to reskin GitPet. Numbers come from <code>state/creature.json</code>.</sub>

</div>

<details>
<summary>How to interact</summary>

Open an issue with titles like `feed`, `play`, or `rest` (the buttons above pre-fill everything). A GitHub Action runs `scripts/update_pet.py` to process the action and refresh this panel.

</details>
{end_marker}"""

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

    state['hunger'] = clamp(state['hunger'])
    state['energy'] = clamp(state['energy'])
    state['happiness'] = clamp(state['happiness'])

    return state


def determine_mood(state):
    if state['hunger'] > 80:
        return 'hungry'
    if state['energy'] < 20:
        return 'sleepy'
    if state['happiness'] < 30:
        return 'dead'
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
