import asyncio
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
import edge_tts

OUT_DIR = "/home/vibecoder/Projects/auto-shorts/temp"
FINAL_OUT = "/home/vibecoder/Projects/auto-shorts/deadliest_creatures_short.mp4"
VOICE = "en-US-ChristopherNeural"

SCENES = [
    {
        "id": "intro",
        "search": "Earth from space night satellite",
        "header": "DEADLIEST ON EARTH",
        "rank": "TOP 5 COUNTDOWN",
        "stat": "Ranked by Annual Kills",
        "speech": "Ranking the top 5 deadliest creatures on Earth by annual human kill count. Number one will surprise you."
    },
    {
        "id": "rank5",
        "search": "Panthera leo male lion portrait",
        "header": "DEADLIEST ON EARTH",
        "rank": "#5 LIONS",
        "stat": "~250 Human Kills / Year",
        "speech": "At number 5: Lions. Responsible for around 250 fatal encounters every single year."
    },
    {
        "id": "rank4",
        "search": "Crocodylus niloticus crocodile mouth open",
        "header": "DEADLIEST ON EARTH",
        "rank": "#4 CROCODILES",
        "stat": "1,000+ Fatal Attacks / Year",
        "speech": "Number 4: Crocodiles. Over 1,000 fatal attacks annually. Do not step into their waters."
    },
    {
        "id": "rank3",
        "search": "Ophiophagus hannah king cobra snake",
        "header": "DEADLIEST ON EARTH",
        "rank": "#3 SNAKES",
        "stat": "100,000+ Deaths / Year",
        "speech": "Number 3: Venomous Snakes. Causing more than 100,000 deaths across the globe every year."
    },
    {
        "id": "rank2",
        "search": "Pedestrians crowd walking city street",
        "header": "DEADLIEST ON EARTH",
        "rank": "#2 HUMANS",
        "stat": "400,000+ Murders / Year",
        "speech": "Number 2: Humans. Taking approximately 400,000 lives of our own kind every year."
    },
    {
        "id": "rank1",
        "search": "Aedes aegypti mosquito macro feeding",
        "header": "DEADLIEST ON EARTH",
        "rank": "#1 THE MOSQUITO",
        "stat": "725,000+ Deaths / Year",
        "speech": "And number 1: The Mosquito. Killing over 725,000 people annually by spreading malaria and dengue. Which one surprised you? Drop a comment."
    }
]

headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def fetch_wiki_image(query, fallback_query=None):
    url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrsearch={urllib.parse.quote(query)}&gsrlimit=5&prop=imageinfo&iiprop=url|mime&format=json"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            pages = data.get('query', {}).get('pages', {})
            for pid, page in pages.items():
                info = page.get('imageinfo', [{}])[0]
                mime = info.get('mime', '')
                img_url = info.get('url', '')
                if 'image/jpeg' in mime or 'image/png' in mime or img_url.endswith(('.jpg', '.jpeg', '.png')):
                    return img_url
    except Exception as e:
        print(f"Error querying {query}: {e}")
    if fallback_query:
        return fetch_wiki_image(fallback_query)
    return None

async def generate_speech(text, out_mp3):
    communicate = edge_tts.Communicate(text, VOICE, rate="+6%")
    await communicate.save(out_mp3)

def get_duration(audio_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
    return float(res.stdout.strip())

async def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for i, s in enumerate(SCENES):
        img_file = os.path.join(OUT_DIR, f"{s['id']}.jpg")
        audio_file = os.path.join(OUT_DIR, f"{s['id']}.mp3")
        
        if not os.path.exists(audio_file):
            print(f"[{i+1}/{len(SCENES)}] Generating voice for: {s['rank']}...")
            await generate_speech(s["speech"], audio_file)
            time.sleep(1)
        dur = get_duration(audio_file)
        s["duration"] = dur
        print(f"  Duration: {dur:.2f}s")
        
        if not os.path.exists(img_file):
            time.sleep(2)
            print(f"[{i+1}/{len(SCENES)}] Fetching image for: {s['search']}...")
            img_url = fetch_wiki_image(s["search"])
            if not img_url:
                print(f"  Fallback query used for {s['id']}")
                img_url = fetch_wiki_image(s["id"])
            print(f"  Found URL: {img_url}")
            time.sleep(1)
            req = urllib.request.Request(img_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                with open(img_file, "wb") as f:
                    f.write(resp.read())
        s["image_file"] = img_file
        s["audio_file"] = audio_file

    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as f:
        json.dump(SCENES, f, indent=2)
    print("All assets prepared successfully!")

if __name__ == "__main__":
    asyncio.run(main())
