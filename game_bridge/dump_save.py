"""Python wrapper around SaveDump: locate game files, run Java, parse JSON.

Usage:
    python dump_save.py <absolute-path-to-serialized-file> [--game-root GAME_ROOT]

Also hosts extract_embedded_jar() (used by extract_jar.py CLI).
"""
import argparse
import io
import os
import subprocess
import sys
import zipfile


def extract_embedded_jar(exe_path: str, out_dir: str) -> str:
    data = open(exe_path, "rb").read()
    i = data.find(b"PK\x03\x04")
    if i < 0:
        raise RuntimeError("no embedded zip found in exe")
    out_jar = os.path.join(out_dir, "aoc2.jar")
    z = zipfile.ZipFile(io.BytesIO(data[i:]))
    with zipfile.ZipFile(out_jar, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in z.infolist():
            dst.writestr(info, z.read(info.filename))
    print(f"extracted {out_jar} ({os.path.getsize(out_jar)} bytes, {len(z.namelist())} entries)")
    return out_jar


def locate(work_dir: str, game_root: str, bridge_dir: str):
    exe = os.path.join(game_root, "AoC2.exe")
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"game exe not found: {exe}")
    jre_java = os.path.join(game_root, "jre", "bin", "java.exe")
    java = jre_java if os.path.isfile(jre_java) else "java"
    os.makedirs(work_dir, exist_ok=True)
    jar = os.path.join(work_dir, "aoc2.jar")
    if not os.path.isfile(jar):
        extract_embedded_jar(exe, work_dir)
    classes = os.path.join(bridge_dir, "build")
    if not os.path.isfile(os.path.join(classes, "SaveDump.class")):
        subprocess.run(["cmd", "/c", os.path.join(bridge_dir, "build.bat")], check=True)
    return java, jar, classes


def dump_file(path: str, game_root: str, bridge_dir: str, work_dir: str, max_depth: int = 8) -> str:
    java, jar, classes = locate(work_dir, game_root, bridge_dir)
    cp = os.pathsep.join([jar, classes])
    proc = subprocess.run(
        [java, "-cp", cp, "SaveDump", path, str(max_depth)],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"SaveDump failed ({proc.returncode}): {proc.stderr[:500]}")
    return proc.stdout.strip()


def default_bridge_dirs():
    bridge_dir = os.path.dirname(os.path.abspath(__file__))
    work_dir = os.path.abspath(os.path.join(bridge_dir, "..", ".bridge"))
    return bridge_dir, work_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--game-root", default=os.environ.get("AOC2_GAME_ROOT", ""))
    ap.add_argument("--max-depth", type=int, default=8)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if not args.game_root:
        sys.exit("set --game-root or env AOC2_GAME_ROOT")
    bridge_dir, work_dir = default_bridge_dirs()
    result = dump_file(args.file, args.game_root, bridge_dir, work_dir, args.max_depth)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(result)
    else:
        print(result)
