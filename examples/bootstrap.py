#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MIN_NODE = (22, 15, 0)

NODE_BIN = None
NPM_BIN = None


def run(cmd, cwd=None, check=True):
    print(f"\n>> {' '.join(map(str, cmd))}")
    p = subprocess.run(cmd, cwd=cwd, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(map(str, cmd))}")
    return p.returncode


def get_output(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if p.returncode != 0:
        return ""
    return p.stdout.strip()


def parse_node_ver(s: str):
    # e.g. "v24.13.0"
    m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", s)
    if not m:
        return None
    return tuple(map(int, m.groups()))


def ensure_tools():
    global NODE_BIN, NPM_BIN

    # Windows: 优先 .cmd/.exe，避免捡到 npm.ps1 导致 subprocess 无法执行
    if os.name == "nt":
        NODE_BIN = shutil.which("node.exe") or shutil.which("node")
        NPM_BIN = shutil.which("npm.cmd") or shutil.which("npm.exe") or shutil.which("npm")
    else:
        NODE_BIN = shutil.which("node")
        NPM_BIN = shutil.which("npm")

    if not NODE_BIN:
        raise RuntimeError("未找到 node，请先安装 Node.js >= 22.15.0")
    if not NPM_BIN:
        raise RuntimeError("未找到 npm（Windows 建议确保存在 npm.cmd），请先安装/修复 Node.js/npm")

    node_v = parse_node_ver(get_output([NODE_BIN, "-v"]))
    if not node_v:
        raise RuntimeError("无法识别 node 版本")
    if node_v < MIN_NODE:
        raise RuntimeError(f"Node 版本过低: {node_v}，需 >= {MIN_NODE}")

    print(f"Node 版本 OK: {node_v}")
    print(f"Using npm: {NPM_BIN}")


def patch_package_json(pkg_path: Path):
    data = json.loads(pkg_path.read_text(encoding="utf-8"))
    deps = data.setdefault("dependencies", {})

    if "@nut-tree/nut-js" in deps:
        deps.pop("@nut-tree/nut-js")

    deps["@nut-tree-fork/nut-js"] = "^4.2.6"
    deps["@vertfrag/rs-capture"] = "^1.3.0"

    pkg_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("已修复 package.json 依赖")


def patch_js_requires(base: Path):
    targets = [base / "server_ws.js", base / "server_webrtc.js"]
    for f in targets:
        if not f.exists():
            continue
        txt = f.read_text(encoding="utf-8")
        new_txt = txt.replace("@nut-tree/nut-js", "@nut-tree-fork/nut-js")
        if new_txt != txt:
            f.write_text(new_txt, encoding="utf-8")
            print(f"已修复 require: {f.name}")


def write_env(env_path: Path, encoder: str, fps: int, max_width: int, quality: int):
    content = (
        f"CAP_ENCODER={encoder}\n"
        f"CAP_FPS={fps}\n"
        f"CAP_MAX_WIDTH={max_width}\n"
        f"CAP_JPEG_QUALITY={quality}\n"
        "CAP_FFMPEG_PATH=\n"
    )
    env_path.write_text(content, encoding="utf-8")
    print(f"已写入 {env_path.name}")


def main():
    parser = argparse.ArgumentParser(description="rs-capture examples 启动器")
    parser.add_argument("--mode", choices=["ws", "webrtc"], default="ws", help="启动模式")
    parser.add_argument("--encoder", choices=["ffmpeg", "sharp"], default="ffmpeg")
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--max-width", type=int, default=1920)
    parser.add_argument("--quality", type=int, default=82)
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    pkg = base / "package.json"
    envf = base / ".env"

    ensure_tools()
    patch_package_json(pkg)
    patch_js_requires(base)
    write_env(envf, args.encoder, args.fps, args.max_width, args.quality)

    if not args.skip_install:
        run([NPM_BIN, "install"], cwd=str(base), check=True)

    script = "start:ws" if args.mode == "ws" else "start:webrtc"
    run([NPM_BIN, "run", script], cwd=str(base), check=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)