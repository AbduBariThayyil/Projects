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
VENV_PYTHON = os.path.join(BASE_DIR, ".venv", "bin", "python3")

def run_nice(cmd, allow_101=False):
    """Run command with low CPU priority and 2-thread cap."""
    res = subprocess.run(["nice", "-n", "15"] + cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0 and not (allow_101 and res.returncode == 101):
        raise subprocess.CalledProcessError(res.returncode, cmd, output=res.stdout, stderr=res.stderr)
    return res

async def generate_voice_clips():
    """Generate audio countdown announcements."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    for num in [5, 4, 3, 2, 1]:
        voice_path = os.path.join(TEMP_DIR, f"voice_{num}.mp3")
        if not os.path.exists(voice_path):
            c = edge_tts.Communicate(f"Number {num}", "en-US-ChristopherNeural", rate="+10%")
            await c.save(voice_path)
    print("Voice countdown announcements ready.")

def ensure_chime():
    """Synthesize clean transition bell sound effect."""
    chime_path = os.path.join(TEMP_DIR, "chime.wav")
    if not os.path.exists(chime_path):
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=987.77:duration=0.25,afade=t=out:st=0.08:d=0.17",
            chime_path
        ]
        run_nice(cmd, allow_101=True)
    return chime_path

def download_source_compilation(topic):
    """Download a top viral compilation video for the topic."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    out_template = os.path.join(TEMP_DIR, "source_video.%(ext)s")
    
    # Clean previous sources
    for old in glob.glob(os.path.join(TEMP_DIR, "source_video.*")):
        os.remove(old)

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

    # Scan up to 180 seconds with 2 threads
    cmd = [
        "ffmpeg", "-threads", "2", "-t", "180",
        "-i", src_file,
        "-filter_complex", f"select='gt(scene,0.35)',metadata=print:file='{scenes_txt}'",
        "-f", "null", "-"
    ]
    run_nice(cmd, allow_101=True)

    timestamps = [1.0]
    if os.path.exists(scenes_txt):
        with open(scenes_txt) as f:
            for line in f:
                if "pts_time" in line:
                    match = re.search(r"pts_time:([0-9\.]+)", line)
                    if match:
                        timestamps.append(float(match.group(1)))

    # Filter timestamps to ensure at least 6 seconds apart
    filtered = []
    last_t = -10.0
    for t in timestamps:
        if t - last_t >= 6.0:
            filtered.append(t)
            last_t = t
        if len(filtered) == 5:
            break

    # If fewer than 5 scene cuts found, fallback to even intervals
    if len(filtered) < 5:
        filtered = [2.0, 25.0, 50.0, 75.0, 100.0]

    print(f"Selected 5 clip start timestamps: {filtered}")
    return filtered

def extract_and_composite(src_file, timestamps, header_title):
    """Extract 5 clips and composite each to 1080x1920 vertical with badges and audio."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    chime_path = ensure_chime()
    rendered_segments = []

    header_clean = header_title.upper().replace("'", "").replace(":", "")

    for idx, start_t in enumerate(timestamps):
        rank_num = 5 - idx
        seg_dur = 6.0 if rank_num > 1 else 7.0
        seg_out = os.path.join(TEMP_DIR, f"rendered_rank_{rank_num}.mp4")
        voice_path = os.path.join(TEMP_DIR, f"voice_{rank_num}.mp3")

        print(f"Rendering rank #{rank_num} (starts at {start_t:.1f}s)...")

        # 1080x1920 vertical composition
        cmd = [
            "ffmpeg", "-y", "-threads", "2",
            "-ss", str(start_t), "-t", str(seg_dur),
            "-i", src_file,
            "-i", voice_path,
            "-i", chime_path,
            "-filter_complex",
            f"[0:v]scale=108:192:force_original_aspect_ratio=increase,crop=108:192,boxblur=5:1,scale=1080:1920:flags=bilinear,eq=brightness=-0.2[bg];"
            f"[0:v]crop=in_w*0.92:in_h*0.92:(in_w-out_w)/2:(in_h-out_h)/2,scale=1080:1080:force_original_aspect_ratio=decrease,setsar=1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
            f"[base]drawtext=fontfile='{FONT}':text='{header_clean}':fontsize=54:fontcolor=white:box=1:boxcolor=red@0.9:boxborderw=18:x=(w-text_w)/2:y=180,"
            f"drawtext=fontfile='{FONT}':text='NUMBER {rank_num}':fontsize=76:fontcolor=yellow:borderw=6:bordercolor=black:box=1:boxcolor=black@0.65:boxborderw=14:x=(w-text_w)/2:y=290,setsar=1[v];"
            f"[2:a]volume=0.8,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a_chime];"
            f"[1:a]adelay=150|150,volume=1.4,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a_voice];"
            f"[a_chime][a_voice]amix=inputs=2:duration=first:dropout_transition=0[sfx];"
            f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[clip_a];"
            f"[clip_a][sfx]amix=inputs=2:duration=first:dropout_transition=0[aout]",
            "-map", "[v]", "-map", "[aout]",
            "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1", "-preset", "veryfast",
            "-c:a", "aac", "-ar", "44100", "-b:a", "128k",
            "-shortest", "-pix_fmt", "yuv420p", seg_out
        ]
        run_nice(cmd, allow_101=True)
        rendered_segments.append(seg_out)

    return rendered_segments

def concatenate_segments(segments, final_path):
    """Concatenate all 5 ranked clips into final Short."""
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
    run_nice(cmd, allow_101=True)
    print(f"FINAL VIDEO COMPLETE: {final_path}")

def main():
    parser = argparse.ArgumentParser(description="Autonomous Viral Ranking Short Generator")
    parser.add_argument("--topic", default="funniest gym fails", help="Topic query for viral clips")
    parser.add_argument("--header", default="FUNNIEST GYM FAILS", help="Banner title on top of video")
    parser.add_argument("--output", default=None, help="Output mp4 path")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    final_output = args.output or os.path.join(OUTPUT_DIR, f"{args.topic.replace(' ', '_')}_short.mp4")

    # 1. Voice countdown
    asyncio.run(generate_voice_clips())

    # 2. Source video
    src_file = download_source_compilation(args.topic)

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
