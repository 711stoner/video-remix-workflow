#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_ROOT = Path.home() / "VideoRemixWorkspace"
ROOT = Path(os.environ.get("VIDEO_REMIX_ROOT", str(DEFAULT_ROOT))).expanduser().resolve()
PROJECTS_DIR = ROOT / "05-剪辑工程与成品" / "自动剪辑制作工程"
SCRIPT_DIR = ROOT / "03-二创文案与脚本"
VIDEO_DIR = ROOT / "04-下载原视频"
DESKTOP = Path.home() / "Desktop"
WEB_DIR = Path(__file__).resolve().parent
PORT = int(os.environ.get("VIDEO_WORKFLOW_PORT", "8788"))

STEP_TITLES = {
    0: "确认任务状态并读取必要文档",
    1: "锁定唯一素材 URL",
    2: "生成原片内容文档",
    3: "下载最高画质兼容原片",
    4: "建立画面事实表",
    5: "生成二创故事方案",
    6: "锁定二创解说稿 / 最终配音稿",
    7: "Qwen 正式配音 + 双 ASR",
    8: "连续配音试听与节奏微调",
    9: "建立画面时间线",
    10: "正文音画剪辑与画面底版锁定",
    11: "成片包装与最终混音",
    12: "完整成片检查与导出",
    13: "交付用户检查与确认",
    14: "锁版、封面、发布文案与双份输出",
}

PASS_PHRASES = {
    8: ["允许进入第 9 步"],
    10: ["允许进入第 11 步"],
    11: ["允许进入第 12 步"],
    12: ["允许交付用户检查"],
    13: ["允许进入第 14 步", "已确认"],
    14: ["封面通过", "发布标题通过", "发布正文通过"],
}

QC_DEFAULTS = {
    8: "配音连续试听QC.md",
    10: "正文音画剪辑QC.md",
    11: "成片包装与混音QC.md",
    12: "完整成片QC.md",
    13: "用户反馈与确认.md",
    14: "封面与发布文案QC.md",
}

def safe_path(raw: str) -> Path:
    p = Path(raw).expanduser().resolve()
    allowed = [ROOT, DESKTOP]
    if not any(p == base or p.is_relative_to(base) for base in allowed):
        raise ValueError("路径不在允许范围内")
    return p

def clean_children(path: Path):
    if not path.exists():
        return []
    return [p for p in path.iterdir() if not p.name.startswith("._")]

def project_prefix(project_name: str) -> str:
    m = re.match(r"^(.+?条)短视频成片$", project_name)
    return m.group(1) if m else project_name.replace("短视频成片", "")

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""

def work_order_info(project: Path) -> dict:
    p = project / "本期制作单.md"
    text = read_text(p)
    info = {"path": str(p), "stage": None, "theme": "", "url": ""}
    for line in text.splitlines():
        s = line.strip().lstrip("-").strip()
        if "当前阶段" in s:
            m = re.search(r"第\s*(\d+)\s*步", s)
            if m:
                info["stage"] = int(m.group(1))
        if s.startswith("主题："):
            info["theme"] = s.split("：", 1)[1].strip()
        if "原始" in s and "URL" in s and "：" in s:
            info["url"] = s.split("：", 1)[1].strip()
    return info

def glob_first(patterns):
    for pattern in patterns:
        hits = sorted([p for p in ROOT.glob(pattern) if not p.name.startswith("._")])
        if hits:
            return hits[0]
    return None

def project_files(project: Path):
    return [p for p in project.rglob("*") if p.is_file() and not p.name.startswith("._")]

def first_named(files, names=None, contains=None, suffix=None):
    names = names or []
    contains = contains or []
    for p in files:
        if p.name in names:
            return p
    for p in files:
        if all(x in p.name for x in contains) and (not suffix or p.suffix == suffix):
            return p
    return None

def desktop_match(prefix: str, tail: str):
    if not DESKTOP.exists():
        return None
    for p in clean_children(DESKTOP):
        if p.is_dir() and p.name.startswith(prefix) and p.name.endswith(tail):
            return p
    return None

