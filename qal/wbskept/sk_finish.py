#!/usr/bin/env python3
"""SKEPTIC finish: record provenance, then free the waveform files.

/ was 98% full and SHARED with several live studies for the whole of this audit,
so row waveforms are deleted after extraction.  The sha256 of every .cir AND
every .prn is kept first, so any row can be re-run and bit-compared later.
"""
import glob, hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    dry = "--dry" in sys.argv
    prov, freed = {}, 0
    for pat in ("c_*.cir", "ck_*.cir", "p_*.cir", "warm_sk.cir"):
        for cir in sorted(glob.glob(os.path.join(HERE, pat))):
            b = os.path.basename(cir)
            e = dict(cir_sha256=sha(cir), cir_bytes=os.path.getsize(cir))
            for ext in (".prn", ".mt0"):
                f = cir + ext
                if os.path.exists(f):
                    e[ext[1:] + "_sha256"] = sha(f)
                    e[ext[1:] + "_bytes"] = os.path.getsize(f)
            prov[b] = e
    json.dump(prov, open(os.path.join(HERE, "SK_PROVENANCE.json"), "w"),
              indent=1)
    print("hashed %d decks -> SK_PROVENANCE.json" % len(prov))

    # .mt0 is TINY and is the measurement of record -- KEEP it.
    # .prn is large and only feeds the .prn-based extractions -- drop it.
    for prn in sorted(glob.glob(os.path.join(HERE, "*.cir.prn"))):
        sz = os.path.getsize(prn)
        if dry:
            print("would free %9.1f MB  %s" % (sz / 1e6, os.path.basename(prn)))
        else:
            os.remove(prn)
        freed += sz
    print("%s %.1f MB of .prn" % ("would free" if dry else "freed",
                                  freed / 1e6))
    with open(os.path.join(HERE, "SK_DISK_AFTER.txt"), "w") as f:
        f.write(subprocess.run(["df", "-h", "/", "/tmp"], capture_output=True,
                               text=True).stdout)
        f.write("\n")
        f.write(subprocess.run(["du", "-sh", HERE], capture_output=True,
                               text=True).stdout)
    print(open(os.path.join(HERE, "SK_DISK_AFTER.txt")).read())


if __name__ == "__main__":
    main()
