import os, json, subprocess, re, math, random
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path("output")
OUT.mkdir(exist_ok=True)
W, H = 720, 1280
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
TTS_VOICE = os.getenv("KOKORO_VOICE", "am_michael")
TTS_MODEL = os.getenv("KOKORO_MODEL_PATH", "models/kokoro-v1.0.onnx")
TTS_VOICES = os.getenv("KOKORO_VOICES_PATH", "models/voices-v1.0.bin")

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
    raw_text=r.json()["candidates"][0]["content"]["parts"][0]["text"]
    try:
        data=json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini returned invalid JSON: {exc}. Response preview: {raw_text[:500]}") from exc

    # Gemini may occasionally return the six scene objects as a top-level
    # JSON array instead of the requested object containing a `scenes` key.
    # Normalize both valid shapes into one consistent structure.
    if isinstance(data, list):
        scenes=data
        data={"title": "Science, psychology and unusual facts", "description": "", "scenes": scenes}
    elif isinstance(data, dict):
        scenes=data.get("scenes", [])
        # Some model responses wrap the object one level deeper.
        if not scenes and isinstance(data.get("data"), dict):
            scenes=data["data"].get("scenes", [])
            if scenes:
                data.update(data["data"])
                data["scenes"]=scenes
    else:
        raise ValueError(f"Gemini returned {type(data).__name__}, expected a JSON object or scene array.")

    if not isinstance(scenes, list) or len(scenes)!=6:
        raise ValueError(f"Gemini must return exactly six scenes; received {len(scenes) if isinstance(scenes, list) else 'a non-list value'}.")
    if any(not isinstance(scene, dict) or not isinstance(scene.get("narration"), str) or not scene["narration"].strip() for scene in scenes):
        raise ValueError("Gemini returned six scenes, but at least one scene is missing valid narration text.")
    data["scenes"]=scenes
    words=" ".join(s["narration"] for s in scenes).split()
    # Gemini may return a slightly shorter or longer script than requested.
    # Audio duration is measured and corrected later by adaptive speech-rate logic,
    # so use a broad safety range here instead of failing on minor word-count drift.
    if not 60 <= len(words) <= 130:
        raise ValueError(f"Script length was {len(words)} words, outside the 60-130 word safety range. Check the generated script.")
    return data

_BG_CACHE = {}

def vertical_gradient(seed):
    if seed in _BG_CACHE:
        return _BG_CACHE[seed].copy()
    palettes=[((7,18,42),(35,68,112)),((20,18,44),(70,42,90)),((5,35,43),(20,91,94)),
              ((38,24,20),(108,62,38)),((13,27,52),(42,80,125)),((35,18,38),(91,42,68))]
    a,b=palettes[seed%len(palettes)]
    im=Image.new("RGB",(W,H)); px=im.load()
    for y in range(H):
        t=y/(H-1)
        c=tuple(int(a[k]*(1-t)+b[k]*t) for k in range(3))
        for x in range(W): px[x,y]=c
    _BG_CACHE[seed] = im.copy()
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
    # Alternating gestures and small leg swings create visible character acting.
    left_hand=(cx-140,cy+115+pose)
    right_hand=(cx+140,cy+105-pose)
    d.line((cx-65,cy+65,left_hand[0],left_hand[1]),fill=(244,177,126),width=25)
    d.line((cx+65,cy+65,right_hand[0],right_hand[1]),fill=(244,177,126),width=25)
    d.ellipse((left_hand[0]-13,left_hand[1]-13,left_hand[0]+13,left_hand[1]+13),fill=(255,205,160))
    d.ellipse((right_hand[0]-13,right_hand[1]-13,right_hand[0]+13,right_hand[1]+13),fill=(255,205,160))
    swing=int(pose*0.22)
    d.line((cx-35,cy+210,cx-55+swing,cy+295),fill=(30,40,72),width=30)
    d.line((cx+35,cy+210,cx+55-swing,cy+295),fill=(30,40,72),width=30)

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


