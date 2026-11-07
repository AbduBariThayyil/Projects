import json
import os
import subprocess
import sys

BASE_DIR = "/home/vibecoder/Projects/auto-shorts"
TEMP_DIR = os.path.join(BASE_DIR, "temp")
FINAL_OUTPUT = os.path.join(BASE_DIR, "deadliest_creatures_ranking_short.mp4")
FONT = "/usr/share/fonts/noto/NotoSans-Bold.ttf"

def escape_ffmpeg_text(text):
    return text.replace(":", "\\:").replace("'", "'\\\\''").replace("%", "\\%")

def wrap_text(text, max_chars=32):
    words = text.split()
    lines = []
    current = []
    curr_len = 0
    for w in words:
        if curr_len + len(w) + 1 > max_chars:
            lines.append(" ".join(current))
            current = [w]
            curr_len = len(w)
        else:
            current.append(w)
            curr_len += len(w) + 1
    if current:
        lines.append(" ".join(current))
    return "\\n".join(lines)

def render_scene(s, idx):
    img = s["image_file"]
    audio = s["audio_file"]
    frame_png = os.path.join(TEMP_DIR, f"frame_{idx}.png")
    seg_mp4 = os.path.join(TEMP_DIR, f"seg_{idx}.mp4")

    header_esc = escape_ffmpeg_text(s["header"])
    rank_esc = escape_ffmpeg_text(s["rank"])
    stat_esc = escape_ffmpeg_text(s["stat"])
    wrapped_speech = wrap_text(s["speech"])
    caption_esc = escape_ffmpeg_text(wrapped_speech)

    # Step 1: Render single composite frame image
    cmd_frame = [
        "ffmpeg", "-y", "-i", img,
        "-filter_complex",
        f"[0:v]scale=108:192:force_original_aspect_ratio=increase,crop=108:192,boxblur=5:1,scale=1080:1920:flags=bilinear,eq=brightness=-0.25[bg];"
        f"[0:v]scale=1020:960:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2-100[base];"
        f"[base]"
        f"drawtext=fontfile='{FONT}':text='{header_esc}':fontsize=50:fontcolor=white:box=1:boxcolor=red@0.9:boxborderw=16:x=(w-text_w)/2:y=180,"
        f"drawtext=fontfile='{FONT}':text='{rank_esc}':fontsize=76:fontcolor=yellow:borderw=6:bordercolor=black:x=(w-text_w)/2:y=280,"
        f"drawtext=fontfile='{FONT}':text='{stat_esc}':fontsize=44:fontcolor=white:borderw=4:bordercolor=black:box=1:boxcolor=black@0.65:boxborderw=10:x=(w-text_w)/2:y=380,"
        f"drawtext=fontfile='{FONT}':text='{caption_esc}':fontsize=46:fontcolor=white:borderw=5:bordercolor=black:box=1:boxcolor=black@0.75:boxborderw=16:line_spacing=12:x=(w-text_w)/2:y=1440[outv]",
        "-map", "[outv]", "-frames:v", "1", "-update", "1", frame_png
    ]
    subprocess.run(cmd_frame, check=True)

    # Step 2: Encode segment with audio
    cmd_seg = [
        "ffmpeg", "-y", "-loop", "1", "-framerate", "25",
        "-i", frame_png, "-i", audio,
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-pix_fmt", "yuv420p", seg_mp4
    ]
    subprocess.run(cmd_seg, check=True)
    return seg_mp4

def main():
    manifest_path = os.path.join(TEMP_DIR, "manifest.json")
    with open(manifest_path) as f:
        scenes = json.load(f)

    seg_files = []
    for idx, s in enumerate(scenes):
        print(f"Rendering scene {idx+1}/{len(scenes)}: {s['rank']}...")
        seg = render_scene(s, idx)
        seg_files.append(seg)

    # Step 3: Concat all segments
    concat_list_path = os.path.join(TEMP_DIR, "concat.txt")
    with open(concat_list_path, "w") as f:
        for fpath in seg_files:
            f.write(f"file '{fpath}'\n")

    print("Concatenating all segments into final video...")
    concat_cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy", FINAL_OUTPUT
    ]
    subprocess.run(concat_cmd, check=True)
    print(f"SUCCESS! Final video saved to: {FINAL_OUTPUT}")

    # Desktop notification
    subprocess.run(["notify-send", "Short Video Ready", "Deadliest Creatures ranking short has been generated!"], check=False)

if __name__ == "__main__":
    main()
