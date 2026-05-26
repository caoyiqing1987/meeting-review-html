#!/usr/bin/env python3
"""
Meeting Review HTML Generator.

Turns meeting transcripts + video frames into a single-file, dark-magazine-style
HTML review document. All images base64-embedded, zero external dependencies.

Usage:
  1. ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 video.mp4
  2. mkdir -p frames && ffmpeg -i video.mp4 -vf "fps=1/3" -q:v 2 frames/frame_%04d.jpg
  3. Read transcript.txt, extract work items
  4. Edit CONFIGURATION and WORK_ITEMS below
  5. python3 generate_review_html.py
  6. Open meeting-review.html in any browser
"""

import base64
import subprocess
from pathlib import Path

# ═══════════════════════════════════════════════
#  CONFIGURATION — edit these before running
# ═══════════════════════════════════════════════

FRAMES_DIR = Path("frames")
OUTPUT_HTML = Path("meeting-review.html")
PROJECT_NAME = "项目名称"
MEETING_DATE = "YYYY-MM-DD"
VIDEO_DURATION = "00:00"  # MM:SS
PARTICIPANTS = "参与人1 / 参与人2 / 参与人3"
BRAND = "团队名称"

FRAME_INTERVAL = 3     # seconds between frames (must match ffmpeg fps=1/N)
IMAGE_WIDTH = 2000     # resize width for retina
DISPLAY_WIDTH = 560    # CSS display width
DISPLAY_HEIGHT = 315

# ═══════════════════════════════════════════════
#  WORK ITEMS — fill this list from your transcript
# ═══════════════════════════════════════════════
#
# Type sets (pick one set per meeting):
#   审片会:  修改要求 / 分镜要求 / 技术难点 / 风格要求
#   产品讨论: 产品决策 / 技术方案 / 市场判断 / 行动项
#   进度同步: 进度确认 / 问题 / 待办 / 风险
#   通用:    决策 / 讨论 / 行动项 / 技术
#
# frame_start/end: floor(timestamp_seconds / FRAME_INTERVAL) + 1
#
WORK_ITEMS = [
    # {
    #     "id": "C1",
    #     "type": "修改要求",
    #     "title": "示例工作项标题",
    #     "summary": "完整的描述文字，用通顺中文总结。",
    #     "quote": "「逐字稿原文引用，保持完整。」",
    #     "frame_start": 42,
    #     "frame_end": 54,
    # },
]

# Meeting summary
SUMMARY_BODY = "核心议题摘要文字"
TAGS = [
    # ("tag red",    "修改要求 ×N"),
    # ("tag cyan",   "分镜要求 ×N"),
    # ("tag yellow", "技术难点 ×N"),
    # ("tag purple", "共 N 个工作项"),
]

# Todo table — (priority_class, task, owner, deadline)
# priority_class: "priority-high" or "priority-mid"
TODO_ITEMS = [
    # ("priority-high", "调整画面构图", "制作组", "明天中午"),
]

# ═══════════════════════════════════════════════
#  TYPE COLORS — extend as needed
# ═══════════════════════════════════════════════

TYPE_COLORS = {
    "修改要求": "#ff6b6b", "分镜要求": "#4ecdc4",
    "技术难点": "#ffd93d", "风格要求": "#a78bfa",
    "产品决策": "#a78bfa", "技术方案": "#4ecdc4",
    "市场判断": "#ffd93d", "行动项":   "#ff6b6b",
    "进度确认": "#4ecdc4", "问题":     "#ff6b6b",
    "待办":     "#ffd93d", "风险":     "#ff6b6b",
    "决策":     "#a78bfa", "讨论":     "#ffd93d",
    "技术":     "#4ecdc4",
}

