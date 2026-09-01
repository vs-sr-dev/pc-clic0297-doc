#!/usr/bin/env python3
"""authenticode.py -- read the certificate table at the end of a signed PE.

No previous disc in this collection carried a signed game executable, so there
was nothing to inherit. This is a minimal DER walker: it does not verify the
signature (that would need the CA's key and a clock), it reads the structure
and prints the names, the serial numbers, the validity window and the
countersigned signing time.

Three things make this readable without an ASN.1 library:

  * the certificate table is found through the PE optional header's fifth data
    directory, whose "RVA" is by definition a *file offset*, not an RVA;
  * a WIN_CERTIFICATE header is 8 bytes: dwLength, wRevision, wCertificateType;
  * inside is a PKCS#7 SignedData, and every value worth printing is a
    primitive DER string, an OID, or a UTCTime, all of which have a tag byte,
    a length, and no surprises.

    python tools/authenticode.py _work/fromzip/hp.exe
    python tools/authenticode.py _work/fromzip/hp.exe --raw
"""
import argparse
import hashlib
import struct
import sys

OIDS = {
    "2.5.4.3": "CN", "2.5.4.6": "C", "2.5.4.7": "L", "2.5.4.8": "ST",
    "2.5.4.10": "O", "2.5.4.11": "OU", "2.5.4.5": "serialNumber",
    "1.2.840.113549.1.9.1": "email",
    "1.2.840.113549.1.7.2": "signedData",
    "1.2.840.113549.1.9.4": "messageDigest",
    "1.2.840.113549.1.9.5": "signingTime",
    "1.2.840.113549.1.9.6": "counterSignature",
    "1.3.6.1.4.1.311.2.1.4": "SPC_INDIRECT_DATA",
    "1.3.6.1.4.1.311.2.1.11": "SPC_STATEMENT_TYPE",
    "1.3.6.1.4.1.311.2.1.12": "SPC_SP_OPUS_INFO",
    "1.3.6.1.4.1.311.2.1.21": "SPC_INDIVIDUAL_SP_KEY_PURPOSE",
    "1.3.6.1.4.1.311.2.1.22": "SPC_COMMERCIAL_SP_KEY_PURPOSE",
    "1.3.6.1.4.1.311.10.3.2": "codeSigning(MS)",
    "1.3.6.1.5.5.7.3.3": "codeSigning",
    "1.3.6.1.5.5.7.3.8": "timeStamping",
    "1.3.14.3.2.26": "sha1",
    "2.16.840.1.101.3.4.2.1": "sha256",
    "1.2.840.113549.2.5": "md5",
    "1.2.840.113549.1.1.1": "rsaEncryption",
    "1.2.840.113549.1.1.4": "md5WithRSA",
    "1.2.840.113549.1.1.5": "sha1WithRSA",
    "1.2.840.113549.1.1.11": "sha256WithRSA",
}

TAGNAME = {0x01: "BOOLEAN", 0x02: "INTEGER", 0x03: "BIT STRING",
           0x04: "OCTET STRING", 0x05: "NULL", 0x06: "OID",
           0x0c: "UTF8String", 0x13: "PrintableString", 0x14: "TeletexString",
           0x16: "IA5String", 0x17: "UTCTime", 0x18: "GeneralizedTime",
           0x1e: "BMPString", 0x30: "SEQUENCE", 0x31: "SET"}


def read_len(b, i):
    n = b[i]
    i += 1
    if n < 0x80:
        return n, i
    k = n & 0x7f
    v = int.from_bytes(b[i:i + k], "big")
    return v, i + k


