#!/usr/bin/env python3
import urllib.request
import json
import datetime

USERNAME = 'sudo-sidd'

def get_contributions_data():
    # Uses a public API that scrapes the contribution graph (No Token Needed)
    url = f'https://github-contributions-api.jogruber.de/v4/{USERNAME}?y={datetime.date.today().year}'
    
    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def calculate_stats(data):
    if not data:
        return 0, 0, 0
    
    total = data.get('total', {}).get(str(datetime.date.today().year), 0)
    days = data.get('contributions', [])
    
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
    if streak == 0:
        if days_since_last == 0:
            return "<em>Ready to start contributing!</em>"
        elif days_since_last == 1:
            return "<em>Just a small break, no worries.</em>"
        elif days_since_last <= 3:
            return "<em>Taking a breather... happens to the best of us.</em>"
        elif days_since_last <= 7:
            return "<em>Been busy with other things, but let's get back!</em>"
        else:
            return "<em>Haven't been active lately, but every journey starts with a step.</em>"
    elif streak == 1:
        return "<em>Getting back into it! One day down.</em>"
    elif streak <= 6:
        return "<em>Building momentum, keep it going!</em>"
    elif streak <= 29:
        return "<em>On fire! This streak is impressive.</em>"
    else:
        return "<em>Unstoppable! You're crushing it!</em>"

def update_readme(status, sprite, total_contributions, streak, dynamic_text):
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
        <strong>{status}</strong>
      </td>
      <td align="left" style="border: none; padding: 20px; vertical-align: middle;">
        <strong>Stats ({datetime.date.today().year})</strong><br><br>
        <strong>Current Streak:</strong> {streak} days<br><br>
        <strong>Total Contributions:</strong> {total_contributions}<br><br>
        {dynamic_text}
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
        update_readme(status, sprite, total_contributions, streak, dynamic_text)