# ═══════════════════════════════════════════════
#  CSS
# ═══════════════════════════════════════════════

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0f;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.7;padding:40px 20px}
.container{max-width:820px;margin:0 auto}
.header{text-align:center;padding:40px 0 30px;border-bottom:1px solid #1a1a2e;margin-bottom:30px}
.header h1{font-size:28px;font-weight:700;background:linear-gradient(135deg,#a78bfa,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}
.header .meta{color:#888;font-size:14px}.header .meta span{margin:0 12px}
.summary-box{background:#111120;border:1px solid #1a1a2e;border-radius:12px;padding:24px;margin-bottom:30px}
.summary-box h2{font-size:16px;color:#a78bfa;margin-bottom:12px}
.summary-box p{color:#ccc;font-size:14px;margin-bottom:8px;line-height:1.8}
.tags-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.tag{padding:4px 12px;border-radius:20px;font-size:12px;background:#1a1a2e;border:1px solid #2a2a3e}
.tag.red{border-color:#ff6b6b40;color:#ff6b6b}.tag.cyan{border-color:#4ecdc440;color:#4ecdc4}
.tag.yellow{border-color:#ffd93d40;color:#ffd93d}.tag.purple{border-color:#a78bfa40;color:#a78bfa}
.work-card{background:#111120;border:1px solid #1a1a2e;border-radius:12px;padding:24px;margin-bottom:20px}
.card-header{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.shot-num{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#a78bfa,#60a5fa);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;color:#fff;flex-shrink:0}
.type-tag{padding:3px 10px;border-radius:6px;font-size:12px;font-weight:600}
.card-title{font-size:18px;font-weight:600;color:#fff;margin-bottom:10px;line-height:1.4}
.card-summary{font-size:14px;color:#bbb;margin-bottom:14px;line-height:1.8}
.quote-block{background:#0d0d1a;border-left:3px solid #a78bfa;padding:12px 16px;font-size:13px;color:#999;line-height:1.8;white-space:pre-wrap;border-radius:0 8px 8px 0;margin-bottom:14px}
.frames-row{display:flex;gap:12px;flex-wrap:wrap}
.frame-wrapper{cursor:pointer;border-radius:8px;overflow:hidden;border:1px solid #1a1a2e;transition:border-color 0.2s;position:relative}
.frame-wrapper:hover{border-color:#a78bfa}
.frame-wrapper img{width:560px;height:315px;object-fit:cover;display:block}
.frame-label{position:absolute;bottom:0;left:0;right:0;background:linear-gradient(transparent,#000000cc);color:#ccc;font-size:11px;padding:20px 10px 6px}
.no-frame{width:100%;padding:40px;text-align:center;color:#555;border:1px dashed #1a1a2e;border-radius:8px}
.executor-note{margin-top:12px;font-size:12px;color:#ffd93d;border:1px dashed #ffd93d40;padding:6px 12px;border-radius:6px;display:inline-block}
.todo-section{background:#111120;border:1px solid #1a1a2e;border-radius:12px;padding:24px;margin-top:30px}
.todo-section h2{font-size:16px;color:#a78bfa;margin-bottom:16px}
.todo-table{width:100%;border-collapse:collapse;font-size:13px}
.todo-table th{text-align:left;padding:8px 12px;border-bottom:1px solid #1a1a2e;color:#888;font-weight:600;text-transform:uppercase;font-size:11px}
.todo-table td{padding:10px 12px;border-bottom:1px solid #0d0d1a;color:#ccc}
.todo-table tr:last-child td{border-bottom:none}
.priority-high{color:#ff6b6b}.priority-mid{color:#ffd93d}
.footer{text-align:center;padding:30px 0;color:#444;font-size:12px;letter-spacing:1px}
.lightbox{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.92);z-index:1000;justify-content:center;align-items:center;cursor:pointer}
.lightbox.active{display:flex}.lightbox img{max-width:90%;max-height:90%;object-fit:contain;border-radius:4px}
"""

# ═══════════════════════════════════════════════
#  IMPLEMENTATION
# ═══════════════════════════════════════════════

def resolve_frames_dir():
    if FRAMES_DIR.exists():
        return FRAMES_DIR
    script_dir = Path(__file__).parent / "frames"
    if script_dir.exists():
        return script_dir
    raise FileNotFoundError(
        f"frames/ directory not found. Create it and run ffmpeg first:\n"
        f"  mkdir -p frames\n"
        f"  ffmpeg -i video.mp4 -vf \"fps=1/3\" -q:v 2 frames/frame_%04d.jpg"
    )

def resize_and_encode(frame_path, target_width=2000):
    out_path = frame_path.with_suffix(".resized.jpg")
    subprocess.run(
        ["sips", "-Z", str(target_width), str(frame_path), "--out", str(out_path)],
        capture_output=True, timeout=30
    )
    with open(out_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    out_path.unlink(missing_ok=True)
    return data

def frame_time(frame_num, interval=3):
    total_sec = (frame_num - 1) * interval
    m, s = divmod(total_sec, 60)
    return f"{m:02d}:{s:02d}"

def pick_frames(item, frames_dir, count=2):
    candidates = []
    step = max(1, (item["frame_end"] - item["frame_start"]) // (count + 1))
    for i in range(count):
        fn = item["frame_start"] + step * (i + 1)
        fn = max(item["frame_start"], min(fn, item["frame_end"]))
        if fn not in {c[0] for c in candidates}:
            candidates.append(fn)
    if not candidates:
        candidates = [item["frame_start"]]
    results = []
    for fn in candidates:
        fp = frames_dir / f"frame_{fn:04d}.jpg"
        if fp.exists():
            try:
                b64 = resize_and_encode(fp, IMAGE_WIDTH)
                results.append((fn, b64))
            except Exception:
                pass
    return results

def build_html():
    frames_dir = resolve_frames_dir()
    for item in WORK_ITEMS:
        item["frames"] = pick_frames(item, frames_dir)

    cards = ""
    for item in WORK_ITEMS:
        tc = TYPE_COLORS.get(item["type"], "#ffffff")
        imgs = ""
        if item["frames"]:
            for fn, b64 in item["frames"]:
                ts = frame_time(fn, FRAME_INTERVAL)
                imgs += f'''
                <div class="frame-wrapper" onclick="openLightbox(this.querySelector('img'))">
                    <img src="data:image/jpeg;base64,{b64}" alt="帧 {fn} @ {ts}" loading="lazy">
                    <span class="frame-label">帧 {fn} · {ts}</span>
                </div>'''
        else:
            imgs = '<div class="no-frame">暂无对应帧画面</div>'

        cards += f'''
        <div class="work-card">
            <div class="card-header">
                <span class="shot-num">{item["id"]}</span>
                <span class="type-tag" style="background:{tc}20; color:{tc}; border:1px solid {tc}40">{item["type"]}</span>
            </div>
            <h3 class="card-title">{item["title"]}</h3>
            <p class="card-summary">{item["summary"]}</p>
            <div class="quote-block">{item["quote"]}</div>
            <div class="frames-row">{imgs}</div>
            <div class="executor-note">⚠ 系统推测，请自行确认</div>
        </div>'''

    tags_html = "".join(f'<span class="{cls}">{label}</span>' for cls, label in TAGS)

    todo_rows = ""
    for prio, task, owner, deadline in TODO_ITEMS:
        todo_rows += f'''
            <tr>
                <td class="{prio}">{'🔴 高' if 'high' in prio else '🟡 中'}</td>
                <td>{task}</td>
                <td>{owner}</td>
                <td>{deadline}</td>
            </tr>'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{PROJECT_NAME} · 工作清单</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>{PROJECT_NAME} · 工作清单</h1>
        <div class="meta">
            <span>{MEETING_DATE}</span>
            <span>·</span>
            <span>时长 {VIDEO_DURATION}</span>
            <span>·</span>
            <span>{PARTICIPANTS}</span>
        </div>
    </div>

    <div class="summary-box">
        <h2>📋 会议总结</h2>
        <p>{SUMMARY_BODY}</p>
        <div class="tags-row">{tags_html}</div>
    </div>

    {cards}

    <div class="todo-section">
        <h2>📌 待办事项</h2>
        <table class="todo-table">
            <tr><th>优先级</th><th>任务</th><th>负责人</th><th>交付时间</th></tr>
            {todo_rows}
        </table>
    </div>

    <div class="footer">{BRAND} · Generated by meeting-review-html</div>
</div>

<div class="lightbox" id="lightbox" onclick="this.classList.remove('active')">
    <img id="lightbox-img" src="" alt="放大查看">
</div>

<script>
function openLightbox(img) {{
    document.getElementById('lightbox-img').src = img.src;
    document.getElementById('lightbox').classList.add('active');
}}
document.addEventListener('keydown', function(e) {{
    if(e.key === 'Escape') {{
        document.getElementById('lightbox').classList.remove('active');
    }}
}});
</script>
</body>
</html>'''

if __name__ == "__main__":
    if not WORK_ITEMS:
        print("ERROR: WORK_ITEMS is empty. Edit the script and add your work items first.")
        exit(1)
    html = build_html()
    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"✅ HTML generated: {OUTPUT_HTML.resolve()}")
    print(f"   Work items: {len(WORK_ITEMS)}")
    frames_used = sum(1 for item in WORK_ITEMS if item.get("frames"))
    print(f"   Items with frames: {frames_used}/{len(WORK_ITEMS)}")
