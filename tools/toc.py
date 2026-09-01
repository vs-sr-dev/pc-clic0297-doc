#!/usr/bin/env python3
"""toc.py -- read the CD table of contents from a Windows CD/DVD drive.

Uses DeviceIoControl / IOCTL_CDROM_READ_TOC on the volume handle. No special
privileges are needed; the handle is opened read-only with full sharing.

    python tools/toc.py E

Prints every track descriptor, the lead-out, and -- if the volume carries an
ISO 9660 primary volume descriptor -- the difference between the lead-out LBA
and the declared volume size. That difference is the whole point of this tool.
"""
import ctypes
import ctypes.wintypes as w
import sys

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

IOCTL_CDROM_READ_TOC = 0x00024000
IOCTL_CDROM_GET_LAST_SESSION = 0x00024038

BS = chr(92)  # backslash; heredocs in this shell eat them


class TRACK_DATA(ctypes.Structure):
    _fields_ = [
        ("Reserved", ctypes.c_ubyte),
        ("Control_Adr", ctypes.c_ubyte),
        ("TrackNumber", ctypes.c_ubyte),
        ("Reserved1", ctypes.c_ubyte),
        ("Address", ctypes.c_ubyte * 4),
    ]


class CDROM_TOC(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ubyte * 2),
        ("FirstTrack", ctypes.c_ubyte),
        ("LastTrack", ctypes.c_ubyte),
        ("TrackData", TRACK_DATA * 100),
    ]


def msf_to_lba(m, s, f):
    return (m * 60 + s) * 75 + f - 150


def open_volume(letter):
    path = BS + BS + "." + BS + letter.upper() + ":"
    k32 = ctypes.windll.kernel32
    k32.CreateFileW.restype = ctypes.c_void_p
    h = k32.CreateFileW(
        path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE_VALUE or h is None:
        raise OSError("CreateFileW(%s) failed, GetLastError=%d"
                      % (path, ctypes.windll.kernel32.GetLastError()))
    return h, path


def read_toc(h):
    toc = CDROM_TOC()
    ret = w.DWORD(0)
    ok = ctypes.windll.kernel32.DeviceIoControl(
        ctypes.c_void_p(h), IOCTL_CDROM_READ_TOC, None, 0,
        ctypes.byref(toc), ctypes.sizeof(toc), ctypes.byref(ret), None)
    if not ok:
        raise OSError("IOCTL_CDROM_READ_TOC failed, GetLastError=%d"
                      % ctypes.windll.kernel32.GetLastError())
    return toc, ret.value


def pvd_sectors(letter):
    """Read sector 16 through the volume device and return declared size."""
    path = BS + BS + "." + BS + letter.upper() + ":"
    try:
        with open(path, "rb") as f:
            f.seek(16 * 2048)
            b = f.read(2048)
    except OSError as e:
        return None, "sector 16 unreadable: %r" % (e,)
    if len(b) < 2048 or b[1:6] != b"CD001":
        return None, "sector 16 is not CD001"
    n = int.from_bytes(b[80:84], "little")
    nbe = int.from_bytes(b[84:88], "big")
    return (n, nbe), None


def main():
    letter = sys.argv[1] if len(sys.argv) > 1 else "E"
    h, path = open_volume(letter)
    print("device      : %s" % path)
    toc, n = read_toc(h)
    length = (toc.Length[0] << 8) | toc.Length[1]
    print("toc bytes   : %d returned, header length field %d" % (n, length))
    print("first track : %d" % toc.FirstTrack)
    print("last track  : %d" % toc.LastTrack)
    print()
    leadout = None
    ntracks = 0
    for i in range(100):
        t = toc.TrackData[i]
        if t.TrackNumber == 0:
            continue
        a = t.Address
        lba = msf_to_lba(a[1], a[2], a[3])
        adr = (t.Control_Adr >> 4) & 0xF
        ctrl = t.Control_Adr & 0xF
        kind = "DATA" if (ctrl & 0x4) else "AUDIO"
        pre = "pre-emphasis" if (ctrl & 0x1) else "no pre-emphasis"
        cp = "copy permitted" if (ctrl & 0x2) else "copy prohibited"
        tag = "  <- LEAD-OUT" if t.TrackNumber == 0xAA else ""
        print("track %3d  adr=%d ctrl=0x%X (%s, %s, %s)  MSF %02d:%02d:%02d  LBA %d%s"
              % (t.TrackNumber, adr, ctrl, kind, pre, cp,
                 a[1], a[2], a[3], lba, tag))
        if t.TrackNumber == 0xAA:
            leadout = lba
        else:
            ntracks += 1
        if t.TrackNumber == toc.LastTrack and leadout is not None:
            break
    print()
    print("tracks      : %d" % ntracks)
    ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(h))

    got, err = pvd_sectors(letter)
    if err:
        print("pvd         : %s" % err)
        return
    le, be = got
    print("pvd vol size: %d sectors (LE)  %d (BE)  %s"
          % (le, be, "agree" if le == be else "*** DISAGREE ***"))
    print("pvd bytes   : %d" % (le * 2048))
    if leadout is not None:
        print()
        print("lead-out LBA        %9d" % leadout)
        print("pvd volume space  - %9d" % le)
        print("                   ----------")
        print("                    %9d" % (leadout - le))


if __name__ == "__main__":
    main()
