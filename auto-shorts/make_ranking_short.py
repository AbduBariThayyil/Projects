#!/usr/bin/env python3
"""
Autonomous Viral Ranking Short Generator
100% Real Internet Clips | Low-Resource Safe (Dual-core / 4GB RAM)
"""

import argparse
import asyncio
import glob
import json
import os
import re
import subprocess
import sys
import edge_tts

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
FONT = "/usr/share/fonts/noto/NotoSans-Bold.ttf"

TRANSITION_SCRIPTS = {
    5: "Ranking the top 5 worst {topic}! Starting off at Number 5.",
    4: "Moving down to Number 4! Watch this.",
    3: "Number 3... it only gets worse.",
    2: "Number 2 was completely avoidable!",
    1: "And Number 1 is an absolute disaster! Which one was the worst? Comment below."
}

def run_nice(cmd, allow_101=False):
    """Run command with low CPU priority and 2-thread cap."""
    res = subprocess.run(["nice", "-n", "15"] + cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0 and not (allow_101 and res.returncode == 101):
        raise subprocess.CalledProcessError(res.returncode, cmd, output=res.stdout, stderr=res.stderr)
    return res

async def generate_voice_clips(topic):
    """Generate dynamic transition countdown announcements bridging clips together."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    for num, tmpl in TRANSITION_SCRIPTS.items():
        voice_path = os.path.join(TEMP_DIR, f"voice_{num}.mp3")
        if os.path.exists(voice_path) and os.path.getsize(voice_path) > 1000:
            continue
        text = tmpl.format(topic=topic)
        for attempt in range(4):
            try:
                c = edge_tts.Communicate(text, "en-US-ChristopherNeural", rate="+10%")
                await c.save(voice_path)
                if os.path.exists(voice_path) and os.path.getsize(voice_path) > 1000:
                    break
            except Exception as e:
                print(f"Retry {attempt+1} for voice {num}: {e}")
                await asyncio.sleep(1.5)
    print("Voice transition announcements ready.")

def ensure_sfx():
    """Synthesize high-energy whoosh + ding transition sound effect."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    sfx_path = os.path.join(TEMP_DIR, "sfx_transition.wav")
    whoosh = os.path.join(TEMP_DIR, "whoosh.wav")
    ding = os.path.join(TEMP_DIR, "ding.wav")

    cmd_whoosh = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "anoisesrc=d=0.3:c=pink:r=44100,lowpass=f=900,afade=t=in:st=0:d=0.1,afade=t=out:st=0.1:d=0.2,volume=1.8",
        whoosh
    ]
    run_nice(cmd_whoosh)

    cmd_ding = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=1200:duration=0.35,afade=t=out:st=0.05:d=0.3,volume=1.5",
        ding
    ]
    run_nice(cmd_ding)

    cmd_mix = [
        "ffmpeg", "-y", "-i", whoosh, "-i", ding,
        "-filter_complex", "amix=inputs=2:duration=first:dropout_transition=0:normalize=0,volume=1.6",
        sfx_path
    ]
    run_nice(cmd_mix)
    return sfx_path

