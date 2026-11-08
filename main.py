import os, json, subprocess, re, math, random
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path("output")
OUT.mkdir(exist_ok=True)
W, H = 720, 1280
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
VOICE = os.getenv("ESPEAK_VOICE", "en-us")
RATE = int(os.getenv("ESPEAK_RATE", "142"))

def run(cmd):
    subprocess.run(cmd, check=True)

def font(size, bold=False):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if Path(p).exists(): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def gemini_script():
    key = os.environ["GEMINI_API_KEY"]
    topic = os.getenv("CHANNEL_TOPIC", "science, human psychology and unusual facts")
    lang = os.getenv("VIDEO_LANGUAGE", "English")
    prompt = f"""
Create one original, accurate YouTube Short about {topic}.
Language: {lang}. Spoken duration must be 35-45 seconds, approximately 85-100 words.
Return ONLY valid JSON with:
title, description, scenes.
scenes must contain exactly 6 objects. Each object must have:
narration (a natural spoken sentence or two, 12-18 words),
screen_text (2-5 short words),
visual_type (one of: character, anatomy, science_diagram, object, environment, data_visual),
visual_note (specific visual direction, 8-18 words),
labels (array of 0-2 short factual labels).
Make one coherent story with a hook in scene 1, progressive explanation in scenes 2-5,
and a satisfying conclusion in scene 6. Avoid fabricated statistics, fake quotations,
medical advice, and claims that need current data. Keep labels short and factual.
"""
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    r=requests.post(url,params={"key":key},
        json={"contents":[{"parts":[{"text":prompt}]}],
              "generationConfig":{"temperature":0.65,"responseMimeType":"application/json"}},
        timeout=90)
    if r.status_code == 404:
        raise RuntimeError(f"Gemini model '{MODEL}' returned 404. Keep the model that worked in your previous run, or set repository variable GEMINI_MODEL to a currently available generateContent model. Details: {r.text[:400]}")
    r.raise_for_status()
    data=json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    scenes=data.get("scenes",[])
    if len(scenes)!=6 or any(not s.get("narration") for s in scenes):
        raise ValueError("Gemini did not return six complete narration scenes. Run again.")
    words=" ".join(s["narration"] for s in scenes).split()
    if not 78 <= len(words) <= 110:
        raise ValueError(f"Script length was {len(words)} words, outside the 78-110 word quality range. Run again.")
    return data

def vertical_gradient(seed):
    palettes=[((7,18,42),(35,68,112)),((20,18,44),(70,42,90)),((5,35,43),(20,91,94)),
              ((38,24,20),(108,62,38)),((13,27,52),(42,80,125)),((35,18,38),(91,42,68))]
    a,b=palettes[seed%len(palettes)]
    im=Image.new("RGB",(W,H)); px=im.load()
    for y in range(H):
        t=y/(H-1)
        c=tuple(int(a[k]*(1-t)+b[k]*t) for k in range(3))
        for x in range(W): px[x,y]=c
    return im

def sphere(draw, box, base, highlight=(255,255,255), outline=None):
    x1,y1,x2,y2=map(int,box)
    # layered radial-style shading approximated with nested ellipses
    draw.ellipse((x1+12,y1+20,x2+12,y2+20),fill=(5,9,22))
    draw.ellipse((x1,y1,x2,y2),fill=base,outline=outline or (225,237,255),width=3)
    w=x2-x1; h=y2-y1
    draw.ellipse((x1+w*.13,y1+h*.08,x1+w*.48,y1+h*.35),fill=highlight)
    draw.arc((x1+w*.08,y1+h*.05,x2-w*.06,y2-h*.06),190,305,fill=(255,255,255),width=4)

def draw_character(d,cx,cy,pose=0):
    # Recurring small guide character, with dimensional shading and simple expression
    sphere(d,(cx-70,cy-110,cx+70,cy+30),(244,177,126),(255,222,185))
    # hair cap
    d.pieslice((cx-74,cy-124,cx+74,cy+5),180,350,fill=(38,28,30))
    # eyes and smile
    d.ellipse((cx-34,cy-40,cx-18,cy-22),fill=(25,30,42))
    d.ellipse((cx+18,cy-40,cx+34,cy-22),fill=(25,30,42))
    d.arc((cx-25,cy-10,cx+25,cy+18),5,170,fill=(120,45,48),width=4)
    # torso, arms and legs
    d.rounded_rectangle((cx-83,cy+25,cx+83,cy+225),radius=48,fill=(47,164,211),outline=(230,245,255),width=4)
    d.line((cx-65,cy+65,cx-140,cy+135+pose),fill=(244,177,126),width=25)
    d.line((cx+65,cy+65,cx+140,cy+105-pose),fill=(244,177,126),width=25)
    d.line((cx-35,cy+210,cx-55,cy+295),fill=(30,40,72),width=30)
    d.line((cx+35,cy+210,cx+55,cy+295),fill=(30,40,72),width=30)