def decode_oid(b):
    if not b:
        return ""
    out = [str(b[0] // 40), str(b[0] % 40)]
    v = 0
    for c in b[1:]:
        v = (v << 7) | (c & 0x7f)
        if not c & 0x80:
            out.append(str(v))
            v = 0
    return ".".join(out)


def walk(b, i, end, depth, out, path):
    """Recursive DER walk. Appends (depth, tag, oid-or-text, byte-offset)."""
    while i + 1 < end:
        tag = b[i]
        if tag == 0x00:      # trailing alignment padding, not a TLV
            break
        ln, j = read_len(b, i + 1)
        if ln < 0 or j + ln > end:
            break
        body = b[j:j + ln]
        if tag == 0x06:
            oid = decode_oid(body)
            out.append((depth, "OID", "%s%s" % (oid, ""
                        if oid not in OIDS else "  (%s)" % OIDS[oid]), i))
            path.append(oid)
        elif tag in (0x13, 0x16, 0x0c, 0x14):
            out.append((depth, TAGNAME.get(tag, hex(tag)),
                        body.decode("latin1"), i))
        elif tag == 0x1e:
            try:
                out.append((depth, "BMPString",
                            body.decode("utf-16-be"), i))
            except UnicodeDecodeError:
                out.append((depth, "BMPString", repr(body), i))
        elif tag in (0x17, 0x18):
            out.append((depth, TAGNAME[tag], body.decode("latin1"), i))
        elif tag == 0x02 and ln <= 20:
            out.append((depth, "INTEGER",
                        "0x" + body.hex() if ln > 4
                        else str(int.from_bytes(body, "big")), i))
        elif tag in (0x30, 0x31) or (tag & 0xc0 == 0x80 and tag & 0x20):
            out.append((depth, TAGNAME.get(tag, "[%d]" % (tag & 0x1f)),
                        "(%d bytes)" % ln, i))
            walk(b, j, j + ln, depth + 1, out, path)
        i = j + ln
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--raw", action="store_true", help="write the blob out")
    ap.add_argument("--tree", action="store_true", help="print the whole DER")
    a = ap.parse_args()

    d = open(a.path, "rb").read()
    e = struct.unpack_from("<I", d, 0x3c)[0]
    optsz = struct.unpack_from("<H", d, e + 20)[0]
    ddoff = e + 24 + 96
    off, size = struct.unpack_from("<II", d, ddoff + 4 * 8)

    print("file            : %s" % a.path)
    print("file size       : %d" % len(d))
    if not off or not size:
        print("SECURITY data directory: empty -- the file is NOT signed")
        return
    print("cert table      : file offset %d (0x%X), %d bytes"
          % (off, off, size))
    print("tail after last section starts at %d, so the table is the tail"
          % off)
    ln, rev, ctype = struct.unpack_from("<IHH", d, off)
    print("WIN_CERTIFICATE : dwLength %d  wRevision 0x%04X  wCertificateType %d"
          % (ln, rev, ctype))
    print("                  (type 2 = PKCS#7 SignedData)")
    blob = d[off + 8: off + ln]
    print("PKCS#7 blob     : %d bytes, sha1 %s"
          % (len(blob), hashlib.sha1(blob).hexdigest()))
    if a.raw:
        open(a.path + ".p7b", "wb").write(blob)
        print("written to      : %s.p7b" % a.path)
    print()

    out, path = [], []
    walk(blob, 0, len(blob), 0, out, path)

    if a.tree:
        for depth, tag, text, i in out:
            print("%s%-14s %s" % ("  " * depth, tag, text[:110]))
        print()

    # Distinguished names: the RDN sets carry OID then value, adjacent.
    print("names found, in order of appearance:")
    prev_oid = None
    dn = []
    for depth, tag, text, i in out:
        if tag == "OID":
            prev_oid = text.split()[0]
        elif tag in ("PrintableString", "UTF8String", "IA5String",
                     "TeletexString", "BMPString") and prev_oid in OIDS \
                and OIDS[prev_oid] in ("CN", "O", "OU", "C", "L", "ST",
                                       "email", "serialNumber"):
            dn.append((OIDS[prev_oid], text))
            prev_oid = None
    seen = set()
    for k, v in dn:
        if (k, v) not in seen:
            seen.add((k, v))
            print("  %-14s %s" % (k, v))

    print()
    print("times found (UTCTime / GeneralizedTime):")
    for depth, tag, text, i in out:
        if tag in ("UTCTime", "GeneralizedTime"):
            print("  %-18s %s" % (tag, text))

    print()
    print("algorithm and purpose OIDs:")
    seen = set()
    for depth, tag, text, i in out:
        if tag == "OID" and "(" in text and text not in seen:
            seen.add(text)
            print("  %s" % text)

    print()
    print("strings that are not part of a name (opus info, urls):")
    for depth, tag, text, i in out:
        if tag in ("BMPString", "IA5String") and len(text) > 3:
            print("  %-14s %s" % (tag, text))


if __name__ == "__main__":
    main()
