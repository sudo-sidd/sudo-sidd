#!/usr/bin/env python3
import urllib.request
import json
import datetime

USERNAME = 'sudo-sidd'

def get_contributions_data():
    # Uses a public API that scrapes the contribution graph (No Token Needed)
    url = f'https://github-contributions-api.jogruber.de/v4/{USERNAME}'
    
    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def calculate_stats(data):
    if not data:
        return 0, 0, 0
    
    totals = data.get('total', {})
    if not totals:
        return 0, 0, 0
    
    # Find the latest year
    latest_year = max(int(y) for y in totals.keys())
    total = totals.get(str(latest_year), 0)
    
    days = data.get('contributions', [])
    
    # Filter days for the latest year
    days = [d for d in days if d['date'].startswith(str(latest_year))]
    
    # Sort days by date descending
    days.sort(key=lambda x: x['date'], reverse=True)
    
    current_streak = 0
    today = datetime.date.today()
    
    # Check consecutive days from today backwards
    current_date = today
    for day in days:
        day_date = datetime.datetime.strptime(day['date'], '%Y-%m-%d').date()
        if day_date == current_date and day['count'] > 0:
            current_streak += 1
            current_date -= datetime.timedelta(days=1)
        elif day_date < current_date:
            break
    
    # Calculate days since last contribution
    days_since_last = 0
    if current_streak == 0:
        for day in days:
            if day['count'] > 0:
                last_date = datetime.datetime.strptime(day['date'], '%Y-%m-%d').date()
                days_since_last = (today - last_date).days
                break
    
    return total, current_streak, days_since_last

def get_status_and_sprite(streak):
    if streak >= 30:
        return f"Excited! (Streak: {streak} days)", "wooper_play.gif"
    elif streak >= 7:
        return f"Happy! (Streak: {streak} days)", "wooper_idle.gif"
    elif streak >= 1:
        return f"Content (Streak: {streak} days)", "wooper_idle.gif"
    elif streak == 0:
        return f"Sad (Streak broken)", "wooper_sad.gif"
    else:
        return "Fainted", "wooper_fainted.gif"

def get_dynamic_text(streak, days_since_last):
    # Scenario: Streak is broken (0)
    if streak == 0:
        if days_since_last == 0:
            return "<em>Coffee in hand, ready to push code.</em>"
        elif days_since_last == 1:
            return "<em>Took a quick breather yesterday.</em>"
        elif days_since_last <= 3:
            return "<em>Touching grass for a few days.</em>"
        elif days_since_last <= 7:
            return "<em>Busy week IRL, but I'll be back.</em>"
        else:
            return "<em>Currently in lurking mode.</em>"
            
    # Scenario: Streak is active (>0)
    elif streak == 1:
        return "<em>Back in the terminal. Streak starts now.</em>"
    elif streak <= 6:
        return "<em>In the flow. Coding daily.</em>"
    elif streak <= 29:
        return "<em>Locked in and shipping code consistently.</em>"
    else:
        return "<em>Living in the terminal. The streak is real.</em>"

def update_readme(status, sprite, total_contributions, streak, dynamic_text, year):
    readme_path = 'README.md'
    try:
        with open(readme_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print("README.md not found!")
        return

    # Markers to find the section
    start_marker = '<!-- PET-START -->'
    end_marker = '<!-- PET-END -->'
    
    start = content.find(start_marker)
    end = content.find(end_marker)
    
    if start == -1 or end == -1:
        print("Markers not found in README.md")
        return

    before = content[:start]
    after = content[end + len(end_marker):]

    # HTML Content with table
    new_section = f'''{start_marker}
<div align="center" id="github-stats">

### GitHub Activity

<div align="center">
  <table border="0" style="border: none; background: transparent;">
    <tr>
      <td align="center" style="border: none; padding: 20px;">
        <img src="sprites/{sprite}" alt="Woop" width="256" style="image-rendering: pixelated;" />
        <br>
        <strong>{dynamic_text}</strong>
      </td>
      <td align="left" style="border: none; padding: 20px; vertical-align: middle;">
        <strong>Stats ({year})</strong><br><br>
        <strong>Current Streak:</strong> {streak} days<br><br>
        <strong>Total Contributions:</strong> {total_contributions}
      </td>
    </tr>
  </table>
</div>

</div>
{end_marker}'''

    new_content = before + new_section + after

    with open(readme_path, 'w') as f:
        f.write(new_content)
    print("README updated successfully.")

if __name__ == '__main__':
    data = get_contributions_data()
    if data:
        total_contributions, streak, days_since_last = calculate_stats(data)
        status, sprite = get_status_and_sprite(streak)
        dynamic_text = get_dynamic_text(streak, days_since_last)
        # Find latest year
        totals = data.get('total', {})
        year = max(int(y) for y in totals.keys()) if totals else datetime.date.today().year
        update_readme(status, sprite, total_contributions, streak, dynamic_text, year)