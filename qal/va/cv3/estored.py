"""Stored energy E(V) = int_0^V u*C_inc(u) du for the fitted Q(V) forms, by
quadrature. This is the EXACT stored energy of the simulated qal_bankcap at
voltage V (Q is a state function), used for the hop energy accounting. Shared
helper: importable by the hop runner."""
import math, json

def cinc(v, C0, CT, VK, W):
    z = (v - VK)/W
    s = 1.0/(1.0+math.exp(-z)) if z >= 0 else math.exp(z)/(1.0+math.exp(z))
    return C0 + CT*s

def estored(V, C0, CT, VK, W, n=4000):
    if V <= 0: return 0.0
    h = V/n; e = 0.0
    for i in range(n+1):
        u = i*h
        w = 0.5 if (i == 0 or i == n) else 1.0
        e += w*u*cinc(u, C0, CT, VK, W)*h
    return e

def qof(V, C0, CT, VK, W):
    z = (V - VK)/W
    sp = (z if z > 0 else 0.0) + math.log1p(math.exp(-abs(z)))
    return C0*V + CT*W*sp

if __name__ == "__main__":
    p = json.load(open("cv_fit.json"))
    A = p["bankA_full"]; B = p["deckB"]
    fa = (A["C0_fF"]*1e-15, A["CT_fF"]*1e-15, A["VK_V"], A["W_V"])
    fb = (B["C0_fF"]*1e-15, B["CT_fF"]*1e-15, B["VK_V"], B["W_V"])
    print("bank A (full):  E(1.0)=%.4f fJ  Q(1.0)=%.4f fC  E(0.0485)=%.5f fJ" %
          (estored(1.0,*fa)*1e15, qof(1.0,*fa)*1e15, estored(0.04853,*fa)*1e15))
    print("  => E released draining 1.0 -> 0.0485 = %.4f fJ" %
          ((estored(1.0,*fa)-estored(0.04853,*fa))*1e15))
    print("bank B (deckB): E(0.576)=%.4f fJ  Q(0.576)=%.4f fC" %
          (estored(0.57632,*fb)*1e15, qof(0.57632,*fb)*1e15))
    # measured anchors for reference
    print("  measured E_stored_full(1.0)=19.220 fJ (transistor slow ramp)")
