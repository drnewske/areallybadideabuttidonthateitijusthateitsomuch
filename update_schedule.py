import requests
import json
import os
import hashlib
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
API_URL = "https://streamed.pk/api/matches/all-today"
IMG_BASE_URL = "https://streamed.pk/api/images/badge/"
STREAM_BASE_URL = "https://streamed.pk/api/stream/"
OUTPUT_FILE = "matches.json"
LOG_FILE = "match_history.log"

# Filter: Hide matches that started more than 12 hours ago
TWELVE_HOURS_MS = 12 * 60 * 60 * 1000

def fetch_matches():
    """Fetches the main list of matches."""
    try:
        response = requests.get(API_URL, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching main API: {e}")
        return []

def resolve_source(source_info):
    """
    Fetches the deep stream data for a single source.
    Returns a list of stream objects (url, lang, hd).
    """
    source = source_info.get('source')
    s_id = source_info.get('id')
    
    if not source or not s_id:
        return []

    try:
        url = f"{STREAM_BASE_URL}{source}/{s_id}"
        # Short timeout because we are running many of these
        response = requests.get(url, timeout=6)
        
        if response.status_code == 200:
            data = response.json()
            cleaned_streams = []
            for stream in data:
                cleaned_streams.append({
                    "url": stream.get("embedUrl"),
                    "language": stream.get("language", "Unknown"),
                    "hd": stream.get("hd", False),
                })
            return cleaned_streams
    except:
        return []
    return []

def process_match(api_match):
    """
    Fully processes a single match:
    1. Checks time limit.
    2. Resolves all sources (deep fetch).
    3. Formats the final object.
    """
    # 1. TIME FILTER
    match_date_ms = api_match.get('date', 0)
    current_time_ms = time.time() * 1000
    
    if current_time_ms - match_date_ms > TWELVE_HOURS_MS:
        return None

    # 2. SAFE EXTRACTION
    teams = api_match.get('teams') or {}
    home = teams.get('home') or {}
    away = teams.get('away') or {}

    home_badge = f"{IMG_BASE_URL}{home.get('badge')}.webp" if home.get('badge') else ""
    away_badge = f"{IMG_BASE_URL}{away.get('badge')}.webp" if away.get('badge') else ""

    # 3. DEEP LINK RESOLUTION (Parallelized in main, but logic is here)
    raw_sources = api_match.get('sources') or []
    final_links = []
    
    # We fetch sources sequentially per match, but matches run in parallel
    for s in raw_sources:
        streams = resolve_source(s)
        final_links.extend(streams)

    return {
        "id": api_match.get('id'),
        "title": api_match.get('title') or f"{home.get('name', 'Home')} vs {away.get('name', 'Away')}",
        "sport": api_match.get('category'),
        "kickOff": datetime.fromtimestamp(match_date_ms / 1000).isoformat(),
        "isLive": False, 
        "team1": {
            "name": home.get('name', 'Home Team'),
            "logo": home_badge
        },
        "team2": {
            "name": away.get('name', 'Away Team'),
            "logo": away_badge
        },
        "links": final_links 
    }

def generate_hash(data):
    """Generates a unique hash for the data to detect changes."""
    return hashlib.md5(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

def load_existing_data():
    if not os.path.exists(OUTPUT_FILE):
        return []
    try:
        with open(OUTPUT_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def main():
    print("Starting update job...")
    raw_matches = fetch_matches()
    
    if not raw_matches:
        print("No data received from API.")
        return

    # Process matches in parallel to speed up deep linking
    final_schedule = []
    print(f"Processing {len(raw_matches)} raw matches...")
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(process_match, raw_matches)
        for res in results:
            if res:
                final_schedule.append(res)

    # Sort by kickoff time
    final_schedule.sort(key=lambda x: x['kickOff'])

    # Change Detection
    current_data = load_existing_data()
    new_hash = generate_hash(final_schedule)
    old_hash = generate_hash(current_data)

    if new_hash != old_hash:
        print(f"Changes detected ({len(final_schedule)} matches). Writing to file...")
        
        # Write JSON
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(final_schedule, f, indent=2)
            
        # Write to Log
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] Updated: {len(final_schedule)} matches found. Hash: {new_hash}\n"
        
        with open(LOG_FILE, "a") as log:
            log.write(log_entry)
            
    else:
        print("No changes detected. Skipping write.")

if __name__ == "__main__":
    main()