def step_docs(project: Path, step: int):
    prefix = project_prefix(project.name)
    files = project_files(project)
    docs = []
    expected = None

    def add(p, role):
        if p and p.exists() and p.is_file():
            docs.append({"path": str(p), "name": p.name, "role": role})

    if step == 0:
        add(ROOT / "02-方法论与规范" / "视频二创制作SOP.md", "主 SOP")
        add(ROOT / "02-方法论与规范" / "每步文档与反馈归档规范.md", "反馈归档规范")
    elif step == 1:
        add(project / "本期制作单.md", "制作单")
        add(project / "本期制作反馈与修改记录.md", "反馈总账")
        expected = project / "本期制作反馈与修改记录.md"
    elif step == 2:
        p = glob_first([f"03-二创文案与脚本/{prefix}*原片内容文档.md"])
        add(p, "原片内容文档")
    elif step == 3:
        p = glob_first([f"04-下载原视频/{prefix}视频素材.mp4", f"04-下载原视频/{prefix}*视频素材*.mp4"])
        add(p, "正式兼容原片")
    elif step == 4:
        p = glob_first([f"03-二创文案与脚本/{prefix}*画面事实表.md", f"03-二创文案与脚本/{prefix}*事实表.md"])
        if not p:
            p = first_named(files, contains=["事实表"], suffix=".md")
        add(p, "画面事实表")
    elif step == 5:
        p = glob_first([f"03-二创文案与脚本/{prefix}*二创故事方案.md"])
        add(p, "二创故事方案")
    elif step == 6:
        add(glob_first([f"03-二创文案与脚本/{prefix}*二创解说稿.md", f"03-二创文案与脚本/{prefix}*二创解说*.md"]), "二创解说稿")
        add(first_named(files, names=["最终配音稿.txt"]), "最终配音稿")
    elif step == 7:
        add(first_named(files, names=["配音技术记录.json"]), "配音技术记录")
        add(first_named(files, names=["ASR内容质检.json"]), "ASR内容质检")
        add(first_named(files, names=["配音时间表.json"]), "配音时间表")
        add(first_named(files, names=["最终配音.wav"]), "最终配音")
    elif step == 8:
        p = first_named(files, names=["配音连续试听QC.md"])
        add(p, "连续试听 QC")
        add(first_named(files, names=["最终配音.wav"]), "最终配音（连续试听）")
        expected = project / "配音" / "v1" / "配音连续试听QC.md"
    elif step == 9:
        add(first_named(files, names=["成片画面时间线.md"]), "画面时间线 MD")
        add(first_named(files, names=["成片画面时间线.json"]), "画面时间线 JSON")
    elif step == 10:
        add(first_named(files, names=["正文音画剪辑QC.md"]), "音画剪辑 QC")
        add(first_named(files, names=["画面剪辑记录.json"]), "画面剪辑记录")
        add(first_named(files, names=["正文音画检查版.mp4"]), "正文音画检查版")
        expected = project / "正文音画剪辑QC.md"
    elif step == 11:
        add(first_named(files, names=["成片包装与混音QC.md"]), "包装与混音 QC")
        add(first_named(files, names=["字幕时间表.json"]), "字幕时间表")
        add(first_named(files, names=["声音设计图.md"]), "声音设计图")
        add(first_named(files, names=["包装混音检查版.mp4"]), "包装混音检查版")
        expected = project / "成片包装与混音QC.md"
    elif step == 12:
        add(first_named(files, names=["完整成片QC.md"]), "完整成片 QC")
        add(first_named(files, names=["检查通过版.mp4"]) or first_named(files, contains=["检查通过版"], suffix=".mp4"), "检查通过版")
        expected = project / "完整成片QC.md"
    elif step == 13:
        add(first_named(files, names=["用户反馈与确认.md"]), "用户反馈与确认")
        pending = desktop_match(prefix, "待检查")
        if pending:
            for p in clean_children(pending):
                if p.is_file() and p.suffix.lower() == ".mp4":
                    add(p, "桌面待检查版")
        expected = project / "用户反馈与确认.md"
    elif step == 14:
        add(first_named(files, names=["封面与发布文案QC.md"]), "封面与发布文案 QC")
        add(first_named(files, names=["本期发布资产记录.md"]), "发布资产记录")
        output = project / "本期输出"
        if output.exists():
            for p in clean_children(output):
                if p.is_file() and p.suffix.lower() in {".mp4", ".png", ".jpg", ".jpeg", ".txt"}:
                    add(p, "硬盘正式输出")
        expected = project / "封面与发布文案QC.md"

    return docs, expected

