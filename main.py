import os, json, subprocess, textwrap, re, math
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path("output")
OUT.mkdir(exist_ok=True)
W, H = 1080, 1920
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

def run(cmd):
    subprocess.run(cmd, check=True)

def gemini_script():
    key = os.environ["GEMINI_API_KEY"]
    niche = os.getenv("CHANNEL_TOPIC", "science, human psychology and unusual facts")
    language = os.getenv("VIDEO_LANGUAGE", "English")
    prompt = f"""
Create one original YouTube Short for a channel about {niche}.
Language: {language}. Target spoken duration: 35-45 seconds.
Return ONLY JSON with keys title, description, narration, scenes.
scenes must contain exactly 6 objects, each with screen_text (2-5 words),
visual_note (one concrete visual scene), and visual_subject (one of:
brain, person, door, magnifier, planet, atom, book, heart, eye, generic).
Start with a truthful hook. Use 75-100 spoken words.
Avoid unsupported statistics, fabricated quotes, medical advice and current-news claims.
Make each visual_note describe a simple cartoon scene that can be illustrated.
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    r = requests.post(url, params={"key": key},
        json={"contents":[{"parts":[{"text":prompt}]}],
              "generationConfig":{"temperature":0.75,"responseMimeType":"application/json"}},
        timeout=90)
    if r.status_code == 404:
        raise RuntimeError(f"Gemini model '{MODEL}' returned 404. Check available models in Google AI Studio and set GEMINI_MODEL as a GitHub Actions variable to a supported generateContent model. Response: {r.text[:500]}")
    r.raise_for_status()
    obj = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    if len(obj.get("scenes", [])) != 6 or len(obj.get("narration","").split()) < 40:
        raise ValueError("Gemini returned an incomplete script. Re-run the workflow.")
    return obj

def get_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]
    for p in paths:
        if Path(p).exists(): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def gradient_bg(seed):
    palettes = [((12,25,58),(48,70,125)),((48,20,66),(117,47,92)),((8,48,57),(26,105,105)),
                ((57,32,22),(143,77,43)),((18,39,73),(57,88,147)),((46,23,48),(120,48,76))]
    a,b = palettes[seed % len(palettes)]
    im = Image.new("RGB",(W,H))
    d=ImageDraw.Draw(im)
    for y in range(H):
        t=y/(H-1); c=tuple(int(a[i]*(1-t)+b[i]*t) for i in range(3))
        d.line((0,y,W,y),fill=c)
    return im

def draw_subject(d, subject, cx, cy, scale=1.0):
    # Original layered vector-style illustrations; faux depth via offset shadows and highlights.
    s=scale
    def ell(box, fill, outline=None, width=5):
        x1,y1,x2,y2=box
        box=(int(x1),int(y1),int(x2),int(y2))
        sh=(box[0]+18,box[1]+24,box[2]+18,box[3]+24)
        d.ellipse(sh,fill=(8,12,28))
        d.ellipse(box,fill=fill,outline=outline or (245,245,255),width=width)
    if subject=="brain":
        ell((cx-190*s,cy-130*s,cx+190*s,cy+130*s),(244,112,145))
        for dx,dy in [(-90,-40),(-25,-80),(55,-45),(100,35),(10,55),(-85,55)]:
            d.arc((cx+(dx-50)*s,cy+(dy-45)*s,cx+(dx+50)*s,cy+(dy+45)*s),0,300,fill=(255,210,220),width=max(3,int(9*s)))
    elif subject in ("person","heart","eye"):
        # cartoon person bust
        ell((cx-95*s,cy-230*s,cx+95*s,cy-40*s),(255,190,137))
        d.rounded_rectangle((int(cx-180*s),int(cy-30*s),int(cx+180*s),int(cy+260*s)),radius=int(90*s),fill=(69,173,220),outline=(245,245,255),width=6)
        if subject=="heart":
            d.polygon([(cx,cy+120*s),(cx-100*s,cy+25*s),(cx-95*s,cy-45*s),(cx,cy-15*s),(cx+95*s,cy-45*s),(cx+100*s,cy+25*s)],fill=(245,80,100))
    elif subject=="door":
        d.rounded_rectangle((cx-155,cy-250,cx+155,cy+260),radius=20,fill=(177,104,54),outline=(255,220,165),width=12)
        d.ellipse((cx+90,cy+5,cx+120,cy+35),fill=(255,215,80))
    elif subject=="magnifier":
        d.ellipse((cx-170,cy-190,cx+120,cy+100),outline=(255,225,130),width=35)
        d.line((cx+90,cy+65,cx+250,cy+235),fill=(255,225,130),width=45)
    elif subject=="planet":
        ell((cx-175,cy-175,cx+175,cy+175),(90,170,230))
        d.ellipse((cx-260,cy-70,cx+260,cy+70),outline=(245,210,130),width=25)
    elif subject=="atom":
        for angle in (0,60,120):
            d.ellipse((cx-220,cy-90,cx+220,cy+90),outline=(255,220,120),width=14)
        ell((cx-35,cy-35,cx+35,cy+35),(255,125,100))
    elif subject=="book":
        d.rounded_rectangle((cx-220,cy-180,cx,cy+190),radius=20,fill=(240,185,90),outline="white",width=10)
        d.rounded_rectangle((cx,cy-180,cx+220,cy+190),radius=20,fill=(250,215,145),outline="white",width=10)
        d.line((cx,cy-170,cx,cy+180),fill=(120,70,40),width=12)
    else:
        ell((cx-150,cy-150,cx+150,cy+150),(105,190,210))

def make_scene(scene, idx, total, title):
    im=gradient_bg(idx)
    d=ImageDraw.Draw(im)
    # soft decorative depth layers
    d.ellipse((760,-150,1250,340),fill=(255,255,255,18))
    d.ellipse((-180,1430,300,1910),fill=(255,255,255,18))
    d.rounded_rectangle((70,90,1010,110),radius=10,fill=(100,115,145))
    d.rounded_rectangle((70,90,70+940*(idx+1)/total,110),radius=10,fill=(255,210,65))
    d.text((75,155),f"FACT FILE  •  {idx+1:02d}",font=get_font(34,True),fill=(255,220,110))
    subject=scene.get("visual_subject","generic").lower()
    draw_subject(d,subject,540,760,1.15)
    text=(scene.get("screen_text","") or "").upper()
    f=get_font(66,True)
    words=text.split(); lines=[]; line=""
    for w in words:
        trial=(line+" "+w).strip()
        if d.textbbox((0,0),trial,font=f)[2] < 900: line=trial
        else: lines.append(line); line=w
    if line: lines.append(line)
    y=1240-(len(lines)*90)//2
    for line in lines:
        box=d.textbbox((0,0),line,font=f); tw=box[2]-box[0]
        d.text(((W-tw)//2,y),line,font=f,fill="white",stroke_width=2,stroke_fill=(10,15,30))
        y+=92
    note=scene.get("visual_note","")
    nf=get_font(29)
    note_words=note.split(); note_lines=[]; line=""
    for w in note_words:
        trial=(line+" "+w).strip()
        if d.textbbox((0,0),trial,font=nf)[2] < 900: line=trial
        else: note_lines.append(line); line=w
    if line: note_lines.append(line)
    for j,line in enumerate(note_lines[:2]):
        box=d.textbbox((0,0),line,font=nf); tw=box[2]-box[0]
        d.text(((W-tw)//2,1580+j*42),line,font=nf,fill=(235,240,250))
    d.text((75,1810),"SCIENCE • PSYCHOLOGY • DISCOVERY",font=get_font(25,True),fill=(255,220,110))
    return im

def ass_time(seconds):
    cs=int(round(seconds*100))
    h=cs//360000; m=(cs%360000)//6000; s=(cs%6000)//100
    return f"{h}:{m:02d}:{s:02d}.{cs%100:02d}"

def make_karaoke_ass(words, total_duration, path):
    # Approximate word timing distributed by character count. This is karaoke-style,
    # not forced alignment; word timing can drift slightly from the spoken audio.
    weights=[max(1,len(w.strip(".,!?;:"))) for w in words]
    total=sum(weights) or 1
    cursor=0.35
    usable=max(1,total_duration-0.65)
    events=[]
    for i,w in enumerate(words):
        dur=usable*weights[i]/total
        # ASS karaoke centiseconds; yellow active word, white upcoming words.
        events.append(f"{{\\k{max(1,int(dur*100))}}}{w}")
        cursor+=dur
    header="""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,DejaVu Sans,62,&H0000D7FF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,5,2,2,80,80,260,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # break into manageable chunks of about 7 words for screen readability
    lines=[]
    for i in range(0,len(events),7):
        chunk=events[i:i+7]
        start=0.35+usable*sum(weights[:i])/total
        end=0.35+usable*sum(weights[:i+len(chunk)])/total
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Karaoke,,0,0,0,,{' '.join(chunk)}")
    Path(path).write_text(header+"\n".join(lines),encoding="utf-8")

