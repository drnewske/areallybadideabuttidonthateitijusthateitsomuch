import requests
import json

def generate_m3u():
    api_url = "https://ntvstream.cx/api/get-iptv"
    output_file = "playlist.m3u"

    print(f"Fetching data from {api_url}...")

    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            print("API reported failure.")
            return

        channels = data.get("channels", [])
        print(f"Found {len(channels)} channels. Generating M3U...")

        # Open file in 'w' mode to overwrite everything
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")

            for channel in channels:
                # Extract metadata
                c_id = channel.get("id", "")
                c_name = channel.get("name", "Unknown Channel")
                c_country = channel.get("country", "")
                
                # Handle categories list
                categories = channel.get("categories", [])
                group_title = ";".join(categories) if categories else "Uncategorized"
                
                # Handle Alt Names for logo matching or search (optional, added as comment)
                # alt_names = channel.get("alt_names", [])

                # ATTEMPT TO FIND STREAM URL
                # The JSON snippet provided only showed metadata. 
                # Usually APIs like this return a 'url', 'stream', or 'source' field.
                # We check common fields, otherwise fallback to website.
                stream_url = channel.get("url") or channel.get("stream") or channel.get("source") or channel.get("website")

                if not stream_url:
                    stream_url = "# No URL found in JSON"

                # Construct the #EXTINF line
                # -1 means live stream
                # tvg-id is good for EPG matching
                # group-title organizes channels in players
                extinf = f'#EXTINF:-1 tvg-id="{c_id}" tvg-name="{c_name}" tvg-country="{c_country}" group-title="{group_title}",{c_name}'
                
                f.write(f"{extinf}\n")
                f.write(f"{stream_url}\n")

        print(f"Successfully created {output_file}")

    except Exception as e:
        print(f"An error occurred: {e}")
        exit(1)

if __name__ == "__main__":
    generate_m3u()
