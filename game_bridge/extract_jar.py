"""CLI: extract the embedded game jar from AoC2.exe.

Usage: python extract_jar.py <AoC2.exe> <out_dir>
"""
import sys

from dump_save import extract_embedded_jar


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: extract_jar.py <AoC2.exe> <out_dir>")
    extract_embedded_jar(sys.argv[1], sys.argv[2])