def main():
    obj=gemini_script()
    (OUT/"metadata.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"script.txt").write_text(obj["narration"],encoding="utf-8")
    (OUT/"review_checklist.txt").write_text(
        "Review factual claims and pronunciation. Captions use estimated word timing, so check sync. "
        "Visuals are original faux-3D vector cartoon illustrations, not AI-generated 3D renders. "
        "Approve manually before uploading.\n",encoding="utf-8")
    narration=obj["narration"]
    (OUT/"narration.txt").write_text(narration,encoding="utf-8")
    voice=os.getenv("ESPEAK_VOICE","en-us")
    run(["espeak-ng","-v",voice,"-s","150","-w",str(OUT/"voice.wav"),narration])
    dur=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(OUT/"voice.wav")],text=True).strip())
    scenes=obj["scenes"]
    per=dur/len(scenes)
    concat=OUT/"slides.txt"
    with concat.open("w") as f:
        for i,scene in enumerate(scenes):
            p=OUT/f"scene_{i:02d}.png"
            make_scene(scene,i,len(scenes),obj["title"]).save(p)
            f.write(f"file '{p.resolve()}'\n")
            f.write(f"duration {per:.3f}\n")
        f.write(f"file '{(OUT/'scene_05.png').resolve()}'\n")
    silent=OUT/"silent.mp4"
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-vf","scale=1080:1920,format=yuv420p","-r","30","-c:v","libx264","-preset","veryfast","-crf","22",str(silent)])
    words=narration.split()
    ass=OUT/"captions.ass"
    make_karaoke_ass(words,dur,ass)
    final=OUT/"SHORT_REVIEW_ME.mp4"
    run(["ffmpeg","-y","-i",str(silent),"-i",str(OUT/"voice.wav"),"-vf",f"ass={ass}","-c:v","libx264","-preset","veryfast","-crf","22","-c:a","aac","-b:a","160k","-shortest","-movflags","+faststart",str(final)])
    print(f"Created upgraded draft: {final}")

if __name__=="__main__":
    main()
