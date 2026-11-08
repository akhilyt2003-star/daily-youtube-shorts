import os, json, re, subprocess, textwrap, math, sys
from pathlib import Path
from datetime import datetime, timezone
import requests
from PIL import Image, ImageDraw, ImageFont

OUT = Path("output")
OUT.mkdir(exist_ok=True)
W, H = 720, 1280
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def call_gemini():
    key = os.environ["GEMINI_API_KEY"]
    niche = os.getenv("CHANNEL_TOPIC", "interesting science and history facts")
    language = os.getenv("VIDEO_LANGUAGE", "English")
    duration = os.getenv("VIDEO_DURATION", "35-45 seconds")
    prompt = f"""
Create one original, concise YouTube Short for this channel niche: {niche}.
Language: {language}. Target duration: {duration}.
Return ONLY valid JSON with this exact schema:
{{
 "title": "short accurate title, max 70 characters",
 "description": "2-3 sentence description plus a brief AI-assisted-content note if appropriate",
 "narration": "spoken narration, roughly 75-100 words",
 "scenes": [
   {{"screen_text":"2-6 words", "visual_note":"simple visual idea"}}
 ]
}}
Create 6 scenes. Start with a strong but truthful hook. Use clear spoken language.
Do not invent statistics, quotes, named sources, dates or dramatic details.
Avoid medical, legal, financial advice and current-news claims.
If a claim is uncertain, phrase it cautiously or choose a better-established topic.
Do not include markdown fences or extra keys.
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    r = requests.post(url, params={"key": key},
        json={"contents":[{"parts":[{"text":prompt}]}],
              "generationConfig":{"temperature":0.8,"responseMimeType":"application/json"}},
        timeout=90)
    r.raise_for_status()
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    obj = json.loads(text)
    if not isinstance(obj.get("scenes"), list) or len(obj["scenes"]) < 4:
        raise ValueError("Gemini returned too few scenes.")
    if len(obj.get("narration","").split()) < 35:
        raise ValueError("Narration is too short.")
    return obj

def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def wrap_words(draw, text, fnt, max_width):
    words, lines, line = text.split(), [], ""
    for word in words:
        test = (line + " " + word).strip()
        if draw.textbbox((0,0), test, font=fnt)[2] <= max_width:
            line = test
        else:
            if line: lines.append(line)
            line = word
    if line: lines.append(line)
    return lines

def make_card(scene, index, total, title):
    # Distinct colour bands without external images/assets; all graphics are generated locally.
    palettes = [
        ((12, 24, 48), (22, 78, 112)),
        ((35, 24, 65), (100, 45, 95)),
        ((8, 50, 56), (22, 105, 92)),
        ((55, 31, 17), (130, 74, 31)),
        ((22, 34, 68), (46, 85, 150)),
        ((46, 23, 44), (115, 49, 70))
    ]
    top, bottom = palettes[index % len(palettes)]
    im = Image.new("RGB", (W,H))
    pix = im.load()
    for y in range(H):
        t = y/(H-1)
        c = tuple(int(top[i]*(1-t)+bottom[i]*t) for i in range(3))
        for x in range(W): pix[x,y] = c
    d = ImageDraw.Draw(im)
    # Decorative circles and progress marker
    d.ellipse((W-190, 120, W+100, 410), outline=(255,255,255), width=3)
    d.ellipse((-130, 900, 190, 1220), outline=(255,255,255), width=3)
    d.rounded_rectangle((54, 70, 666, 86), radius=8, fill=(255,255,255,70))
    d.rounded_rectangle((54, 70, 54+612*(index+1)/total, 86), radius=8, fill=(255,210,75))
    d.text((58, 130), f"FACT FILE  /  {index+1:02d}", font=font(25,True), fill=(255,213,95))
    label = scene.get("screen_text","")
    lines = wrap_words(d, label.upper(), font(58,True), 580)
    y = 420 - (len(lines)*78)//2
    for line in lines:
        bbox = d.textbbox((0,0), line, font=font(58,True))
        tw = bbox[2]-bbox[0]
        d.text(((W-tw)//2, y), line, font=font(58,True), fill="white", stroke_width=1, stroke_fill=(0,0,0))
        y += 82
    note = scene.get("visual_note","")
    if note:
        small_lines = wrap_words(d, note, font(23), 550)[:3]
        y2 = 830
        for line in small_lines:
            tw = d.textbbox((0,0), line, font=font(23))[2]
            d.text(((W-tw)//2, y2), line, font=font(23), fill=(226,235,245))
            y2 += 34
    # Footer brand line
    d.text((58, 1170), "FOLLOW FOR MORE •", font=font(22,True), fill=(255,213,95))
    return im

def run(cmd):
    subprocess.run(cmd, check=True)

def main():
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("Missing GEMINI_API_KEY secret.")
    obj = call_gemini()
    (OUT/"metadata.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT/"script.txt").write_text(obj["narration"], encoding="utf-8")
    (OUT/"review_checklist.txt").write_text(
        "REVIEW BEFORE PUBLISHING\\n"
        "1. Fact-check the claims using reliable sources.\\n"
        "2. Listen for pronunciation and factual errors.\\n"
        "3. Check that every visual matches the narration.\\n"
        "4. Check title/description and platform policies.\\n"
        "5. If approved, upload in YouTube Studio and schedule for 7:00 PM IST.\\n"
        "Do not publish automatically: this workflow intentionally creates a draft only.\\n",
        encoding="utf-8")
    # Voice generation
    narration = obj["narration"]
    (OUT/"narration.txt").write_text(narration, encoding="utf-8")
    run(["espeak-ng", "-v", os.getenv("ESPEAK_VOICE","en-us"), "-s", "155",
         "-w", str(OUT/"voice.wav"), narration])
    # Duration of voice track; assign scene duration evenly, with slight minimum.
    probe = subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration",
                                     "-of","default=noprint_wrappers=1:nokey=1",str(OUT/"voice.wav")], text=True)
    audio_dur = float(probe.strip())
    scenes = obj["scenes"][:8]
    per = max(3.5, audio_dur/len(scenes))
    cards = []
    for i, scene in enumerate(scenes):
        p = OUT/f"scene_{i:02d}.png"
        make_card(scene, i, len(scenes), obj["title"]).save(p)
        cards.append((p, per))
    # Create concat manifest and render still cards into vertical video.
    manifest = OUT/"slides.txt"
    with manifest.open("w", encoding="utf-8") as f:
        for p, dur in cards:
            f.write(f"file '{p.resolve()}'\n")
            f.write(f"duration {dur:.3f}\n")
        f.write(f"file '{cards[-1][0].resolve()}'\n")
    silent = OUT/"silent.mp4"
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(manifest),
         "-vf","scale=720:1280,format=yuv420p","-r","30","-c:v","libx264",
         "-preset","veryfast","-crf","23",str(silent)])
    final = OUT/"SHORT_REVIEW_ME.mp4"
    run(["ffmpeg","-y","-i",str(silent),"-i",str(OUT/"voice.wav"),
         "-c:v","copy","-c:a","aac","-b:a","160k","-shortest","-movflags","+faststart",str(final)])
    print(f"Created draft: {final}")

if __name__ == "__main__":
    main()
