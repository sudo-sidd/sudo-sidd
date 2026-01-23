#!/usr/bin/env python3
import urllib.request
import json
import datetime

USERNAME = 'sudo-sidd'

# === DEDSEC COLOR THEME ===
COLOR_PURPLE = "#bd93f9"
COLOR_CYAN = "#8be9fd"
COLOR_RED = "#ff5555"
COLOR_BG_DARK = "#1a1b26"
COLOR_BORDER = "#bd93f9"

def get_contributions_data():
    url = f'https://github-contributions-api.jogruber.de/v4/{USERNAME}?y={datetime.date.today().year}'
    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def calculate_stats(data):
    if not data: return 0, 0
    total = data.get('total', {}).get(str(datetime.date.today().year), 0)
    days = data.get('contributions', [])
    days.sort(key=lambda x: x['date'], reverse=True)
    
    current_streak = 0
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    
    streak_active = False
    for day in days:
        day_date = datetime.datetime.strptime(day['date'], '%Y-%m-%d').date()
        count = day['count']
        if day_date == today:
            if count > 0:
                current_streak += 1
                streak_active = True
        elif day_date == yesterday:
            if count > 0:
                if not streak_active: 
                    current_streak += 1
                    streak_active = True
                elif streak_active: current_streak += 1
            elif not streak_active: break
        else:
            if streak_active:
                last_date = today - datetime.timedelta(days=current_streak)
                if day_date == last_date:
                    if count > 0: current_streak += 1
                    else: break
            else: break
    return total, current_streak

def get_status_data(streak, days_since_last=0):
    # 1. Select Sprite
    if streak >= 30: sprite = "wooper_play.gif"
    elif streak >= 7: sprite = "wooper_idle.gif"
    elif streak >= 1: sprite = "wooper_idle.gif"
    else: sprite = "wooper_sad.gif"

    # 2. Select Terminal Text (lowercase for aesthetic)
    if streak == 0:
        if days_since_last <= 1: text = "connection unstable. re-establishing link..."
        elif days_since_last <= 3: text = "system idle. touching grass."
        elif days_since_last <= 7: text = "offline mode active. i'll be back."
        else: text = "system dormant. reboot imminent."
    elif streak == 1: text = "link established. we are back in."
    elif streak <= 6: text = "upload stream active. flow state engaged."
    elif streak <= 29: text = "system optimized. shipping code daily."
    else: text = "god mode enabled. the streak is real."
        
    return sprite, text

def update_readme(sprite, status_text, total, streak):
    readme_path = 'README.md'
    try:
        with open(readme_path, 'r') as f: content = f.read()
    except FileNotFoundError: return

    start_marker = '<!-- TABLE-START -->'
    end_marker = '<!-- TABLE-END -->'
    
    start = content.find(start_marker)
    end = content.find(end_marker)
    
    if start == -1 or end == -1: return

    before = content[:start]
    after = content[end + len(end_marker):]

    # STYLING: Linux/Kitty Terminal aesthetic
    # Sharp corners (border-radius: 0px)
    # Purple borders, dark blue header background
    # Chain icon ⛓️ instead of traffic lights
    
    log_color = COLOR_CYAN if streak > 0 else COLOR_RED
    
    new_html = f'''
<div align="center">
  <table style="border: 1px solid {COLOR_BORDER}; border-radius: 0px; background: #0d1117; width: 80%; box-shadow: 0 0 10px {COLOR_BORDER}40;">
    <tr style="border-bottom: 1px solid {COLOR_BORDER};">
      <td colspan="2" style="padding: 8px; background: {COLOR_BG_DARK}; color: {COLOR_PURPLE}; font-family: monospace; font-size: 12px;">
        sudo_sidd @ github :: ~/status
      </td>
    </tr>
    <tr>
      <td align="center" style="padding: 20px; border-right: 1px solid {COLOR_BORDER}; width: 40%; vertical-align: middle;">
        <img src="sprites/{sprite}" alt="Pet" width="180" style="image-rendering: pixelated; filter: drop-shadow(0 0 5px {COLOR_PURPLE});" />
        <br><br>
        <code style="color: {COLOR_CYAN};">{status_text}</code>
      </td>
      <td align="left" style="padding: 20px; font-family: 'Courier New', monospace; color: {COLOR_PURPLE};">
        <strong>// system_metrics</strong><br><br>
        streak_active :: <code style="color: {COLOR_CYAN};">{streak} days</code><br>
        total_pkts&nbsp;&nbsp;&nbsp;&nbsp;:: <code style="color: {COLOR_CYAN};">{total}</code><br>
        current_year&nbsp;&nbsp;:: <code style="color: {COLOR_CYAN};">{datetime.date.today().year}</code><br><br>
        <br>
        <strong>// latest_log</strong><br>
        <span style="color: {log_color};">> uploading data...</span><span style="animation: blink 1s infinite; color: {COLOR_CYAN};">_</span>
      </td>
    </tr>
  </table>
</div>
'''

    with open(readme_path, 'w') as f:
        f.write(before + new_html + after)

if __name__ == '__main__':
    data = get_contributions_data()
    if data:
        total, streak = calculate_stats(data)
        
        days_list = data.get('contributions', [])
        days_list.sort(key=lambda x: x['date'], reverse=True)
        days_since = 0
        for d in days_list:
            if d['count'] == 0: days_since += 1
            else: break
            
        sprite, text = get_status_data(streak, days_since)
        update_readme(sprite, text, total, streak)