def status_for(project: Path, step: int, docs, stage):
    if stage is not None and step <= stage:
        return "passed"
    phrases = PASS_PHRASES.get(step, [])
    if phrases:
        all_text = "\n".join(read_text(Path(d["path"])) for d in docs if Path(d["path"]).suffix.lower() in {".md", ".txt", ".json"})
        if all(x in all_text for x in phrases):
            return "passed"
    if docs:
        return "has_files"
    return "missing"

def project_payload(project_name: str):
    project = safe_path(str(PROJECTS_DIR / project_name))
    if not project.exists() or not project.is_dir():
        raise FileNotFoundError("项目不存在")
    wo = work_order_info(project)
    steps = []
    for n in range(15):
        docs, expected = step_docs(project, n)
        steps.append({
            "number": n,
            "title": STEP_TITLES[n],
            "status": status_for(project, n, docs, wo["stage"]),
            "docs": docs,
            "expected_doc": str(expected) if expected else "",
        })
    return {
        "name": project.name,
        "prefix": project_prefix(project.name),
        "path": str(project),
        "theme": wo["theme"],
        "stage": wo["stage"],
        "url": wo["url"],
        "feedback_path": str(project / "本期制作反馈与修改记录.md"),
        "steps": steps,
    }

def doc_template(project: Path, step: int):
    title = QC_DEFAULTS.get(step, f"第{step}步记录.md")
    base = f"# {title.removesuffix('.md')}\n\n项目：{project.name}\n\n"
    if step == 10:
        return base + "## 完整观看\n\n- 状态：待检查\n\n## 问题记录\n\n## 最终结论\n\n- 是否允许进入第 11 步：否\n"
    if step == 11:
        return base + "## 字幕\n\n## 顶部标题\n\n## 现场声\n\n## BGM\n\n## 音效\n\n## 最终混音\n\n## 最终结论\n\n- 是否允许进入第 12 步：否\n"
    if step == 12:
        return base + "## 技术检查\n\n## 完整观看检查\n\n## 设备听感\n\n## 问题与回退\n\n## 最终结论\n\n- 是否允许交付用户检查：否\n"
    if step == 13:
        return base + "## 当前检查版本\n\n## 用户反馈\n\n## 修改与复核\n\n## 确认状态\n\n- 是否允许进入第 14 步：否\n"
    if step == 14:
        return base + "## 封面\n\n## 发布标题\n\n## 发布正文\n\n## 标签\n\n## 最终结论\n\n- 封面通过：否\n- 发布标题通过：否\n- 发布正文通过：否\n"
    return base

