#include <cmath>
#include <cstdio>
#include <cstring>
struct VaeState { double V[16]; double Vt; };
inline double conjugate(double x){ return x; }
// Runtime (callback) params: the eval fetches these via _pcb("NAME")
// instead of a baked literal, so the compiler cannot const-fold them
// and Xyce .SAMPLING/AGAUSS reaches them live (no per-sample rebuild).
// The device shell installs _pms_cb via vae_set_param_cb; it returns
// the value for whichever instance is currently being evaluated. Until
// installed (or for an unknown name) we return 0.0, the Verilog-A
// default for a shift param like DELVTO.
static double (*_pms_cb)(const char*) = 0;
extern "C" void vae_set_param_cb(double (*f)(const char*)){ _pms_cb = f; }
static inline double _pcb(const char* n){ return _pms_cb ? _pms_cb(n) : 0.0; }
#define vae_eval _vae_eval_impl
#define vae_jacobian _vae_jacobian_impl
static const double temperature = 300.15;
#include "/usr/local/src/stat-sim/qal/muxbuck/vae_cache_muxbuck/vae_PSP103VA_da4dbd14fa92b21c.so.build/eval.cpp"
#undef vae_eval
#undef vae_jacobian
extern "C" void vae_eval(VaeState* s, double* F, double* Q){ _vae_eval_impl(s,F,Q); }
extern "C" void vae_jacobian(VaeState* s, double* dFdV, double* dQdV){
  int N = vae_n_nodes(); int NB = vae_n_branches();
  static double F0[256], Q0[256], Fp[256], Qp[256];
  _vae_eval_impl(s, F0, Q0);
  for (int j = 0; j < N; ++j) {
    VaeState sp = *s; double dv = 1e-4 * (std::fabs(s->V[j]) + 1.0);
    sp.V[j] += dv; _vae_eval_impl(&sp, Fp, Qp); double inv = 1.0 / dv;
    for (int i = 0; i < NB; ++i) {
      dFdV[i*N + j] = (Fp[i] - F0[i]) * inv;
      dQdV[i*N + j] = (Qp[i] - Q0[i]) * inv;
    }
  }
}