def draw_brain(d,cx,cy):
    sphere(d,(cx-145,cy-105,cx+145,cy+105),(218,94,130),(255,182,192))
    for dx,dy in [(-70,-25),(-20,-55),(45,-45),(82,20),(10,48),(-78,38)]:
        d.arc((cx+dx-45,cy+dy-35,cx+dx+45,cy+dy+35),0,300,fill=(255,220,225),width=7)
    d.line((cx,cy-75,cx,cy+75),fill=(140,52,90),width=5)

def draw_neuron(d,cx,cy):
    sphere(d,(cx-35,cy-35,cx+35,cy+35),(245,181,80))
    for ang in range(0,360,45):
        x2=cx+int(190*math.cos(math.radians(ang))); y2=cy+int(145*math.sin(math.radians(ang)))
        d.line((cx,cy,x2,y2),fill=(120,225,230),width=8)
        d.ellipse((x2-13,y2-13,x2+13,y2+13),fill=(255,215,100))
    d.arc((cx-250,cy-180,cx+250,cy+180),15,340,fill=(210,240,255),width=3)

def draw_diagram(d,cx,cy,kind):
    if kind=="data_visual":
        # clean conceptual bar chart, no invented numerical values
        d.line((cx-210,cy+150,cx+210,cy+150),fill=(235,245,255),width=5)
        heights=[95,165,245,310]
        for i,h in enumerate(heights):
            x=cx-170+i*105
            d.rounded_rectangle((x,cy+150-h,x+58,cy+150),radius=12,fill=[(65,190,220),(255,194,75),(160,130,235),(90,210,160)][i])
    elif kind=="anatomy":
        draw_brain(d,cx,cy)
    else:
        # connected concept nodes
        pts=[(cx-150,cy-90),(cx+145,cy-100),(cx,cy+130)]
        d.line((pts[0],pts[1],pts[2],pts[0]),fill=(150,220,245),width=8)
        for i,p in enumerate(pts):
            sphere(d,(p[0]-45,p[1]-45,p[0]+45,p[1]+45),[(80,180,220),(245,160,90),(155,130,225)][i])

def draw_object(d,cx,cy):
    # magnifier plus a floating object for the "investigation" visual
    d.ellipse((cx-170,cy-170,cx+90,cy+90),outline=(255,222,130),width=24)
    d.line((cx+65,cy+65,cx+210,cy+210),fill=(255,222,130),width=34)
    sphere(d,(cx-75,cy-75,cx+5,cy+5),(105,200,220))

def draw_environment(d,cx,cy):
    # layered planet / horizon
    sphere(d,(cx-160,cy-160,cx+160,cy+160),(68,154,208),(190,235,255))
    d.arc((cx-235,cy-70,cx+235,cy+70),185,350,fill=(255,215,130),width=20)
    d.ellipse((cx+180,cy-190,cx+215,cy-155),fill=(255,220,130))
    for x,y in [(cx-230,cy-200),(cx+235,cy+130),(cx-260,cy+100)]:
        d.ellipse((x-5,y-5,x+5,y+5),fill="white")

