#!/usr/bin/env python3
"""Disk space sanity — abort если внешний < 10GB free."""
import shutil, sys
EXTERNAL = "/run/media/user/External"
INTERNAL = "/"
ext = shutil.disk_usage(EXTERNAL).free / 1e9
int_ = shutil.disk_usage(INTERNAL).free / 1e9
print(f"External: {ext:.1f} GB free  |  Internal: {int_:.1f} GB free")
if ext < 10:
    print("ERROR: External disk < 10 GB — abort", file=sys.stderr); sys.exit(2)
if int_ < 5:
    print("ERROR: Internal disk < 5 GB — abort", file=sys.stderr); sys.exit(2)