def append_feedback(project: Path, step: int, message: str, detail: str = ""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = project / "本期制作反馈与修改记录.md"
    if not total.exists():
        total.write_text(f"# 本期制作反馈与修改记录\n\n项目：{project.name}\n", encoding="utf-8")
    block = (
        f"\n## {now}｜第 {step} 步｜待处理\n\n"
        f"用户反馈：\n{message.strip()}\n\n"
        f"问题定位：\n{detail.strip() or '待定位'}\n\n"
        f"处理：\n待处理\n\n结果：\n未验证\n\n永久规则：\n否\n"
    )
    with total.open("a", encoding="utf-8") as f:
        f.write(block)

    docs, expected = step_docs(project, step)
    qc = None
    if step in QC_DEFAULTS:
        for d in docs:
            if d["name"] == QC_DEFAULTS[step]:
                qc = Path(d["path"])
                break
        if qc is None:
            qc = expected or (project / QC_DEFAULTS[step])
            qc.parent.mkdir(parents=True, exist_ok=True)
            qc.write_text(doc_template(project, step), encoding="utf-8")
        with qc.open("a", encoding="utf-8") as f:
            f.write(f"\n## {now}｜用户反馈\n\n{message.strip()}\n\n定位：{detail.strip() or '待定位'}\n")
    return total, qc

def sync_review(project: Path):
    prefix = project_prefix(project.name)
    files = project_files(project)
    src = first_named(files, names=["检查通过版.mp4"]) or first_named(files, contains=["检查通过版"], suffix=".mp4")
    if not src:
        raise FileNotFoundError("没有找到检查通过版.mp4")
    theme = work_order_info(project)["theme"] or project.name.replace("短视频成片", "")
    dest = DESKTOP / f"{prefix}｜{theme}｜待检查"
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"{prefix}｜{theme}｜检查通过版.mp4"
    shutil.copy2(src, out)
    return out

def sync_output(project: Path):
    prefix = project_prefix(project.name)
    source = project / "本期输出"
    if not source.exists():
        raise FileNotFoundError("硬盘本期输出文件夹不存在")
    theme = work_order_info(project)["theme"] or project.name.replace("短视频成片", "")
    dest = DESKTOP / f"{prefix}｜{theme}｜本期输出"
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for p in clean_children(source):
        if p.is_file() and p.suffix.lower() in {".mp4", ".png", ".jpg", ".jpeg", ".txt"}:
            out = dest / p.name
            shutil.copy2(p, out)
            copied.append(str(out))
    if not copied:
        raise FileNotFoundError("硬盘本期输出里没有可同步的正式文件")
    return dest, copied

class Handler(BaseHTTPRequestHandler):
    server_version = "VideoWorkflow/1.0"

    def send_json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                raw = (WEB_DIR / "static" / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if parsed.path == "/api/projects":
                projects = [p.name for p in clean_children(PROJECTS_DIR) if p.is_dir() and p.name.endswith("短视频成片")]
                projects.sort()
                self.send_json({"projects": projects})
                return
            if parsed.path == "/api/project":
                self.send_json(project_payload(q.get("name", [""])[0]))
                return
            if parsed.path == "/api/file":
                p = safe_path(q.get("path", [""])[0])
                self.send_json({"path": str(p), "name": p.name, "content": read_text(p), "exists": p.exists()})
                return
            if parsed.path == "/api/media":
                self.serve_media(safe_path(q.get("path", [""])[0]))
                return
            self.send_error(404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def serve_media(self, p: Path):
        if not p.exists() or not p.is_file():
            self.send_error(404)
            return
        size = p.stat().st_size
        start, end = 0, size - 1
        status = 200
        range_header = self.headers.get("Range")
        if range_header:
            m = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
                status = 206
        length = max(0, end - start + 1)
        self.send_response(status)
        self.send_header("Content-Type", mimetypes.guess_type(p.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with p.open("rb") as f:
            f.seek(start)
            remain = length
            while remain:
                chunk = f.read(min(1024 * 1024, remain))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remain -= len(chunk)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            data = self.json_body()
            if parsed.path == "/api/file":
                p = safe_path(data["path"])
                if p.suffix.lower() not in {".md", ".txt", ".json", ".tsv"}:
                    raise ValueError("网页只允许保存文本类工作文件")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(data.get("content", ""), encoding="utf-8")
                self.send_json({"ok": True, "path": str(p)})
                return
            if parsed.path == "/api/create_doc":
                project = safe_path(str(PROJECTS_DIR / data["project"]))
                step = int(data["step"])
                _, expected = step_docs(project, step)
                if not expected:
                    raise ValueError("这一步没有固定可新建 QC 文档")
                expected.parent.mkdir(parents=True, exist_ok=True)
                if not expected.exists():
                    expected.write_text(doc_template(project, step), encoding="utf-8")
                self.send_json({"ok": True, "path": str(expected)})
                return
            if parsed.path == "/api/feedback":
                project = safe_path(str(PROJECTS_DIR / data["project"]))
                total, qc = append_feedback(project, int(data["step"]), data.get("message", ""), data.get("detail", ""))
                self.send_json({"ok": True, "feedback_path": str(total), "qc_path": str(qc) if qc else ""})
                return
            if parsed.path == "/api/reveal":
                p = safe_path(data["path"])
                target = p if p.exists() else p.parent
                subprocess.run(["open", "-R", str(target)], check=False)
                self.send_json({"ok": True})
                return
            if parsed.path == "/api/sync_review":
                project = safe_path(str(PROJECTS_DIR / data["project"]))
                out = sync_review(project)
                self.send_json({"ok": True, "path": str(out)})
                return
            if parsed.path == "/api/sync_output":
                project = safe_path(str(PROJECTS_DIR / data["project"]))
                dest, copied = sync_output(project)
                self.send_json({"ok": True, "path": str(dest), "files": copied})
                return
            self.send_error(404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} {fmt % args}")

def main():
    print(f"视频二创工作台：http://127.0.0.1:{PORT}")
    print(f"项目根目录：{ROOT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