def download_source_compilation(topic):
    """Download a top viral compilation video for the topic."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    out_template = os.path.join(TEMP_DIR, "source_video.%(ext)s")
    
    # Check if a source already exists for this query
    existing = [f for f in glob.glob(os.path.join(TEMP_DIR, "source_video.*")) if not f.endswith(('.part', '.ytdl'))]
    if existing:
        print(f"Using existing source footage: {existing[0]}")
        return existing[0]

    print(f"Searching for top viral compilation for topic: '{topic}'...")
    query = f"ytsearch5:{topic} compilation"
    cmd = [
        "yt-dlp",
        "--match-filter", "duration >= 90 & duration <= 600",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "--max-downloads", "1",
        query,
        "-o", out_template
    ]
    run_nice(cmd, allow_101=True)

    downloaded = [f for f in glob.glob(os.path.join(TEMP_DIR, "source_video.*")) if not f.endswith(('.part', '.ytdl'))]
    if not downloaded:
        raise RuntimeError("Failed to find or download source video matching query.")
    src_file = downloaded[0]
    print(f"Downloaded source video: {src_file}")
    return src_file

def detect_scene_cuts(src_file):
    """Detect natural comedic scene cut timestamps across the source video."""
    print("Detecting scene cuts across source footage...")
    scenes_txt = os.path.join(TEMP_DIR, "scenes.txt")
    if os.path.exists(scenes_txt):
        os.remove(scenes_txt)

    cmd = [
        "ffmpeg", "-threads", "2", "-t", "180",
        "-i", src_file,
        "-filter_complex", f"select='gt(scene,0.35)',metadata=print:file='{scenes_txt}'",
        "-f", "null", "-"
    ]
    run_nice(cmd)

    timestamps = [2.0]
    if os.path.exists(scenes_txt):
        with open(scenes_txt) as f:
            for line in f:
                if "pts_time" in line:
                    match = re.search(r"pts_time:([0-9\.]+)", line)
                    if match:
                        timestamps.append(float(match.group(1)))

    filtered = []
    last_t = -15.0
    for t in timestamps:
        if t - last_t >= 8.0:
            filtered.append(t)
            last_t = t
        if len(filtered) == 5:
            break

    if len(filtered) < 5:
        filtered = [8.0, 30.0, 55.0, 80.0, 110.0]

    print(f"Selected 5 clip start timestamps: {filtered}")
    return filtered

def extract_and_composite(src_file, timestamps, header_title):
    """Extract 5 clips and composite each to 1080x1920 vertical with left-aligned badges and audible sound mixing."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    sfx_path = ensure_sfx()
    rendered_segments = []

    header_clean = header_title.upper().replace("'", "").replace(":", "")

    # Durations tailored to voiceover lengths
    durations = {5: 6.5, 4: 6.0, 3: 6.0, 2: 5.5, 1: 8.0}

    for idx, start_t in enumerate(timestamps):
        rank_num = 5 - idx
        seg_dur = durations.get(rank_num, 6.0)
        seg_out = os.path.join(TEMP_DIR, f"rendered_rank_{rank_num}.mp4")
        voice_path = os.path.join(TEMP_DIR, f"voice_{rank_num}.mp3")

        print(f"Rendering rank #{rank_num} (starts at {start_t:.1f}s, dur {seg_dur}s)...")

        # Layout: Blurred mirror background + 8% cropped centered clip (watermark removal) + LEFT-ALIGNED RANKING
        cmd = [
            "ffmpeg", "-y", "-threads", "2",
            "-ss", str(start_t), "-t", str(seg_dur),
            "-i", src_file,
            "-i", voice_path,
            "-i", sfx_path,
            "-filter_complex",
            f"[0:v]scale=108:192:force_original_aspect_ratio=increase,crop=108:192,boxblur=5:1,scale=1080:1920:flags=bilinear,eq=brightness=-0.2[bg];"
            f"[0:v]crop=in_w*0.92:in_h*0.92:(in_w-out_w)/2:(in_h-out_h)/2,scale=1080:1080:force_original_aspect_ratio=decrease,setsar=1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
            f"[base]drawtext=fontfile='{FONT}':text='{header_clean}':fontsize=46:fontcolor=white:box=1:boxcolor=red@0.9:boxborderw=16:x=60:y=240,"
            f"drawtext=fontfile='{FONT}':text='#{rank_num}':fontsize=110:fontcolor=yellow:borderw=8:bordercolor=black:box=1:boxcolor=black@0.75:boxborderw=20:x=60:y=340,setsar=1[v];"
            f"[2:a]volume=1.5,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[sfx];"
            f"[1:a]adelay=100|100,volume=2.2,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[voice];"
            f"[sfx][voice]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[vo_track];"
            f"[0:a]volume=0.5,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[bg_audio];"
            f"[bg_audio][vo_track]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]",
            "-map", "[v]", "-map", "[aout]",
            "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1", "-preset", "veryfast", "-r", "30",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
            "-shortest", "-pix_fmt", "yuv420p", seg_out
        ]
        run_nice(cmd)
        rendered_segments.append(seg_out)

    return rendered_segments

def concatenate_segments(segments, final_path):
    """Concatenate all 5 ranked clips into final Short with clean timestamp generation."""
    concat_txt = os.path.join(TEMP_DIR, "concat_final.txt")
    with open(concat_txt, "w") as f:
        for s in segments:
            f.write(f"file '{s}'\n")

    print(f"Assembling final Short into: {final_path}...")
    cmd = [
        "ffmpeg", "-y", "-fflags", "+genpts",
        "-f", "concat", "-safe", "0",
        "-i", concat_txt,
        "-avoid_negative_ts", "make_zero",
        "-c", "copy", final_path
    ]
    run_nice(cmd)
    print(f"FINAL VIDEO COMPLETE: {final_path}")

def main():
    parser = argparse.ArgumentParser(description="Autonomous Viral Ranking Short Generator")
    parser.add_argument("--topic", default="car fails", help="Topic query for viral clips")
    parser.add_argument("--header", default="CAR FAILS", help="Banner title on top/left of video")
    parser.add_argument("--src", default=None, help="Explicit source video path (optional)")
    parser.add_argument("--output", default=None, help="Output mp4 path")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    final_output = args.output or os.path.join(OUTPUT_DIR, f"{args.topic.replace(' ', '_')}_short.mp4")

    # 1. Voice transition countdown
    asyncio.run(generate_voice_clips(args.topic))

    # 2. Source video
    src_file = args.src or download_source_compilation(args.topic)

    # 3. Scene cuts
    cuts = detect_scene_cuts(src_file)

    # 4. Composite clips
    segments = extract_and_composite(src_file, cuts, args.header)

    # 5. Concatenate
    concatenate_segments(segments, final_output)

    # 6. Desktop Alert
    subprocess.run(["notify-send", "Ranking Short Ready", f"Created: {os.path.basename(final_output)}"], check=False)

if __name__ == "__main__":
    main()