def draw_scene(scene,index):
    im=vertical_gradient(index)
    d=ImageDraw.Draw(im)
    # background depth rings and subtle grid
    for rad in (260,360,470):
        d.arc((W//2-rad,420-rad,W//2+rad,420+rad),195,345,fill=(70,105,150),width=2)
    d.rounded_rectangle((45,58,675,66),radius=5,fill=(70,90,125))
    d.rounded_rectangle((45,58,45+630*(index+1)/6,66),radius=5,fill=(255,211,75))
    d.text((48,92),f"FIELD NOTES  /  {index+1:02d}",font=font(22,True),fill=(255,220,125))
    kind=scene.get("visual_type","science_diagram")
    if kind=="character":
        draw_character(d,360,390,index%3*9)
        draw_brain(d,360,900)
    elif kind=="anatomy":
        draw_brain(d,360,650)
        draw_character(d,540,960,8)
    elif kind=="object":
        draw_object(d,350,650)
        draw_character(d,525,950,5)
    elif kind=="environment":
        draw_environment(d,360,650)
        draw_character(d,525,950,0)
    elif kind=="data_visual":
        draw_diagram(d,360,660,"data_visual")
        draw_character(d,525,950,0)
    else:
        draw_diagram(d,360,650,"science_diagram")
        draw_character(d,525,950,0)
    # scene heading, concise and separate from captions
    headline=(scene.get("screen_text","") or "").upper()
    f=font(43,True)
    bb=d.textbbox((0,0),headline,font=f); tw=bb[2]-bb[0]
    if tw>620:
        f=font(34,True); bb=d.textbbox((0,0),headline,font=f); tw=bb[2]-bb[0]
    d.rounded_rectangle((35,1010,685,1100),radius=22,fill=(8,15,32))
    d.text(((W-tw)//2,1027),headline,font=f,fill=(255,255,255))
    # labels are deliberately tiny and sparse, above caption safe area
    labels=scene.get("labels",[])[:2]
    if labels:
        label="  •  ".join(str(x)[:22] for x in labels)
        lf=font(17,True); bb=d.textbbox((0,0),label,font=lf); lw=bb[2]-bb[0]
        d.text(((W-lw)//2,1120),label,font=lf,fill=(180,220,240))
    return im

def ass_time(t):
    cs=max(0,int(round(t*100)))
    return f"{cs//360000}:{(cs%360000)//6000:02d}:{(cs%6000)//100:02d}.{cs%100:02d}"

def make_karaoke_ass(scene_words,scene_durations,path):
    head="""[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,DejaVu Sans,42,&H0000D7FF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,35,35,95,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines=[]; offset=0.0
    for words,dur in zip(scene_words,scene_durations):
        weights=[max(1,len(w.strip(".,!?;:"))) for w in words]
        total=sum(weights) or 1
        usable=max(0.5,dur-0.15)
        # 5 words max per subtitle event for a clean two-line reading block
        for i in range(0,len(words),5):
            chunk=words[i:i+5]
            start=offset+0.08+usable*sum(weights[:i])/total
            end=offset+0.08+usable*sum(weights[:i+len(chunk)])/total
            karaoke=[]
            for w in chunk:
                idx=words.index(w) if False else None
                weight=max(1,len(w.strip(".,!?;:")))
                karaoke.append(f"{{\\k{max(1,int(usable*weight/total*100))}}}{w}")
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Karaoke,,0,0,0,,{' '.join(karaoke)}")
        offset+=dur
    Path(path).write_text(head+"\n".join(lines),encoding="utf-8")

def main():
    obj=gemini_script()
    scenes=obj["scenes"]
    narrations=[s["narration"].strip() for s in scenes]
    (OUT/"metadata.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"script.txt").write_text("\n\n".join(narrations),encoding="utf-8")
    (OUT/"review_checklist.txt").write_text(
        "PRE-PUBLISH REVIEW\n"
        "1. Verify factual claims and pronunciation.\n"
        "2. Check the estimated word-by-word captions against the narration.\n"
        "3. Confirm all six scenes tell one coherent story.\n"
        "4. This is hybrid 2.5D motion graphics: illustrated cartoon guide + schematic science visuals + camera movement. It is not generated full 3D character animation.\n"
        "5. Upload manually only after approval.\n",encoding="utf-8")
    scene_words=[]; durations=[]; audio_files=[]
    for i,text in enumerate(narrations):
        wav=OUT/f"voice_{i:02d}.wav"
        subprocess.run(["espeak-ng","-v",VOICE,"-s",str(RATE),"-w",str(wav),text],check=True)
        dur=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(wav)],text=True).strip())
        durations.append(dur); audio_files.append(wav); scene_words.append(text.split())
    total=sum(durations)
    if total<35 or total>45:
        raise RuntimeError(f"Generated narration is {total:.1f} seconds, outside the 35-45 second target. Run the workflow again; if repeated, adjust ESPEAK_RATE or the script length.")
    # Per-scene motion clip: slow push-in / drift, varied direction to avoid slideshow feel.
    video_parts=[]
    for i,(scene,dur) in enumerate(zip(scenes,durations)):
        still=OUT/f"scene_{i:02d}.png"
        draw_scene(scene,i).save(still)
        clip=OUT/f"motion_{i:02d}.mp4"
        frames=max(2,int(math.ceil(dur*30)))
        zoom="min(zoom+0.0008,1.12)" if i%2==0 else "max(zoom-0.00035,1.0)"
        x="iw/2-(iw/zoom/2)+8*sin(on/35)" if i%2==0 else "iw/2-(iw/zoom/2)-8*sin(on/35)"
        y="ih/2-(ih/zoom/2)+5*cos(on/40)"
        vf=f"scale=900:1600,zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s=720x1280:fps=30,trim=duration={dur:.3f},setpts=PTS-STARTPTS,format=yuv420p"
        run(["ffmpeg","-y","-loop","1","-i",str(still),"-vf",vf,"-t",f"{dur:.3f}","-r","30","-an","-c:v","libx264","-preset","veryfast","-crf","22",str(clip)])
        video_parts.append(clip)
    concat=OUT/"videos.txt"
    concat.write_text("".join(f"file '{p.resolve()}'\n" for p in video_parts),encoding="utf-8")
    silent=OUT/"picture.mp4"
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-c","copy",str(silent)])
    audio_list=OUT/"audio.txt"
    audio_list.write_text("".join(f"file '{p.resolve()}'\n" for p in audio_files),encoding="utf-8")
    voice=OUT/"voice.wav"
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(audio_list),"-c","copy",str(voice)])
    ass=OUT/"captions.ass"
    make_karaoke_ass(scene_words,durations,ass)
    final=OUT/"SHORT_REVIEW_ME.mp4"
    run(["ffmpeg","-y","-i",str(silent),"-i",str(voice),"-vf",f"ass={ass}","-c:v","libx264","-preset","veryfast","-crf","22","-c:a","aac","-b:a","160k","-shortest","-movflags","+faststart",str(final)])
    print(f"Created hybrid animated draft: {final} ({total:.1f}s)")

if __name__=="__main__":
    main()
