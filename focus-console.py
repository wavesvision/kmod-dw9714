#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Interactive focus console for the DW9714 VCM.
#
# The script keeps the V4L2 subdevice open for its whole lifetime, which keeps
# the VCM runtime-PM active and the lens at the selected position. When the
# script exits, the driver parks the lens at position 0 and remembers the last
# value for the next time the device is opened.

import argparse
import fcntl
import glob
import os
import re
import select
import struct
import subprocess
import sys
import termios
import tty

V4L2_CID_FOCUS_ABSOLUTE = 0x009A090A
VIDIOC_G_CTRL = 0xC008561B
VIDIOC_S_CTRL = 0xC008561C


def run(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        sys.exit(f"{cmd[0]} not found; install v4l-utils")
    return result.stdout + result.stderr


def find_device(explicit):
    if explicit:
        return explicit

    for media in sorted(glob.glob("/dev/media*")):
        topology = run(["media-ctl", "-d", media, "-p"])
        match = re.search(r"entity \d+: (dw9714 [^ ]+)", topology)
        if not match:
            continue

        device = run(["media-ctl", "-d", media, "-e", match.group(1)]).strip()
        if device.startswith("/dev/v4l-subdev"):
            return device

    sys.exit("DW9714 lens subdevice not found; use --device /dev/v4l-subdevN")


def parse_control(text):
    match = re.search(
        r"focus_absolute.*?min=(-?\d+).*?max=(-?\d+).*?step=(-?\d+)"
        r".*?default=(-?\d+).*?value=(-?\d+)",
        text,
    )
    if not match:
        sys.exit("focus_absolute control not found on the selected device")
    minimum, maximum, step, default, value = (int(v) for v in match.groups())
    return minimum, maximum, step, default, value


def get_ctrl(fd):
    data = fcntl.ioctl(fd, VIDIOC_G_CTRL,
                       struct.pack("=Ii", V4L2_CID_FOCUS_ABSOLUTE, 0))
    _, value = struct.unpack("=Ii", data)
    return value


def set_ctrl(fd, value):
    fcntl.ioctl(fd, VIDIOC_S_CTRL,
                struct.pack("=Ii", V4L2_CID_FOCUS_ABSOLUTE, value))


def read_key():
    fd = sys.stdin.fileno()
    ready, _, _ = select.select([fd], [], [], 0.2)
    if not ready:
        return None

    char = os.read(fd, 1).decode("latin1")
    if char != "\x1b":
        return char

    sequence = char
    while True:
        ready, _, _ = select.select([fd], [], [], 0.01)
        if not ready:
            break
        sequence += os.read(fd, 1).decode("latin1")
        if len(sequence) >= 3 and (sequence[-1].isalpha() or sequence[-1] == "~"):
            break
    return sequence


def draw(device, value, minimum, maximum, step, fast_step, use_color, use_ascii):
    width = 48
    span = maximum - minimum if maximum > minimum else 1
    filled = int(round((value - minimum) * width / span))
    filled = max(0, min(width, filled))
    percent = int(round((value - minimum) * 100 / span))

    if use_ascii:
        bar_fill, bar_empty = "#", "-"
    else:
        bar_fill, bar_empty = "█", "░"

    if use_color:
        title = "\x1b[1;36mDW9714 focus console\x1b[0m"
        bar = "\x1b[36m" + bar_fill * filled + "\x1b[2m" + bar_empty * (width - filled) + "\x1b[0m"
        number = f"\x1b[1;33m{value:4d}\x1b[0m"
        hint = "\x1b[2m"
        reset = "\x1b[0m"
    else:
        title = "DW9714 focus console"
        bar = bar_fill * filled + bar_empty * (width - filled)
        number = f"{value:4d}"
        hint = ""
        reset = ""

    arrows = "up/down" if use_ascii else "↑/↓"

    lines = [
        f"{title}  {device}",
        f"[{bar}]  {number} / {maximum}   {percent:3d}%",
        f"{minimum:<4d} {' ' * (width - 8)} {maximum:>4d}",
        "",
        f"{hint}{arrows} {step:<3d}   +/- 1   PgUp/PgDn {fast_step:<3d}   "
        f"r reset   q quit{reset}",
    ]
    sys.stdout.write("\x1b[H" + "\n".join(line + "\x1b[K" for line in lines) + "\x1b[J")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        description="Adjust DW9714 focus with the up/down arrow keys.")
    parser.add_argument("-d", "--device", help="V4L2 lens subdevice")
    parser.add_argument("-s", "--step", type=int, default=16,
                        help="arrow-key step (default: 16)")
    parser.add_argument("--ascii", action="store_true",
                        help="use ASCII instead of Unicode blocks")
    parser.add_argument("--no-color", action="store_true",
                        help="disable ANSI colours")
    args = parser.parse_args()

    if not sys.stdin.isatty():
        sys.exit("stdin is not a terminal")

    device = find_device(args.device)
    controls = run(["v4l2-ctl", "-d", device, "--list-ctrls"])
    minimum, maximum, _, default, _ = parse_control(controls)

    try:
        fd = os.open(device, os.O_RDWR)
    except PermissionError:
        sys.exit(f"cannot open {device}; add the user to the video group or use sudo")

    step = max(1, args.step)
    fast_step = max(step, min(128, step * 8))

    value = get_ctrl(fd)
    value = max(minimum, min(maximum, value))

    old_term = termios.tcgetattr(sys.stdin.fileno())
    tty.setcbreak(sys.stdin.fileno())

    use_color = sys.stdout.isatty() and not args.no_color
    use_ascii = args.ascii or "UTF-8" not in (sys.stdout.encoding or "").upper()

    try:
        sys.stdout.write("\x1b[2J")
        while True:
            draw(device, value, minimum, maximum, step, fast_step,
                 use_color, use_ascii)
            key = read_key()
            if key is None:
                continue

            if key in ("q", "Q", "\x03", "\x1b"):
                break
            if key in ("\x1b[A", "\x1bOA"):
                value += step
            elif key in ("\x1b[B", "\x1bOB"):
                value -= step
            elif key == "\x1b[5~":
                value += fast_step
            elif key == "\x1b[6~":
                value -= fast_step
            elif key in ("+", "="):
                value += 1
            elif key in ("-", "_"):
                value -= 1
            elif key in ("r", "R"):
                value = default
            else:
                continue

            value = max(minimum, min(maximum, value))
            set_ctrl(fd, value)
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_term)
        os.close(fd)
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.write(
            f"Focus set to {value}. The lens parks at 0 when the device is "
            f"released; the value {value} is restored on the next open "
            f"(until reboot or module reload).\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
