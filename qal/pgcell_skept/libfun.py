#!/usr/bin/env python3
"""Extract each stdcell's Boolean function DIRECTLY from the PDK liberty file --
a source neither the Phase-1/2 run nor I authored.  Used to regenerate my own
cell models so the equivalence proof does not rest on the run's minicells.v."""
import re, sys, json

LIB = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/"
       "sg13g2_stdcell_typ_1p20V_25C.lib")


def blocks(src, kw):
    for m in re.finditer(r'\b%s \(([^)]*)\) \{' % kw, src):
        i = src.index('{', m.end() - 1)
        d = 0
        for j in range(i, len(src)):
            if src[j] == '{':
                d += 1
            elif src[j] == '}':
                d -= 1
                if d == 0:
                    break
        yield m.group(1).strip(), src[i + 1:j], m.start(), j


def cells():
    src = open(LIB).read()
    out = {}
    for name, blk, _, _ in blocks(src, 'cell'):
        pins = {}
        order = []
        for pn, pb, _, _ in blocks(blk, 'pin'):
            dirm = re.search(r'direction\s*:\s*(\w+)\s*;', pb)
            fn = re.search(r'function\s*:\s*"([^"]*)"\s*;', pb)
            pins[pn] = (dirm.group(1) if dirm else '?',
                        fn.group(1) if fn else None)
            order.append(pn)
        out[name] = (order, pins)
    return out


def lib_to_verilog(expr):
    """liberty function syntax -> verilog.  ops: ! ~ (not), * & (and),
    + | (or), ^ (xor), implicit AND by juxtaposition, postfix ' (not)."""
    e = expr.strip()
    # tokenise
    toks = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|[()!~*&+|^']|\S", e)
    out = []
    for t in toks:
        if t == "'":
            # postfix not: wrap previous atom
            j = len(out) - 1
            if out[j] == ')':
                d = 0
                while j >= 0:
                    if out[j] == ')':
                        d += 1
                    elif out[j] == '(':
                        d -= 1
                        if d == 0:
                            break
                    j -= 1
            out.insert(j, '~')
            continue
        if t == '*':
            t = '&'
        if t == '+':
            t = '|'
        if t == '!':
            t = '~'
        # implicit AND
        if out and (re.match(r'^[A-Za-z_]', t) or t == '(' or t == '~') and \
           (re.match(r'^[A-Za-z_]', out[-1]) or out[-1] == ')'):
            out.append('&')
        out.append(t)
    return ' '.join(out)


if __name__ == '__main__':
    C = cells()
    want = sys.argv[1:] or sorted(C)
    for c in want:
        order, pins = C[c]
        print(c, [(p, pins[p][0], pins[p][1]) for p in order])