def draw_heart(d,cx,cy,scale=1.0):
    # Stylised anatomical heart built from layered vector forms.
    r=int(95*scale)
    d.line((cx-28*scale,cy-75*scale,cx-42*scale,cy-150*scale),fill=(225,90,110),width=max(8,int(24*scale)))
    d.line((cx+30*scale,cy-70*scale,cx+75*scale,cy-145*scale),fill=(245,125,115),width=max(8,int(22*scale)))
    d.ellipse((cx-r,cy-r//2,cx+8*scale,cy+r),fill=(180,48,85),outline=(255,185,190),width=4)
    d.ellipse((cx-8*scale,cy-r//2,cx+r,cy+r),fill=(215,65,95),outline=(255,185,190),width=4)
    d.polygon([(cx-r,cy),(cx+r,cy),(cx,cy+int(1.45*r))],fill=(195,48,83))
    d.arc((cx-r//2,cy-r//3,cx+r//2,cy+r//2),190,300,fill=(255,190,195),width=5)

def draw_eye(d,cx,cy,scale=1.0):
    w=int(210*scale); h=int(115*scale)
    d.ellipse((cx-w,cy-h,cx+w,cy+h),fill=(225,238,245),outline=(105,210,230),width=8)
    d.ellipse((cx-int(78*scale),cy-int(78*scale),cx+int(78*scale),cy+int(78*scale)),fill=(55,150,180))
    d.ellipse((cx-int(34*scale),cy-int(34*scale),cx+int(34*scale),cy+int(34*scale)),fill=(8,22,42))
    d.ellipse((cx-int(20*scale),cy-int(48*scale),cx+int(2*scale),cy-int(26*scale)),fill="white")
    d.arc((cx-w,cy-h,cx+w,cy+h),190,350,fill=(255,255,255),width=5)

def draw_clock(d,cx,cy,scale=1.0):
    r=int(155*scale)
    d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(19,43,75),outline=(120,210,235),width=9)
    for a in range(0,360,30):
        x1=cx+int((r-18)*math.cos(math.radians(a))); y1=cy+int((r-18)*math.sin(math.radians(a)))
        x2=cx+int((r-35)*math.cos(math.radians(a))); y2=cy+int((r-35)*math.sin(math.radians(a)))
        d.line((x1,y1,x2,y2),fill=(225,240,250),width=5)
    d.line((cx,cy,cx-int(45*scale),cy-int(90*scale)),fill=(255,210,105),width=10)
    d.line((cx,cy,cx+int(90*scale),cy+int(35*scale)),fill=(255,210,105),width=8)
    d.ellipse((cx-12,cy-12,cx+12,cy+12),fill="white")

def draw_dna(d,cx,cy,scale=1.0):
    pts1=[]; pts2=[]
    for i in range(13):
        y=cy-int(230*scale)+int(i*38*scale)
        x=cx+int(95*scale*math.sin(i*math.pi/3))
        x2=cx-int(95*scale*math.sin(i*math.pi/3))
        pts1.append((x,y)); pts2.append((x2,y))
        d.line((x,y,x2,y),fill=(245,190,105),width=5)
        d.ellipse((x-10,y-10,x+10,y+10),fill=(95,210,230))
        d.ellipse((x2-10,y-10,x2+10,y+10),fill=(190,140,235))
    d.line(pts1,fill=(100,215,235),width=12)
    d.line(pts2,fill=(205,150,235),width=12)

def draw_atom(d,cx,cy,scale=1.0):
    for angle in (0,60,120):
        box=(cx-int(210*scale),cy-int(85*scale),cx+int(210*scale),cy+int(85*scale))
        layer=Image.new("RGBA",(W,H),(0,0,0,0)); ld=ImageDraw.Draw(layer)
        ld.ellipse(box,outline=(95,215,240,230),width=7)
        layer=layer.rotate(angle,resample=Image.Resampling.BICUBIC,center=(cx,cy))
        # Composite onto the RGB canvas without changing its mode.
        d._image.paste(layer,(0,0),layer)
    d.ellipse((cx-34,cy-34,cx+34,cy+34),fill=(255,205,100),outline="white",width=4)

def scene_motif(d,scene,index,cx,cy,phase):
    words=(" ".join(str(scene.get(k,"")) for k in ("screen_text","visual_note","narration"))).lower()
    kind=scene.get("visual_type","science_diagram")
    # Semantic cues select a concrete visual; index fallback guarantees variety.
    if any(k in words for k in ("brain","memory","thought","mind","psych","neuron","decision","emotion","fear","attention")):
        draw_brain(d,cx,cy)
        motif="BRAIN / NEURAL ACTIVITY"
    elif any(k in words for k in ("heart","blood","pulse","cardiac")):
        draw_heart(d,cx,cy,1.0); motif="CARDIOVASCULAR SYSTEM"
    elif any(k in words for k in ("eye","vision","visual","see","light","blind")):
        draw_eye(d,cx,cy,0.9); motif="VISION / PERCEPTION"
    elif any(k in words for k in ("time","clock","sleep","circadian","rhythm")):
        draw_clock(d,cx,cy,0.9); motif="BIOLOGICAL RHYTHM"
    elif any(k in words for k in ("dna","gene","genetic","cell","evolution")):
        draw_dna(d,cx,cy,0.9); motif="GENETIC INFORMATION"
    elif any(k in words for k in ("atom","quantum","particle","molecule","physics","energy")):
        draw_atom(d,cx,cy,0.8); motif="PHYSICAL SYSTEM"
    elif kind=="anatomy":
        draw_brain(d,cx,cy); motif="ANATOMICAL DETAIL"
    elif kind=="data_visual":
        draw_diagram(d,cx,cy,"data_visual"); motif="PATTERN / DATA"
    elif kind=="environment":
        draw_environment(d,cx,cy); motif="NATURAL SYSTEM"
    elif kind=="object":
        draw_object(d,cx,cy); motif="OBJECT / EVIDENCE"
    else:
        choices=[draw_neuron,draw_diagram,draw_environment,draw_object]
        if index % 4 == 0:
            draw_neuron(d,cx,cy); motif="CONNECTED NETWORK"
        elif index % 4 == 1:
            draw_diagram(d,cx,cy,"science_diagram"); motif="SYSTEM MAP"
        elif index % 4 == 2:
            draw_environment(d,cx,cy); motif="ENVIRONMENT"
        else:
            draw_object(d,cx,cy); motif="OBSERVATION"
    # Small moving highlight to make the illustration feel active.
    pulse=13+int(8*(0.5+0.5*math.sin(phase*2*math.pi)))
    d.ellipse((cx-pulse*3,cy-pulse*3,cx+pulse*3,cy+pulse*3),outline=(255,220,130),width=3)
    return motif

def draw_scene(scene,index,phase=0.0):
    im=vertical_gradient(index)
    d=ImageDraw.Draw(im)
    # Cinematic technical backdrop: subtle grid, orbital rings and moving particles.
    drift=int(22*math.sin(phase*2*math.pi))
    for rad in (245,345,455):
        d.arc((W//2-rad+drift,470-rad,W//2+rad+drift,470+rad),195,345,fill=(65,105,150),width=2)
    for x in range(28,W,58):
        d.line((x,130,x,940),fill=(55,85,120),width=1)
    for y in range(150,950,58):
        d.line((25,y,695,y),fill=(55,85,120),width=1)
    for j in range(12):
        px=int((j*79+phase*210+index*43)%W)
        py=int((j*113+phase*125+index*67)%940)
        rr=2+(j%3)
        d.ellipse((px-rr,py-rr,px+rr,py+rr),fill=(125,210,235))
    # Progress indicator and editorial header.
    d.rounded_rectangle((38,48,682,56),radius=5,fill=(65,85,115))
    d.rounded_rectangle((38,48,38+644*(index+1)/6,56),radius=5,fill=(255,211,75))
    d.text((42,76),f"FIELD NOTES  /  {index+1:02d}",font=font(20,True),fill=(255,220,125))

    # Hero illustration changes position and scale across scenes.
    layouts=[(360,425,0.92),(360,475,0.82),(360,430,0.95),
             (360,475,0.84),(360,420,0.92),(360,430,0.90)]
    cx,cy,scale=layouts[index%len(layouts)]
    # Soft halo behind the subject.
    halo=Image.new("RGBA",(W,H),(0,0,0,0)); hd=ImageDraw.Draw(halo)
    hr=int(245*scale)
    hd.ellipse((cx-hr,cy-hr,cx+hr,cy+hr),fill=(55,145,195,32))
    halo=halo.filter(ImageFilter.GaussianBlur(32))
    im=Image.alpha_composite(im.convert("RGBA"),halo).convert("RGB")
    d=ImageDraw.Draw(im)
    motif=scene_motif(d,scene,index,cx,cy,phase)

    # Character is now a guide, not a repeated decoration in every scene.
    if index in (0,5) or scene.get("visual_type")=="character":
        pose=int(35*math.sin(phase*2*math.pi))
        draw_character(d,570,790+int(8*math.sin(phase*2*math.pi)),pose)

    # Distinct scene title panel and short factual labels from Gemini.
    headline=(scene.get("screen_text","") or "").upper()
    f=font(42,True)
    bb=d.textbbox((0,0),headline,font=f); tw=bb[2]-bb[0]
    if tw>620:
        f=font(33,True); bb=d.textbbox((0,0),headline,font=f); tw=bb[2]-bb[0]
    d.rounded_rectangle((30,890,690,1000),radius=24,fill=(7,15,31),outline=(75,125,160),width=2)
    d.text(((W-tw)//2,915),headline,font=f,fill=(255,255,255))
    d.text((42,1020),motif,font=font(17,True),fill=(115,215,230))

    labels=scene.get("labels",[])
    if isinstance(labels,list) and labels:
        label_text="   •   ".join(str(x)[:28] for x in labels[:2])
        d.rounded_rectangle((38,1060,682,1120),radius=16,fill=(17,32,53),outline=(70,105,140),width=1)
        d.text((56,1078),label_text,font=font(19,True),fill=(225,235,245))

    # Scene-specific visual direction is retained as a small editorial cue.
    note=str(scene.get("visual_note","")).strip()
    if note:
        note=re.sub(r"\s+"," ",note)
        if len(note)>66: note=note[:63].rstrip()+"..."
        d.text((42,1160),note,font=font(15),fill=(165,190,210))
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


# --- Cinematic photo-based scene renderer (free Wikimedia Commons assets) ---
IMAGE_CACHE = Path("output/visual_assets")
IMAGE_CACHE.mkdir(parents=True, exist_ok=True)

def fetch_scene_image(scene, index):
    """Find a freely licensed Wikimedia Commons image; cache it for this run."""
    target = IMAGE_CACHE / f"scene_{index:02d}.jpg"
    if target.exists() and target.stat().st_size > 15000:
        return target
    raw = " ".join(str(scene.get(k, "")) for k in ("visual_note", "screen_text", "narration"))
    # Search using the visual direction first; avoid long full-sentence queries.
    terms = re.findall(r"[A-Za-z]{4,}", raw)
    stop = {"with", "from", "that", "this", "when", "where", "your", "into", "over", "under", "their", "they", "them", "scene", "show", "shows", "visual", "image", "close", "camera", "dramatic"}
    query = " ".join([w for w in terms if w.lower() not in stop][:7]) or "science" 
    try:
        api = "https://commons.wikimedia.org/w/api.php"
        params = {"action":"query", "generator":"search", "gsrsearch":f'filetype:bitmap {query}',
                  "gsrnamespace":6, "gsrlimit":8, "prop":"imageinfo", "iiprop":"url|extmetadata",
                  "iiurlwidth":1400, "format":"json"}
        response = requests.get(api, params=params, headers={"User-Agent":"DailyShortsDraftBot/1.0 (educational video project)"}, timeout=25)
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        candidates=[]
        for page in pages.values():
            info=(page.get("imageinfo") or [{}])[0]
            meta=info.get("extmetadata", {})
            mime=info.get("mime", "")
            url=info.get("thumburl") or info.get("url")
            if url and mime.startswith("image/"):
                # Commons files carry their own license metadata; save attribution for review.
                candidates.append((url, page.get("title", ""), meta.get("LicenseShortName", {}).get("value", "Unknown"), meta.get("Artist", {}).get("value", "Unknown"), meta.get("Credit", {}).get("value", "")))
        for url, title, license_name, artist, credit in candidates:
            try:
                img=requests.get(url, headers={"User-Agent":"DailyShortsDraftBot/1.0"}, timeout=30)
                img.raise_for_status()
                from io import BytesIO
                im=Image.open(BytesIO(img.content)).convert("RGB")
                if im.width >= 500 and im.height >= 500:
                    im.save(target, "JPEG", quality=92)
                    with (IMAGE_CACHE / "ATTRIBUTION.txt").open("a", encoding="utf-8") as f:
                        f.write(f"Scene {index+1}: {title}\nLicense: {license_name}\nCreator: {artist}\nCredit: {re.sub('<[^>]+>', '', str(credit))}\nSource: {url}\n\n")
                    return target
            except Exception:
                continue
    except Exception as e:
        print(f"Wikimedia image search failed for scene {index+1}: {e}")
    return None

def cinematic_scene(scene, index, phase=0.0):
    """Full-bleed photo, cinematic grade, restrained editorial typography."""
    path=fetch_scene_image(scene,index)
    if path:
        src=Image.open(path).convert("RGB")
        sw,sh=src.size
        scale=max(W/sw,H/sh)
        src=src.resize((int(sw*scale),int(sh*scale)),Image.Resampling.LANCZOS)
        # Gentle per-frame drift creates motion without distorting the photograph.
        maxx=max(0,src.width-W); maxy=max(0,src.height-H)
        x=int(maxx*(0.35+0.30*phase)); y=int(maxy*(0.40+0.20*math.sin(phase*math.pi)))
        im=src.crop((x,y,x+W,y+H)).convert("RGBA")
    else:
        # Explicit fallback: atmospheric dark background, not a misleading unrelated stock image.
        im=vertical_gradient(index).convert("RGBA")
    # Dark cinematic grade + top/bottom gradients for legible text.
    shade=Image.new("RGBA",(W,H),(3,8,18,72))
    im=Image.alpha_composite(im,shade)
    grad=Image.new("RGBA",(W,H),(0,0,0,0)); gp=grad.load()
    for yy in range(H):
        top=max(0, int(155*(1-yy/430))) if yy<430 else 0
        bottom=max(0, int(205*((yy-(H-520))/520))) if yy>H-520 else 0
        a=min(220,top+bottom)
        if a:
            for xx in range(W): gp[xx,yy]=(2,7,16,a)
    im=Image.alpha_composite(im,grad).convert("RGB")
    d=ImageDraw.Draw(im)
    # Small documentary-style progress marker.
    d.rounded_rectangle((38,48,682,55),radius=4,fill=(255,255,255,75))
    d.rounded_rectangle((38,48,38+644*(index+1)/6,55),radius=4,fill=(255,190,75))
    d.text((42,82),f"SCIENCE / FIELD REPORT     {index+1:02d}",font=font(17,True),fill=(255,205,115))
    headline=re.sub(r"\s+"," ",str(scene.get("screen_text", ""))).strip().upper()
    f=font(43,True)
    while d.textbbox((0,0),headline,font=f)[2] > 630 and f.size>27:
        f=font(f.size-2,True)
    d.multiline_text((42,H-430),headline,font=f,fill=(255,255,255),spacing=8,stroke_width=1,stroke_fill=(0,0,0))
    labels=scene.get("labels",[])
    if isinstance(labels,list) and labels:
        label="   /   ".join(str(v)[:26] for v in labels[:2])
        d.text((44,H-300),label,font=font(18,True),fill=(255,196,92))
    return im


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
        "4. Visuals use full-screen Wikimedia Commons photographs where suitable, with cinematic grading and camera movement. Check ATTRIBUTION.txt and verify each image license before publishing.\n"
        "5. Narration uses the local Kokoro open-weight neural TTS model (American male voice).\n"
        "6. Upload manually only after approval.\n",encoding="utf-8")
    scene_words=[text.split() for text in narrations]
    audio_files=[OUT/f"voice_{i:02d}.wav" for i in range(len(narrations))]

    # Kokoro is an open-weight neural TTS model running locally on the GitHub runner.
    # No external TTS account, API key, card, or per-character fee is required.
    import soundfile as sf
    from kokoro_onnx import Kokoro

    model_path=Path(TTS_MODEL)
    voices_path=Path(TTS_VOICES)
    if not model_path.exists() or not voices_path.exists():
        raise FileNotFoundError(
            f"Kokoro model files are missing. Expected {model_path} and {voices_path}. "
            "Check the workflow model-download step."
        )
    tts=Kokoro(str(model_path), str(voices_path))

    def render_voice(speed):
        rendered_durations=[]
        try:
            for text,wav in zip(narrations,audio_files):
                audio,sample_rate=tts.create(
                    text, voice=TTS_VOICE, speed=float(speed), lang="en-us"
                )
                if audio is None or len(audio)==0:
                    raise RuntimeError(f"Kokoro returned empty audio for {wav.name}")
                sf.write(str(wav),audio,sample_rate,subtype="PCM_16")
                dur=float(subprocess.check_output(
                    ["ffprobe","-v","error","-show_entries","format=duration",
                     "-of","default=noprint_wrappers=1:nokey=1",str(wav)],text=True
                ).strip())
                rendered_durations.append(dur)
            return rendered_durations,sum(rendered_durations)
        finally:
            # Keep the model loaded while measuring/re-rendering; it is released at exit.
            pass

    active_speed=1.0
    durations,total=render_voice(active_speed)
    for attempt in range(2):
        if 35.0 <= total <= 45.0:
            break
        # Kokoro speed > 1 speaks faster; keep adjustments modest for natural delivery.
        proposed=active_speed*(total/40.0)
        active_speed=max(0.88,min(1.15,proposed))
        durations,total=render_voice(active_speed)

    if not 35.0 <= total <= 45.0:
        raise RuntimeError(
            f"Kokoro narration duration is {total:.1f}s, outside the 35-45s target "
            f"after modest speed adjustment ({active_speed:.2f}x). "
            "Shorten or expand the generated script and rerun."
        )
    print(f"Kokoro neural narration duration: {total:.1f}s; voice: {TTS_VOICE}; speed: {active_speed:.2f}x")
    try:
        tts.voices.close()
    except Exception:
        pass
    # Render animated scene frames: the guide gestures/bobs, science highlights pulse,
    # particles drift, and each scene receives a gentle camera move during encoding.
    video_parts=[]
    fps=20
    for i,(scene,dur) in enumerate(zip(scenes,durations)):
        clip=OUT/f"motion_{i:02d}.mp4"
        frame_count=max(2,int(math.ceil(dur*fps)))
        cmd=["ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}",
             "-r",str(fps),"-i","-","-an","-vf",
             "zoompan=z='min(zoom+0.00045,1.06)':d=1:s=720x1280:fps=20,format=yuv420p",
             "-t",f"{dur:.3f}","-c:v","libx264","-preset","veryfast","-crf","21",str(clip)]
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        try:
            for frame in range(frame_count):
                phase=frame/max(1,frame_count-1)
                image=cinematic_scene(scene,i,phase)
                proc.stdin.write(image.tobytes())
            proc.stdin.close()
            rc=proc.wait()
            if rc:
                raise subprocess.CalledProcessError(rc,cmd)
        except Exception:
            if proc.poll() is None:
                proc.kill()
            raise
        still=OUT/f"scene_{i:02d}.png"
        cinematic_scene(scene,i,0.0).save(still)
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
    run(["ffmpeg","-y","-i",str(silent),"-i",str(voice),"-vf",f"ass={ass},scale=1080:1920:flags=lanczos","-r","30","-c:v","libx264","-preset","veryfast","-crf","22","-c:a","aac","-b:a","160k","-shortest","-movflags","+faststart",str(final)])
    print(f"Created cinematic science draft: {final} ({total:.1f}s)")

if __name__=="__main__":
    main()
