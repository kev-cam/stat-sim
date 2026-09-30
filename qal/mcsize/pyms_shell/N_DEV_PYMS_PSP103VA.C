// PyMS-generated Xyce device implementation: PSP103VA
#include "N_DEV_PYMS_PSP103VA.h"
#include <N_DEV_DeviceOptions.h>
#include <N_DEV_SolverState.h>
#include <N_DEV_ExternData.h>
#include <N_DEV_MatrixLoadData.h>
#include <N_DEV_Message.h>
#include <N_LAS_Vector.h>
#include <N_LAS_Matrix.h>
#include <cstring>
#include <cmath>
#ifdef VERSION
#undef VERSION
#endif
#ifdef PACKAGE_VERSION
#undef PACKAGE_VERSION
#endif
#ifdef PACKAGE_NAME
#undef PACKAGE_NAME
#endif
#ifdef PACKAGE_STRING
#undef PACKAGE_STRING
#endif
#ifdef MAJOR
#undef MAJOR
#endif
#ifdef MINOR
#undef MINOR
#endif
#include <cstdlib>
#include <cstdio>
#include <cctype>
#include <functional>
#include <fstream>
#include <sstream>
#include <sys/stat.h>

namespace Xyce { namespace Device { namespace PYMS_PSP103VA {

static const char *nodeNameArray[] = { "D", "G", "S", "B" };
const char **Traits::nodeNames() { return nodeNameArray; }

void Traits::loadInstanceParameters(ParametricData<Instance> &p) {
  p.addPar("L", 1e-05, &Instance::L)
    .setUnit(U_NONE)
    .setDescription("L");
  p.addPar("W", 1e-05, &Instance::W)
    .setUnit(U_NONE)
    .setDescription("W");
  p.addPar("SA", 0.0, &Instance::SA)
    .setUnit(U_NONE)
    .setDescription("SA");
  p.addPar("SB", 0.0, &Instance::SB)
    .setUnit(U_NONE)
    .setDescription("SB");
  p.addPar("SD", 0.0, &Instance::SD)
    .setUnit(U_NONE)
    .setDescription("SD");
  p.addPar("SCA", 0.0, &Instance::SCA)
    .setUnit(U_NONE)
    .setDescription("SCA");
  p.addPar("SCB", 0.0, &Instance::SCB)
    .setUnit(U_NONE)
    .setDescription("SCB");
  p.addPar("SCC", 0.0, &Instance::SCC)
    .setUnit(U_NONE)
    .setDescription("SCC");
  p.addPar("SC", 0.0, &Instance::SC)
    .setUnit(U_NONE)
    .setDescription("SC");
  p.addPar("NF", 1.0, &Instance::NF)
    .setUnit(U_NONE)
    .setDescription("NF");
  p.addPar("NGCON", 1.0, &Instance::NGCON)
    .setUnit(U_NONE)
    .setDescription("NGCON");
  p.addPar("XGW", 1e-07, &Instance::XGW)
    .setUnit(U_NONE)
    .setDescription("XGW");
  p.addPar("NRS", 0.0, &Instance::NRS)
    .setUnit(U_NONE)
    .setDescription("NRS");
  p.addPar("NRD", 0.0, &Instance::NRD)
    .setUnit(U_NONE)
    .setDescription("NRD");
  p.addPar("JW", 1e-06, &Instance::JW)
    .setUnit(U_NONE)
    .setDescription("JW");
  p.addPar("DELVTO", 0.0, &Instance::DELVTO)
    .setUnit(U_NONE)
    .setDescription("DELVTO");
  p.addPar("FACTUO", 1.0, &Instance::FACTUO)
    .setUnit(U_NONE)
    .setDescription("FACTUO");
  p.addPar("DELVTOEDGE", 0.0, &Instance::DELVTOEDGE)
    .setUnit(U_NONE)
    .setDescription("DELVTOEDGE");
  p.addPar("FACTUOEDGE", 1.0, &Instance::FACTUOEDGE)
    .setUnit(U_NONE)
    .setDescription("FACTUOEDGE");
  p.addPar("ABSOURCE", 1e-12, &Instance::ABSOURCE)
    .setUnit(U_NONE)
    .setDescription("ABSOURCE");
  p.addPar("LSSOURCE", 1e-06, &Instance::LSSOURCE)
    .setUnit(U_NONE)
    .setDescription("LSSOURCE");
  p.addPar("LGSOURCE", 1e-06, &Instance::LGSOURCE)
    .setUnit(U_NONE)
    .setDescription("LGSOURCE");
  p.addPar("ABDRAIN", 1e-12, &Instance::ABDRAIN)
    .setUnit(U_NONE)
    .setDescription("ABDRAIN");
  p.addPar("LSDRAIN", 1e-06, &Instance::LSDRAIN)
    .setUnit(U_NONE)
    .setDescription("LSDRAIN");
  p.addPar("LGDRAIN", 1e-06, &Instance::LGDRAIN)
    .setUnit(U_NONE)
    .setDescription("LGDRAIN");
  p.addPar("AS", 1e-12, &Instance::AS)
    .setUnit(U_NONE)
    .setDescription("AS");
  p.addPar("PS", 1e-06, &Instance::PS)
    .setUnit(U_NONE)
    .setDescription("PS");
  p.addPar("AD", 1e-12, &Instance::AD)
    .setUnit(U_NONE)
    .setDescription("AD");
  p.addPar("PD", 1e-06, &Instance::PD)
    .setUnit(U_NONE)
    .setDescription("PD");
  p.addPar("MULT", 1.0, &Instance::MULT)
    .setUnit(U_NONE)
    .setDescription("MULT");
  p.addPar("DTA", 0.0, &Instance::DTA)
    .setUnit(U_NONE)
    .setDescription("DTA");
}

void Traits::loadModelParameters(ParametricData<Model> &p) {
  p.addPar("LEVEL", 103.0, &Model::LEVEL)
    .setUnit(U_NONE)
    .setDescription("LEVEL");
  p.addPar("TYPE", 1.0, &Model::TYPE)
    .setUnit(U_NONE)
    .setDescription("TYPE");
  p.addPar("TR", 21.0, &Model::TR)
    .setUnit(U_NONE)
    .setDescription("TR");
  p.addPar("SWGEO", 1.0, &Model::SWGEO)
    .setUnit(U_NONE)
    .setDescription("SWGEO");
  p.addPar("SWIGATE", 0.0, &Model::SWIGATE)
    .setUnit(U_NONE)
    .setDescription("SWIGATE");
  p.addPar("SWIMPACT", 0.0, &Model::SWIMPACT)
    .setUnit(U_NONE)
    .setDescription("SWIMPACT");
  p.addPar("SWGIDL", 0.0, &Model::SWGIDL)
    .setUnit(U_NONE)
    .setDescription("SWGIDL");
  p.addPar("SWJUNCAP", 0.0, &Model::SWJUNCAP)
    .setUnit(U_NONE)
    .setDescription("SWJUNCAP");
  p.addPar("SWJUNASYM", 0.0, &Model::SWJUNASYM)
    .setUnit(U_NONE)
    .setDescription("SWJUNASYM");
  p.addPar("SWNUD", 0.0, &Model::SWNUD)
    .setUnit(U_NONE)
    .setDescription("SWNUD");
  p.addPar("SWEDGE", 0.0, &Model::SWEDGE)
    .setUnit(U_NONE)
    .setDescription("SWEDGE");
  p.addPar("SWDELVTAC", 0.0, &Model::SWDELVTAC)
    .setUnit(U_NONE)
    .setDescription("SWDELVTAC");
  p.addPar("SWIGN", 1.0, &Model::SWIGN)
    .setUnit(U_NONE)
    .setDescription("SWIGN");
  p.addPar("QMC", 1.0, &Model::QMC)
    .setUnit(U_NONE)
    .setDescription("QMC");
  p.addPar("VFB", -1.0, &Model::VFB)
    .setUnit(U_NONE)
    .setDescription("VFB");
  p.addPar("STVFB", 0.0005, &Model::STVFB)
    .setUnit(U_NONE)
    .setDescription("STVFB");
  p.addPar("TOX", 2e-09, &Model::TOX)
    .setUnit(U_NONE)
    .setDescription("TOX");
  p.addPar("EPSROX", 3.9, &Model::EPSROX)
    .setUnit(U_NONE)
    .setDescription("EPSROX");
  p.addPar("NEFF", 5e+23, &Model::NEFF)
    .setUnit(U_NONE)
    .setDescription("NEFF");
  p.addPar("FACNEFFAC", 1.0, &Model::FACNEFFAC)
    .setUnit(U_NONE)
    .setDescription("FACNEFFAC");
  p.addPar("GFACNUD", 1.0, &Model::GFACNUD)
    .setUnit(U_NONE)
    .setDescription("GFACNUD");
  p.addPar("VSBNUD", 0.0, &Model::VSBNUD)
    .setUnit(U_NONE)
    .setDescription("VSBNUD");
  p.addPar("DVSBNUD", 1.0, &Model::DVSBNUD)
    .setUnit(U_NONE)
    .setDescription("DVSBNUD");
  p.addPar("VNSUB", 0.0, &Model::VNSUB)
    .setUnit(U_NONE)
    .setDescription("VNSUB");
  p.addPar("NSLP", 0.05, &Model::NSLP)
    .setUnit(U_NONE)
    .setDescription("NSLP");
  p.addPar("DNSUB", 0.0, &Model::DNSUB)
    .setUnit(U_NONE)
    .setDescription("DNSUB");
  p.addPar("DPHIB", 0.0, &Model::DPHIB)
    .setUnit(U_NONE)
    .setDescription("DPHIB");
  p.addPar("DELVTAC", 0.0, &Model::DELVTAC)
    .setUnit(U_NONE)
    .setDescription("DELVTAC");
  p.addPar("NP", 1e+26, &Model::NP)
    .setUnit(U_NONE)
    .setDescription("NP");
  p.addPar("CT", 0.0, &Model::CT)
    .setUnit(U_NONE)
    .setDescription("CT");
  p.addPar("TOXOV", 2e-09, &Model::TOXOV)
    .setUnit(U_NONE)
    .setDescription("TOXOV");
  p.addPar("TOXOVD", 2e-09, &Model::TOXOVD)
    .setUnit(U_NONE)
    .setDescription("TOXOVD");
  p.addPar("NOV", 5e+25, &Model::NOV)
    .setUnit(U_NONE)
    .setDescription("NOV");
  p.addPar("NOVD", 5e+25, &Model::NOVD)
    .setUnit(U_NONE)
    .setDescription("NOVD");
  p.addPar("CF", 0.0, &Model::CF)
    .setUnit(U_NONE)
    .setDescription("CF");
  p.addPar("CFD", 0.0, &Model::CFD)
    .setUnit(U_NONE)
    .setDescription("CFD");
  p.addPar("CFB", 0.0, &Model::CFB)
    .setUnit(U_NONE)
    .setDescription("CFB");
  p.addPar("PSCE", 0.0, &Model::PSCE)
    .setUnit(U_NONE)
    .setDescription("PSCE");
  p.addPar("PSCEB", 0.0, &Model::PSCEB)
    .setUnit(U_NONE)
    .setDescription("PSCEB");
  p.addPar("PSCED", 0.0, &Model::PSCED)
    .setUnit(U_NONE)
    .setDescription("PSCED");
  p.addPar("BETN", 0.07, &Model::BETN)
    .setUnit(U_NONE)
    .setDescription("BETN");
  p.addPar("STBET", 1.0, &Model::STBET)
    .setUnit(U_NONE)
    .setDescription("STBET");
  p.addPar("MUE", 0.5, &Model::MUE)
    .setUnit(U_NONE)
    .setDescription("MUE");
  p.addPar("STMUE", 0.0, &Model::STMUE)
    .setUnit(U_NONE)
    .setDescription("STMUE");
  p.addPar("THEMU", 1.5, &Model::THEMU)
    .setUnit(U_NONE)
    .setDescription("THEMU");
  p.addPar("STTHEMU", 1.5, &Model::STTHEMU)
    .setUnit(U_NONE)
    .setDescription("STTHEMU");
  p.addPar("CS", 0.0, &Model::CS)
    .setUnit(U_NONE)
    .setDescription("CS");
  p.addPar("STCS", 0.0, &Model::STCS)
    .setUnit(U_NONE)
    .setDescription("STCS");
  p.addPar("XCOR", 0.0, &Model::XCOR)
    .setUnit(U_NONE)
    .setDescription("XCOR");
  p.addPar("STXCOR", 0.0, &Model::STXCOR)
    .setUnit(U_NONE)
    .setDescription("STXCOR");
  p.addPar("FETA", 1.0, &Model::FETA)
    .setUnit(U_NONE)
    .setDescription("FETA");
  p.addPar("RS", 30.0, &Model::RS)
    .setUnit(U_NONE)
    .setDescription("RS");
  p.addPar("STRS", 1.0, &Model::STRS)
    .setUnit(U_NONE)
    .setDescription("STRS");
  p.addPar("RSB", 0.0, &Model::RSB)
    .setUnit(U_NONE)
    .setDescription("RSB");
  p.addPar("RSG", 0.0, &Model::RSG)
    .setUnit(U_NONE)
    .setDescription("RSG");
  p.addPar("THESAT", 1.0, &Model::THESAT)
    .setUnit(U_NONE)
    .setDescription("THESAT");
  p.addPar("STTHESAT", 1.0, &Model::STTHESAT)
    .setUnit(U_NONE)
    .setDescription("STTHESAT");
  p.addPar("THESATB", 0.0, &Model::THESATB)
    .setUnit(U_NONE)
    .setDescription("THESATB");
  p.addPar("THESATG", 0.0, &Model::THESATG)
    .setUnit(U_NONE)
    .setDescription("THESATG");
  p.addPar("AX", 3.0, &Model::AX)
    .setUnit(U_NONE)
    .setDescription("AX");
  p.addPar("ALP", 0.01, &Model::ALP)
    .setUnit(U_NONE)
    .setDescription("ALP");
  p.addPar("ALP1", 0.0, &Model::ALP1)
    .setUnit(U_NONE)
    .setDescription("ALP1");
  p.addPar("ALP2", 0.0, &Model::ALP2)
    .setUnit(U_NONE)
    .setDescription("ALP2");
  p.addPar("VP", 0.05, &Model::VP)
    .setUnit(U_NONE)
    .setDescription("VP");
  p.addPar("A1", 1.0, &Model::A1)
    .setUnit(U_NONE)
    .setDescription("A1");
  p.addPar("A2", 10.0, &Model::A2)
    .setUnit(U_NONE)
    .setDescription("A2");
  p.addPar("STA2", 0.0, &Model::STA2)
    .setUnit(U_NONE)
    .setDescription("STA2");
  p.addPar("A3", 1.0, &Model::A3)
    .setUnit(U_NONE)
    .setDescription("A3");
  p.addPar("A4", 0.0, &Model::A4)
    .setUnit(U_NONE)
    .setDescription("A4");
  p.addPar("GCO", 0.0, &Model::GCO)
    .setUnit(U_NONE)
    .setDescription("GCO");
  p.addPar("IGINV", 0.0, &Model::IGINV)
    .setUnit(U_NONE)
    .setDescription("IGINV");
  p.addPar("IGOV", 0.0, &Model::IGOV)
    .setUnit(U_NONE)
    .setDescription("IGOV");
  p.addPar("IGOVD", 0.0, &Model::IGOVD)
    .setUnit(U_NONE)
    .setDescription("IGOVD");
  p.addPar("STIG", 2.0, &Model::STIG)
    .setUnit(U_NONE)
    .setDescription("STIG");
  p.addPar("GC2", 0.375, &Model::GC2)
    .setUnit(U_NONE)
    .setDescription("GC2");
  p.addPar("GC3", 0.063, &Model::GC3)
    .setUnit(U_NONE)
    .setDescription("GC3");
  p.addPar("CHIB", 3.1, &Model::CHIB)
    .setUnit(U_NONE)
    .setDescription("CHIB");
  p.addPar("AGIDL", 0.0, &Model::AGIDL)
    .setUnit(U_NONE)
    .setDescription("AGIDL");
  p.addPar("AGIDLD", 0.0, &Model::AGIDLD)
    .setUnit(U_NONE)
    .setDescription("AGIDLD");
  p.addPar("BGIDL", 41.0, &Model::BGIDL)
    .setUnit(U_NONE)
    .setDescription("BGIDL");
  p.addPar("BGIDLD", 41.0, &Model::BGIDLD)
    .setUnit(U_NONE)
    .setDescription("BGIDLD");
  p.addPar("STBGIDL", 0.0, &Model::STBGIDL)
    .setUnit(U_NONE)
    .setDescription("STBGIDL");
  p.addPar("STBGIDLD", 0.0, &Model::STBGIDLD)
    .setUnit(U_NONE)
    .setDescription("STBGIDLD");
  p.addPar("CGIDL", 0.0, &Model::CGIDL)
    .setUnit(U_NONE)
    .setDescription("CGIDL");
  p.addPar("CGIDLD", 0.0, &Model::CGIDLD)
    .setUnit(U_NONE)
    .setDescription("CGIDLD");
  p.addPar("COX", 1e-14, &Model::COX)
    .setUnit(U_NONE)
    .setDescription("COX");
  p.addPar("CGOV", 1e-15, &Model::CGOV)
    .setUnit(U_NONE)
    .setDescription("CGOV");
  p.addPar("CGOVD", 1e-15, &Model::CGOVD)
    .setUnit(U_NONE)
    .setDescription("CGOVD");
  p.addPar("CGBOV", 0.0, &Model::CGBOV)
    .setUnit(U_NONE)
    .setDescription("CGBOV");
  p.addPar("CFR", 0.0, &Model::CFR)
    .setUnit(U_NONE)
    .setDescription("CFR");
  p.addPar("CFRD", 0.0, &Model::CFRD)
    .setUnit(U_NONE)
    .setDescription("CFRD");
  p.addPar("FNT", 1.0, &Model::FNT)
    .setUnit(U_NONE)
    .setDescription("FNT");
  p.addPar("FNTEXC", 0.0, &Model::FNTEXC)
    .setUnit(U_NONE)
    .setDescription("FNTEXC");
  p.addPar("NFA", 8e+22, &Model::NFA)
    .setUnit(U_NONE)
    .setDescription("NFA");
  p.addPar("NFB", 30000000.0, &Model::NFB)
    .setUnit(U_NONE)
    .setDescription("NFB");
  p.addPar("NFC", 0.0, &Model::NFC)
    .setUnit(U_NONE)
    .setDescription("NFC");
  p.addPar("EF", 1.0, &Model::EF)
    .setUnit(U_NONE)
    .setDescription("EF");
  p.addPar("VFBEDGE", -1.0, &Model::VFBEDGE)
    .setUnit(U_NONE)
    .setDescription("VFBEDGE");
  p.addPar("STVFBEDGE", 0.0005, &Model::STVFBEDGE)
    .setUnit(U_NONE)
    .setDescription("STVFBEDGE");
  p.addPar("DPHIBEDGE", 0.0, &Model::DPHIBEDGE)
    .setUnit(U_NONE)
    .setDescription("DPHIBEDGE");
  p.addPar("NEFFEDGE", 5e+23, &Model::NEFFEDGE)
    .setUnit(U_NONE)
    .setDescription("NEFFEDGE");
  p.addPar("CTEDGE", 0.0, &Model::CTEDGE)
    .setUnit(U_NONE)
    .setDescription("CTEDGE");
  p.addPar("BETNEDGE", 0.0005, &Model::BETNEDGE)
    .setUnit(U_NONE)
    .setDescription("BETNEDGE");
  p.addPar("STBETEDGE", 1.0, &Model::STBETEDGE)
    .setUnit(U_NONE)
    .setDescription("STBETEDGE");
  p.addPar("PSCEEDGE", 0.0, &Model::PSCEEDGE)
    .setUnit(U_NONE)
    .setDescription("PSCEEDGE");
  p.addPar("PSCEBEDGE", 0.0, &Model::PSCEBEDGE)
    .setUnit(U_NONE)
    .setDescription("PSCEBEDGE");
  p.addPar("PSCEDEDGE", 0.0, &Model::PSCEDEDGE)
    .setUnit(U_NONE)
    .setDescription("PSCEDEDGE");
  p.addPar("CFEDGE", 0.0, &Model::CFEDGE)
    .setUnit(U_NONE)
    .setDescription("CFEDGE");
  p.addPar("CFDEDGE", 0.0, &Model::CFDEDGE)
    .setUnit(U_NONE)
    .setDescription("CFDEDGE");
  p.addPar("CFBEDGE", 0.0, &Model::CFBEDGE)
    .setUnit(U_NONE)
    .setDescription("CFBEDGE");
  p.addPar("FNTEDGE", 1.0, &Model::FNTEDGE)
    .setUnit(U_NONE)
    .setDescription("FNTEDGE");
  p.addPar("NFAEDGE", 8e+22, &Model::NFAEDGE)
    .setUnit(U_NONE)
    .setDescription("NFAEDGE");
  p.addPar("NFBEDGE", 30000000.0, &Model::NFBEDGE)
    .setUnit(U_NONE)
    .setDescription("NFBEDGE");
  p.addPar("NFCEDGE", 0.0, &Model::NFCEDGE)
    .setUnit(U_NONE)
    .setDescription("NFCEDGE");
  p.addPar("EFEDGE", 1.0, &Model::EFEDGE)
    .setUnit(U_NONE)
    .setDescription("EFEDGE");
  p.addPar("RG", 0.0, &Model::RG)
    .setUnit(U_NONE)
    .setDescription("RG");
  p.addPar("RSE", 0.0, &Model::RSE)
    .setUnit(U_NONE)
    .setDescription("RSE");
  p.addPar("RDE", 0.0, &Model::RDE)
    .setUnit(U_NONE)
    .setDescription("RDE");
  p.addPar("RBULK", 0.0, &Model::RBULK)
    .setUnit(U_NONE)
    .setDescription("RBULK");
  p.addPar("RWELL", 0.0, &Model::RWELL)
    .setUnit(U_NONE)
    .setDescription("RWELL");
  p.addPar("RJUNS", 0.0, &Model::RJUNS)
    .setUnit(U_NONE)
    .setDescription("RJUNS");
  p.addPar("RJUND", 0.0, &Model::RJUND)
    .setUnit(U_NONE)
    .setDescription("RJUND");
  p.addPar("POVFB", -1.0, &Model::POVFB)
    .setUnit(U_NONE)
    .setDescription("POVFB");
  p.addPar("PLVFB", 0.0, &Model::PLVFB)
    .setUnit(U_NONE)
    .setDescription("PLVFB");
  p.addPar("PWVFB", 0.0, &Model::PWVFB)
    .setUnit(U_NONE)
    .setDescription("PWVFB");
  p.addPar("PLWVFB", 0.0, &Model::PLWVFB)
    .setUnit(U_NONE)
    .setDescription("PLWVFB");
  p.addPar("POSTVFB", 0.0005, &Model::POSTVFB)
    .setUnit(U_NONE)
    .setDescription("POSTVFB");
  p.addPar("PLSTVFB", 0.0, &Model::PLSTVFB)
    .setUnit(U_NONE)
    .setDescription("PLSTVFB");
  p.addPar("PWSTVFB", 0.0, &Model::PWSTVFB)
    .setUnit(U_NONE)
    .setDescription("PWSTVFB");
  p.addPar("PLWSTVFB", 0.0, &Model::PLWSTVFB)
    .setUnit(U_NONE)
    .setDescription("PLWSTVFB");
  p.addPar("POTOX", 2e-09, &Model::POTOX)
    .setUnit(U_NONE)
    .setDescription("POTOX");
  p.addPar("POEPSROX", 3.9, &Model::POEPSROX)
    .setUnit(U_NONE)
    .setDescription("POEPSROX");
  p.addPar("PONEFF", 5e+23, &Model::PONEFF)
    .setUnit(U_NONE)
    .setDescription("PONEFF");
  p.addPar("PLNEFF", 0.0, &Model::PLNEFF)
    .setUnit(U_NONE)
    .setDescription("PLNEFF");
  p.addPar("PWNEFF", 0.0, &Model::PWNEFF)
    .setUnit(U_NONE)
    .setDescription("PWNEFF");
  p.addPar("PLWNEFF", 0.0, &Model::PLWNEFF)
    .setUnit(U_NONE)
    .setDescription("PLWNEFF");
  p.addPar("POFACNEFFAC", 1.0, &Model::POFACNEFFAC)
    .setUnit(U_NONE)
    .setDescription("POFACNEFFAC");
  p.addPar("PLFACNEFFAC", 0.0, &Model::PLFACNEFFAC)
    .setUnit(U_NONE)
    .setDescription("PLFACNEFFAC");
  p.addPar("PWFACNEFFAC", 0.0, &Model::PWFACNEFFAC)
    .setUnit(U_NONE)
    .setDescription("PWFACNEFFAC");
  p.addPar("PLWFACNEFFAC", 0.0, &Model::PLWFACNEFFAC)
    .setUnit(U_NONE)
    .setDescription("PLWFACNEFFAC");
  p.addPar("POGFACNUD", 1.0, &Model::POGFACNUD)
    .setUnit(U_NONE)
    .setDescription("POGFACNUD");
  p.addPar("PLGFACNUD", 0.0, &Model::PLGFACNUD)
    .setUnit(U_NONE)
    .setDescription("PLGFACNUD");
  p.addPar("PWGFACNUD", 0.0, &Model::PWGFACNUD)
    .setUnit(U_NONE)
    .setDescription("PWGFACNUD");
  p.addPar("PLWGFACNUD", 0.0, &Model::PLWGFACNUD)
    .setUnit(U_NONE)
    .setDescription("PLWGFACNUD");
  p.addPar("POVSBNUD", 0.0, &Model::POVSBNUD)
    .setUnit(U_NONE)
    .setDescription("POVSBNUD");
  p.addPar("PODVSBNUD", 1.0, &Model::PODVSBNUD)
    .setUnit(U_NONE)
    .setDescription("PODVSBNUD");
  p.addPar("POVNSUB", 0.0, &Model::POVNSUB)
    .setUnit(U_NONE)
    .setDescription("POVNSUB");
  p.addPar("PONSLP", 0.05, &Model::PONSLP)
    .setUnit(U_NONE)
    .setDescription("PONSLP");
  p.addPar("PODNSUB", 0.0, &Model::PODNSUB)
    .setUnit(U_NONE)
    .setDescription("PODNSUB");
  p.addPar("PODPHIB", 0.0, &Model::PODPHIB)
    .setUnit(U_NONE)
    .setDescription("PODPHIB");
  p.addPar("PLDPHIB", 0.0, &Model::PLDPHIB)
    .setUnit(U_NONE)
    .setDescription("PLDPHIB");
  p.addPar("PWDPHIB", 0.0, &Model::PWDPHIB)
    .setUnit(U_NONE)
    .setDescription("PWDPHIB");
  p.addPar("PLWDPHIB", 0.0, &Model::PLWDPHIB)
    .setUnit(U_NONE)
    .setDescription("PLWDPHIB");
  p.addPar("PODELVTAC", 0.0, &Model::PODELVTAC)
    .setUnit(U_NONE)
    .setDescription("PODELVTAC");
  p.addPar("PLDELVTAC", 0.0, &Model::PLDELVTAC)
    .setUnit(U_NONE)
    .setDescription("PLDELVTAC");
  p.addPar("PWDELVTAC", 0.0, &Model::PWDELVTAC)
    .setUnit(U_NONE)
    .setDescription("PWDELVTAC");
  p.addPar("PLWDELVTAC", 0.0, &Model::PLWDELVTAC)
    .setUnit(U_NONE)
    .setDescription("PLWDELVTAC");
  p.addPar("PONP", 1e+26, &Model::PONP)
    .setUnit(U_NONE)
    .setDescription("PONP");
  p.addPar("PLNP", 0.0, &Model::PLNP)
    .setUnit(U_NONE)
    .setDescription("PLNP");
  p.addPar("PWNP", 0.0, &Model::PWNP)
    .setUnit(U_NONE)
    .setDescription("PWNP");
  p.addPar("PLWNP", 0.0, &Model::PLWNP)
    .setUnit(U_NONE)
    .setDescription("PLWNP");
  p.addPar("POCT", 0.0, &Model::POCT)
    .setUnit(U_NONE)
    .setDescription("POCT");
  p.addPar("PLCT", 0.0, &Model::PLCT)
    .setUnit(U_NONE)
    .setDescription("PLCT");
  p.addPar("PWCT", 0.0, &Model::PWCT)
    .setUnit(U_NONE)
    .setDescription("PWCT");
  p.addPar("PLWCT", 0.0, &Model::PLWCT)
    .setUnit(U_NONE)
    .setDescription("PLWCT");
  p.addPar("POTOXOV", 2e-09, &Model::POTOXOV)
    .setUnit(U_NONE)
    .setDescription("POTOXOV");
  p.addPar("POTOXOVD", 2e-09, &Model::POTOXOVD)
    .setUnit(U_NONE)
    .setDescription("POTOXOVD");
  p.addPar("PONOV", 5e+25, &Model::PONOV)
    .setUnit(U_NONE)
    .setDescription("PONOV");
  p.addPar("PLNOV", 0.0, &Model::PLNOV)
    .setUnit(U_NONE)
    .setDescription("PLNOV");
  p.addPar("PWNOV", 0.0, &Model::PWNOV)
    .setUnit(U_NONE)
    .setDescription("PWNOV");
  p.addPar("PLWNOV", 0.0, &Model::PLWNOV)
    .setUnit(U_NONE)
    .setDescription("PLWNOV");
  p.addPar("PONOVD", 5e+25, &Model::PONOVD)
    .setUnit(U_NONE)
    .setDescription("PONOVD");
  p.addPar("PLNOVD", 0.0, &Model::PLNOVD)
    .setUnit(U_NONE)
    .setDescription("PLNOVD");
  p.addPar("PWNOVD", 0.0, &Model::PWNOVD)
    .setUnit(U_NONE)
    .setDescription("PWNOVD");
  p.addPar("PLWNOVD", 0.0, &Model::PLWNOVD)
    .setUnit(U_NONE)
    .setDescription("PLWNOVD");
  p.addPar("POCF", 0.0, &Model::POCF)
    .setUnit(U_NONE)
    .setDescription("POCF");
  p.addPar("PLCF", 0.0, &Model::PLCF)
    .setUnit(U_NONE)
    .setDescription("PLCF");
  p.addPar("PWCF", 0.0, &Model::PWCF)
    .setUnit(U_NONE)
    .setDescription("PWCF");
  p.addPar("PLWCF", 0.0, &Model::PLWCF)
    .setUnit(U_NONE)
    .setDescription("PLWCF");
  p.addPar("POCFD", 0.0, &Model::POCFD)
    .setUnit(U_NONE)
    .setDescription("POCFD");
  p.addPar("POCFB", 0.0, &Model::POCFB)
    .setUnit(U_NONE)
    .setDescription("POCFB");
  p.addPar("POPSCE", 0.0, &Model::POPSCE)
    .setUnit(U_NONE)
    .setDescription("POPSCE");
  p.addPar("PLPSCE", 0.0, &Model::PLPSCE)
    .setUnit(U_NONE)
    .setDescription("PLPSCE");
  p.addPar("PWPSCE", 0.0, &Model::PWPSCE)
    .setUnit(U_NONE)
    .setDescription("PWPSCE");
  p.addPar("PLWPSCE", 0.0, &Model::PLWPSCE)
    .setUnit(U_NONE)
    .setDescription("PLWPSCE");
  p.addPar("POPSCEB", 0.0, &Model::POPSCEB)
    .setUnit(U_NONE)
    .setDescription("POPSCEB");
  p.addPar("POPSCED", 0.0, &Model::POPSCED)
    .setUnit(U_NONE)
    .setDescription("POPSCED");
  p.addPar("POBETN", 0.07, &Model::POBETN)
    .setUnit(U_NONE)
    .setDescription("POBETN");
  p.addPar("PLBETN", 0.0, &Model::PLBETN)
    .setUnit(U_NONE)
    .setDescription("PLBETN");
  p.addPar("PWBETN", 0.0, &Model::PWBETN)
    .setUnit(U_NONE)
    .setDescription("PWBETN");
  p.addPar("PLWBETN", 0.0, &Model::PLWBETN)
    .setUnit(U_NONE)
    .setDescription("PLWBETN");
  p.addPar("POSTBET", 1.0, &Model::POSTBET)
    .setUnit(U_NONE)
    .setDescription("POSTBET");
  p.addPar("PLSTBET", 0.0, &Model::PLSTBET)
    .setUnit(U_NONE)
    .setDescription("PLSTBET");
  p.addPar("PWSTBET", 0.0, &Model::PWSTBET)
    .setUnit(U_NONE)
    .setDescription("PWSTBET");
  p.addPar("PLWSTBET", 0.0, &Model::PLWSTBET)
    .setUnit(U_NONE)
    .setDescription("PLWSTBET");
  p.addPar("POMUE", 0.5, &Model::POMUE)
    .setUnit(U_NONE)
    .setDescription("POMUE");
  p.addPar("PLMUE", 0.0, &Model::PLMUE)
    .setUnit(U_NONE)
    .setDescription("PLMUE");
  p.addPar("PWMUE", 0.0, &Model::PWMUE)
    .setUnit(U_NONE)
    .setDescription("PWMUE");
  p.addPar("PLWMUE", 0.0, &Model::PLWMUE)
    .setUnit(U_NONE)
    .setDescription("PLWMUE");
  p.addPar("POSTMUE", 0.0, &Model::POSTMUE)
    .setUnit(U_NONE)
    .setDescription("POSTMUE");
  p.addPar("POTHEMU", 1.5, &Model::POTHEMU)
    .setUnit(U_NONE)
    .setDescription("POTHEMU");
  p.addPar("POSTTHEMU", 1.5, &Model::POSTTHEMU)
    .setUnit(U_NONE)
    .setDescription("POSTTHEMU");
  p.addPar("POCS", 0.0, &Model::POCS)
    .setUnit(U_NONE)
    .setDescription("POCS");
  p.addPar("PLCS", 0.0, &Model::PLCS)
    .setUnit(U_NONE)
    .setDescription("PLCS");
  p.addPar("PWCS", 0.0, &Model::PWCS)
    .setUnit(U_NONE)
    .setDescription("PWCS");
  p.addPar("PLWCS", 0.0, &Model::PLWCS)
    .setUnit(U_NONE)
    .setDescription("PLWCS");
  p.addPar("POSTCS", 0.0, &Model::POSTCS)
    .setUnit(U_NONE)
    .setDescription("POSTCS");
  p.addPar("POXCOR", 0.0, &Model::POXCOR)
    .setUnit(U_NONE)
    .setDescription("POXCOR");
  p.addPar("PLXCOR", 0.0, &Model::PLXCOR)
    .setUnit(U_NONE)
    .setDescription("PLXCOR");
  p.addPar("PWXCOR", 0.0, &Model::PWXCOR)
    .setUnit(U_NONE)
    .setDescription("PWXCOR");
  p.addPar("PLWXCOR", 0.0, &Model::PLWXCOR)
    .setUnit(U_NONE)
    .setDescription("PLWXCOR");
  p.addPar("POSTXCOR", 0.0, &Model::POSTXCOR)
    .setUnit(U_NONE)
    .setDescription("POSTXCOR");
  p.addPar("POFETA", 1.0, &Model::POFETA)
    .setUnit(U_NONE)
    .setDescription("POFETA");
  p.addPar("PORS", 30.0, &Model::PORS)
    .setUnit(U_NONE)
    .setDescription("PORS");
  p.addPar("PLRS", 0.0, &Model::PLRS)
    .setUnit(U_NONE)
    .setDescription("PLRS");
  p.addPar("PWRS", 0.0, &Model::PWRS)
    .setUnit(U_NONE)
    .setDescription("PWRS");
  p.addPar("PLWRS", 0.0, &Model::PLWRS)
    .setUnit(U_NONE)
    .setDescription("PLWRS");
  p.addPar("POSTRS", 1.0, &Model::POSTRS)
    .setUnit(U_NONE)
    .setDescription("POSTRS");
  p.addPar("PORSB", 0.0, &Model::PORSB)
    .setUnit(U_NONE)
    .setDescription("PORSB");
  p.addPar("PORSG", 0.0, &Model::PORSG)
    .setUnit(U_NONE)
    .setDescription("PORSG");
  p.addPar("POTHESAT", 1.0, &Model::POTHESAT)
    .setUnit(U_NONE)
    .setDescription("POTHESAT");
  p.addPar("PLTHESAT", 0.0, &Model::PLTHESAT)
    .setUnit(U_NONE)
    .setDescription("PLTHESAT");
  p.addPar("PWTHESAT", 0.0, &Model::PWTHESAT)
    .setUnit(U_NONE)
    .setDescription("PWTHESAT");
  p.addPar("PLWTHESAT", 0.0, &Model::PLWTHESAT)
    .setUnit(U_NONE)
    .setDescription("PLWTHESAT");
  p.addPar("POSTTHESAT", 1.0, &Model::POSTTHESAT)
    .setUnit(U_NONE)
    .setDescription("POSTTHESAT");
  p.addPar("PLSTTHESAT", 0.0, &Model::PLSTTHESAT)
    .setUnit(U_NONE)
    .setDescription("PLSTTHESAT");
  p.addPar("PWSTTHESAT", 0.0, &Model::PWSTTHESAT)
    .setUnit(U_NONE)
    .setDescription("PWSTTHESAT");
  p.addPar("PLWSTTHESAT", 0.0, &Model::PLWSTTHESAT)
    .setUnit(U_NONE)
    .setDescription("PLWSTTHESAT");
  p.addPar("POTHESATB", 0.0, &Model::POTHESATB)
    .setUnit(U_NONE)
    .setDescription("POTHESATB");
  p.addPar("PLTHESATB", 0.0, &Model::PLTHESATB)
    .setUnit(U_NONE)
    .setDescription("PLTHESATB");
  p.addPar("PWTHESATB", 0.0, &Model::PWTHESATB)
    .setUnit(U_NONE)
    .setDescription("PWTHESATB");
  p.addPar("PLWTHESATB", 0.0, &Model::PLWTHESATB)
    .setUnit(U_NONE)
    .setDescription("PLWTHESATB");
  p.addPar("POTHESATG", 0.0, &Model::POTHESATG)
    .setUnit(U_NONE)
    .setDescription("POTHESATG");
  p.addPar("PLTHESATG", 0.0, &Model::PLTHESATG)
    .setUnit(U_NONE)
    .setDescription("PLTHESATG");
  p.addPar("PWTHESATG", 0.0, &Model::PWTHESATG)
    .setUnit(U_NONE)
    .setDescription("PWTHESATG");
  p.addPar("PLWTHESATG", 0.0, &Model::PLWTHESATG)
    .setUnit(U_NONE)
    .setDescription("PLWTHESATG");
  p.addPar("POAX", 3.0, &Model::POAX)
    .setUnit(U_NONE)
    .setDescription("POAX");
  p.addPar("PLAX", 0.0, &Model::PLAX)
    .setUnit(U_NONE)
    .setDescription("PLAX");
  p.addPar("PWAX", 0.0, &Model::PWAX)
    .setUnit(U_NONE)
    .setDescription("PWAX");
  p.addPar("PLWAX", 0.0, &Model::PLWAX)
    .setUnit(U_NONE)
    .setDescription("PLWAX");
  p.addPar("POALP", 0.01, &Model::POALP)
    .setUnit(U_NONE)
    .setDescription("POALP");
  p.addPar("PLALP", 0.0, &Model::PLALP)
    .setUnit(U_NONE)
    .setDescription("PLALP");
  p.addPar("PWALP", 0.0, &Model::PWALP)
    .setUnit(U_NONE)
    .setDescription("PWALP");
  p.addPar("PLWALP", 0.0, &Model::PLWALP)
    .setUnit(U_NONE)
    .setDescription("PLWALP");
  p.addPar("POALP1", 0.0, &Model::POALP1)
    .setUnit(U_NONE)
    .setDescription("POALP1");
  p.addPar("PLALP1", 0.0, &Model::PLALP1)
    .setUnit(U_NONE)
    .setDescription("PLALP1");
  p.addPar("PWALP1", 0.0, &Model::PWALP1)
    .setUnit(U_NONE)
    .setDescription("PWALP1");
  p.addPar("PLWALP1", 0.0, &Model::PLWALP1)
    .setUnit(U_NONE)
    .setDescription("PLWALP1");
  p.addPar("POALP2", 0.0, &Model::POALP2)
    .setUnit(U_NONE)
    .setDescription("POALP2");
  p.addPar("PLALP2", 0.0, &Model::PLALP2)
    .setUnit(U_NONE)
    .setDescription("PLALP2");
  p.addPar("PWALP2", 0.0, &Model::PWALP2)
    .setUnit(U_NONE)
    .setDescription("PWALP2");
  p.addPar("PLWALP2", 0.0, &Model::PLWALP2)
    .setUnit(U_NONE)
    .setDescription("PLWALP2");
  p.addPar("POVP", 0.05, &Model::POVP)
    .setUnit(U_NONE)
    .setDescription("POVP");
  p.addPar("POA1", 1.0, &Model::POA1)
    .setUnit(U_NONE)
    .setDescription("POA1");
  p.addPar("PLA1", 0.0, &Model::PLA1)
    .setUnit(U_NONE)
    .setDescription("PLA1");
  p.addPar("PWA1", 0.0, &Model::PWA1)
    .setUnit(U_NONE)
    .setDescription("PWA1");
  p.addPar("PLWA1", 0.0, &Model::PLWA1)
    .setUnit(U_NONE)
    .setDescription("PLWA1");
  p.addPar("POA2", 10.0, &Model::POA2)
    .setUnit(U_NONE)
    .setDescription("POA2");
  p.addPar("POSTA2", 0.0, &Model::POSTA2)
    .setUnit(U_NONE)
    .setDescription("POSTA2");
  p.addPar("POA3", 1.0, &Model::POA3)
    .setUnit(U_NONE)
    .setDescription("POA3");
  p.addPar("PLA3", 0.0, &Model::PLA3)
    .setUnit(U_NONE)
    .setDescription("PLA3");
  p.addPar("PWA3", 0.0, &Model::PWA3)
    .setUnit(U_NONE)
    .setDescription("PWA3");
  p.addPar("PLWA3", 0.0, &Model::PLWA3)
    .setUnit(U_NONE)
    .setDescription("PLWA3");
  p.addPar("POA4", 0.0, &Model::POA4)
    .setUnit(U_NONE)
    .setDescription("POA4");
  p.addPar("PLA4", 0.0, &Model::PLA4)
    .setUnit(U_NONE)
    .setDescription("PLA4");
  p.addPar("PWA4", 0.0, &Model::PWA4)
    .setUnit(U_NONE)
    .setDescription("PWA4");
  p.addPar("PLWA4", 0.0, &Model::PLWA4)
    .setUnit(U_NONE)
    .setDescription("PLWA4");
  p.addPar("POGCO", 0.0, &Model::POGCO)
    .setUnit(U_NONE)
    .setDescription("POGCO");
  p.addPar("POIGINV", 0.0, &Model::POIGINV)
    .setUnit(U_NONE)
    .setDescription("POIGINV");
  p.addPar("PLIGINV", 0.0, &Model::PLIGINV)
    .setUnit(U_NONE)
    .setDescription("PLIGINV");
  p.addPar("PWIGINV", 0.0, &Model::PWIGINV)
    .setUnit(U_NONE)
    .setDescription("PWIGINV");
  p.addPar("PLWIGINV", 0.0, &Model::PLWIGINV)
    .setUnit(U_NONE)
    .setDescription("PLWIGINV");
  p.addPar("POIGOV", 0.0, &Model::POIGOV)
    .setUnit(U_NONE)
    .setDescription("POIGOV");
  p.addPar("PLIGOV", 0.0, &Model::PLIGOV)
    .setUnit(U_NONE)
    .setDescription("PLIGOV");
  p.addPar("PWIGOV", 0.0, &Model::PWIGOV)
    .setUnit(U_NONE)
    .setDescription("PWIGOV");
  p.addPar("PLWIGOV", 0.0, &Model::PLWIGOV)
    .setUnit(U_NONE)
    .setDescription("PLWIGOV");
  p.addPar("POIGOVD", 0.0, &Model::POIGOVD)
    .setUnit(U_NONE)
    .setDescription("POIGOVD");
  p.addPar("PLIGOVD", 0.0, &Model::PLIGOVD)
    .setUnit(U_NONE)
    .setDescription("PLIGOVD");
  p.addPar("PWIGOVD", 0.0, &Model::PWIGOVD)
    .setUnit(U_NONE)
    .setDescription("PWIGOVD");
  p.addPar("PLWIGOVD", 0.0, &Model::PLWIGOVD)
    .setUnit(U_NONE)
    .setDescription("PLWIGOVD");
  p.addPar("POSTIG", 2.0, &Model::POSTIG)
    .setUnit(U_NONE)
    .setDescription("POSTIG");
  p.addPar("POGC2", 0.375, &Model::POGC2)
    .setUnit(U_NONE)
    .setDescription("POGC2");
  p.addPar("POGC3", 0.063, &Model::POGC3)
    .setUnit(U_NONE)
    .setDescription("POGC3");
  p.addPar("POCHIB", 3.1, &Model::POCHIB)
    .setUnit(U_NONE)
    .setDescription("POCHIB");
  p.addPar("POAGIDL", 0.0, &Model::POAGIDL)
    .setUnit(U_NONE)
    .setDescription("POAGIDL");
  p.addPar("PLAGIDL", 0.0, &Model::PLAGIDL)
    .setUnit(U_NONE)
    .setDescription("PLAGIDL");
  p.addPar("PWAGIDL", 0.0, &Model::PWAGIDL)
    .setUnit(U_NONE)
    .setDescription("PWAGIDL");
  p.addPar("PLWAGIDL", 0.0, &Model::PLWAGIDL)
    .setUnit(U_NONE)
    .setDescription("PLWAGIDL");
  p.addPar("POAGIDLD", 0.0, &Model::POAGIDLD)
    .setUnit(U_NONE)
    .setDescription("POAGIDLD");
  p.addPar("PLAGIDLD", 0.0, &Model::PLAGIDLD)
    .setUnit(U_NONE)
    .setDescription("PLAGIDLD");
  p.addPar("PWAGIDLD", 0.0, &Model::PWAGIDLD)
    .setUnit(U_NONE)
    .setDescription("PWAGIDLD");
  p.addPar("PLWAGIDLD", 0.0, &Model::PLWAGIDLD)
    .setUnit(U_NONE)
    .setDescription("PLWAGIDLD");
  p.addPar("POBGIDL", 41.0, &Model::POBGIDL)
    .setUnit(U_NONE)
    .setDescription("POBGIDL");
  p.addPar("POBGIDLD", 41.0, &Model::POBGIDLD)
    .setUnit(U_NONE)
    .setDescription("POBGIDLD");
  p.addPar("POSTBGIDL", 0.0, &Model::POSTBGIDL)
    .setUnit(U_NONE)
    .setDescription("POSTBGIDL");
  p.addPar("POSTBGIDLD", 0.0, &Model::POSTBGIDLD)
    .setUnit(U_NONE)
    .setDescription("POSTBGIDLD");
  p.addPar("POCGIDL", 0.0, &Model::POCGIDL)
    .setUnit(U_NONE)
    .setDescription("POCGIDL");
  p.addPar("POCGIDLD", 0.0, &Model::POCGIDLD)
    .setUnit(U_NONE)
    .setDescription("POCGIDLD");
  p.addPar("POCOX", 1e-14, &Model::POCOX)
    .setUnit(U_NONE)
    .setDescription("POCOX");
  p.addPar("PLCOX", 0.0, &Model::PLCOX)
    .setUnit(U_NONE)
    .setDescription("PLCOX");
  p.addPar("PWCOX", 0.0, &Model::PWCOX)
    .setUnit(U_NONE)
    .setDescription("PWCOX");
  p.addPar("PLWCOX", 0.0, &Model::PLWCOX)
    .setUnit(U_NONE)
    .setDescription("PLWCOX");
  p.addPar("POCGOV", 1e-15, &Model::POCGOV)
    .setUnit(U_NONE)
    .setDescription("POCGOV");
  p.addPar("PLCGOV", 0.0, &Model::PLCGOV)
    .setUnit(U_NONE)
    .setDescription("PLCGOV");
  p.addPar("PWCGOV", 0.0, &Model::PWCGOV)
    .setUnit(U_NONE)
    .setDescription("PWCGOV");
  p.addPar("PLWCGOV", 0.0, &Model::PLWCGOV)
    .setUnit(U_NONE)
    .setDescription("PLWCGOV");
  p.addPar("POCGOVD", 1e-15, &Model::POCGOVD)
    .setUnit(U_NONE)
    .setDescription("POCGOVD");
  p.addPar("PLCGOVD", 0.0, &Model::PLCGOVD)
    .setUnit(U_NONE)
    .setDescription("PLCGOVD");
  p.addPar("PWCGOVD", 0.0, &Model::PWCGOVD)
    .setUnit(U_NONE)
    .setDescription("PWCGOVD");
  p.addPar("PLWCGOVD", 0.0, &Model::PLWCGOVD)
    .setUnit(U_NONE)
    .setDescription("PLWCGOVD");
  p.addPar("POCGBOV", 0.0, &Model::POCGBOV)
    .setUnit(U_NONE)
    .setDescription("POCGBOV");
  p.addPar("PLCGBOV", 0.0, &Model::PLCGBOV)
    .setUnit(U_NONE)
    .setDescription("PLCGBOV");
  p.addPar("PWCGBOV", 0.0, &Model::PWCGBOV)
    .setUnit(U_NONE)
    .setDescription("PWCGBOV");
  p.addPar("PLWCGBOV", 0.0, &Model::PLWCGBOV)
    .setUnit(U_NONE)
    .setDescription("PLWCGBOV");
  p.addPar("POCFR", 0.0, &Model::POCFR)
    .setUnit(U_NONE)
    .setDescription("POCFR");
  p.addPar("PLCFR", 0.0, &Model::PLCFR)
    .setUnit(U_NONE)
    .setDescription("PLCFR");
  p.addPar("PWCFR", 0.0, &Model::PWCFR)
    .setUnit(U_NONE)
    .setDescription("PWCFR");
  p.addPar("PLWCFR", 0.0, &Model::PLWCFR)
    .setUnit(U_NONE)
    .setDescription("PLWCFR");
  p.addPar("POCFRD", 0.0, &Model::POCFRD)
    .setUnit(U_NONE)
    .setDescription("POCFRD");
  p.addPar("PLCFRD", 0.0, &Model::PLCFRD)
    .setUnit(U_NONE)
    .setDescription("PLCFRD");
  p.addPar("PWCFRD", 0.0, &Model::PWCFRD)
    .setUnit(U_NONE)
    .setDescription("PWCFRD");
  p.addPar("PLWCFRD", 0.0, &Model::PLWCFRD)
    .setUnit(U_NONE)
    .setDescription("PLWCFRD");
  p.addPar("POFNT", 1.0, &Model::POFNT)
    .setUnit(U_NONE)
    .setDescription("POFNT");
  p.addPar("POFNTEXC", 0.0, &Model::POFNTEXC)
    .setUnit(U_NONE)
    .setDescription("POFNTEXC");
  p.addPar("PLFNTEXC", 0.0, &Model::PLFNTEXC)
    .setUnit(U_NONE)
    .setDescription("PLFNTEXC");
  p.addPar("PWFNTEXC", 0.0, &Model::PWFNTEXC)
    .setUnit(U_NONE)
    .setDescription("PWFNTEXC");
  p.addPar("PLWFNTEXC", 0.0, &Model::PLWFNTEXC)
    .setUnit(U_NONE)
    .setDescription("PLWFNTEXC");
  p.addPar("PONFA", 8e+22, &Model::PONFA)
    .setUnit(U_NONE)
    .setDescription("PONFA");
  p.addPar("PLNFA", 0.0, &Model::PLNFA)
    .setUnit(U_NONE)
    .setDescription("PLNFA");
  p.addPar("PWNFA", 0.0, &Model::PWNFA)
    .setUnit(U_NONE)
    .setDescription("PWNFA");
  p.addPar("PLWNFA", 0.0, &Model::PLWNFA)
    .setUnit(U_NONE)
    .setDescription("PLWNFA");
  p.addPar("PONFB", 30000000.0, &Model::PONFB)
    .setUnit(U_NONE)
    .setDescription("PONFB");
  p.addPar("PLNFB", 0.0, &Model::PLNFB)
    .setUnit(U_NONE)
    .setDescription("PLNFB");
  p.addPar("PWNFB", 0.0, &Model::PWNFB)
    .setUnit(U_NONE)
    .setDescription("PWNFB");
  p.addPar("PLWNFB", 0.0, &Model::PLWNFB)
    .setUnit(U_NONE)
    .setDescription("PLWNFB");
  p.addPar("PONFC", 0.0, &Model::PONFC)
    .setUnit(U_NONE)
    .setDescription("PONFC");
  p.addPar("PLNFC", 0.0, &Model::PLNFC)
    .setUnit(U_NONE)
    .setDescription("PLNFC");
  p.addPar("PWNFC", 0.0, &Model::PWNFC)
    .setUnit(U_NONE)
    .setDescription("PWNFC");
  p.addPar("PLWNFC", 0.0, &Model::PLWNFC)
    .setUnit(U_NONE)
    .setDescription("PLWNFC");
  p.addPar("POEF", 1.0, &Model::POEF)
    .setUnit(U_NONE)
    .setDescription("POEF");
  p.addPar("POVFBEDGE", -1.0, &Model::POVFBEDGE)
    .setUnit(U_NONE)
    .setDescription("POVFBEDGE");
  p.addPar("POSTVFBEDGE", 0.0, &Model::POSTVFBEDGE)
    .setUnit(U_NONE)
    .setDescription("POSTVFBEDGE");
  p.addPar("PLSTVFBEDGE", 0.0, &Model::PLSTVFBEDGE)
    .setUnit(U_NONE)
    .setDescription("PLSTVFBEDGE");
  p.addPar("PWSTVFBEDGE", 0.0, &Model::PWSTVFBEDGE)
    .setUnit(U_NONE)
    .setDescription("PWSTVFBEDGE");
  p.addPar("PLWSTVFBEDGE", 0.0, &Model::PLWSTVFBEDGE)
    .setUnit(U_NONE)
    .setDescription("PLWSTVFBEDGE");
  p.addPar("PODPHIBEDGE", 0.0, &Model::PODPHIBEDGE)
    .setUnit(U_NONE)
    .setDescription("PODPHIBEDGE");
  p.addPar("PLDPHIBEDGE", 0.0, &Model::PLDPHIBEDGE)
    .setUnit(U_NONE)
    .setDescription("PLDPHIBEDGE");
  p.addPar("PWDPHIBEDGE", 0.0, &Model::PWDPHIBEDGE)
    .setUnit(U_NONE)
    .setDescription("PWDPHIBEDGE");
  p.addPar("PLWDPHIBEDGE", 0.0, &Model::PLWDPHIBEDGE)
    .setUnit(U_NONE)
    .setDescription("PLWDPHIBEDGE");
  p.addPar("PONEFFEDGE", 5e+23, &Model::PONEFFEDGE)
    .setUnit(U_NONE)
    .setDescription("PONEFFEDGE");
  p.addPar("PLNEFFEDGE", 0.0, &Model::PLNEFFEDGE)
    .setUnit(U_NONE)
    .setDescription("PLNEFFEDGE");
  p.addPar("PWNEFFEDGE", 0.0, &Model::PWNEFFEDGE)
    .setUnit(U_NONE)
    .setDescription("PWNEFFEDGE");
  p.addPar("PLWNEFFEDGE", 0.0, &Model::PLWNEFFEDGE)
    .setUnit(U_NONE)
    .setDescription("PLWNEFFEDGE");
  p.addPar("POCTEDGE", 0.0, &Model::POCTEDGE)
    .setUnit(U_NONE)
    .setDescription("POCTEDGE");
  p.addPar("PLCTEDGE", 0.0, &Model::PLCTEDGE)
    .setUnit(U_NONE)
    .setDescription("PLCTEDGE");
  p.addPar("PWCTEDGE", 0.0, &Model::PWCTEDGE)
    .setUnit(U_NONE)
    .setDescription("PWCTEDGE");
  p.addPar("PLWCTEDGE", 0.0, &Model::PLWCTEDGE)
    .setUnit(U_NONE)
    .setDescription("PLWCTEDGE");
  p.addPar("POBETNEDGE", 0.0005, &Model::POBETNEDGE)
    .setUnit(U_NONE)
    .setDescription("POBETNEDGE");
  p.addPar("PLBETNEDGE", 0.0, &Model::PLBETNEDGE)
    .setUnit(U_NONE)
    .setDescription("PLBETNEDGE");
  p.addPar("PWBETNEDGE", 0.0, &Model::PWBETNEDGE)
    .setUnit(U_NONE)
    .setDescription("PWBETNEDGE");
  p.addPar("PLWBETNEDGE", 0.0, &Model::PLWBETNEDGE)
    .setUnit(U_NONE)
    .setDescription("PLWBETNEDGE");
  p.addPar("POSTBETEDGE", 1.0, &Model::POSTBETEDGE)
    .setUnit(U_NONE)
    .setDescription("POSTBETEDGE");
  p.addPar("PLSTBETEDGE", 0.0, &Model::PLSTBETEDGE)
    .setUnit(U_NONE)
    .setDescription("PLSTBETEDGE");
  p.addPar("PWSTBETEDGE", 0.0, &Model::PWSTBETEDGE)
    .setUnit(U_NONE)
    .setDescription("PWSTBETEDGE");
  p.addPar("PLWSTBETEDGE", 0.0, &Model::PLWSTBETEDGE)
    .setUnit(U_NONE)
    .setDescription("PLWSTBETEDGE");
  p.addPar("POPSCEEDGE", 0.0, &Model::POPSCEEDGE)
    .setUnit(U_NONE)
    .setDescription("POPSCEEDGE");
  p.addPar("PLPSCEEDGE", 0.0, &Model::PLPSCEEDGE)
    .setUnit(U_NONE)
    .setDescription("PLPSCEEDGE");
  p.addPar("PWPSCEEDGE", 0.0, &Model::PWPSCEEDGE)
    .setUnit(U_NONE)
    .setDescription("PWPSCEEDGE");
  p.addPar("PLWPSCEEDGE", 0.0, &Model::PLWPSCEEDGE)
    .setUnit(U_NONE)
    .setDescription("PLWPSCEEDGE");
  p.addPar("POPSCEBEDGE", 0.0, &Model::POPSCEBEDGE)
    .setUnit(U_NONE)
    .setDescription("POPSCEBEDGE");
  p.addPar("POPSCEDEDGE", 0.0, &Model::POPSCEDEDGE)
    .setUnit(U_NONE)
    .setDescription("POPSCEDEDGE");
  p.addPar("POCFEDGE", 0.0, &Model::POCFEDGE)
    .setUnit(U_NONE)
    .setDescription("POCFEDGE");
  p.addPar("PLCFEDGE", 0.0, &Model::PLCFEDGE)
    .setUnit(U_NONE)
    .setDescription("PLCFEDGE");
  p.addPar("PWCFEDGE", 0.0, &Model::PWCFEDGE)
    .setUnit(U_NONE)
    .setDescription("PWCFEDGE");
  p.addPar("PLWCFEDGE", 0.0, &Model::PLWCFEDGE)
    .setUnit(U_NONE)
    .setDescription("PLWCFEDGE");
  p.addPar("POCFDEDGE", 0.0, &Model::POCFDEDGE)
    .setUnit(U_NONE)
    .setDescription("POCFDEDGE");
  p.addPar("POCFBEDGE", 0.0, &Model::POCFBEDGE)
    .setUnit(U_NONE)
    .setDescription("POCFBEDGE");
  p.addPar("POFNTEDGE", 1.0, &Model::POFNTEDGE)
    .setUnit(U_NONE)
    .setDescription("POFNTEDGE");
  p.addPar("PONFAEDGE", 8e+22, &Model::PONFAEDGE)
    .setUnit(U_NONE)
    .setDescription("PONFAEDGE");
  p.addPar("PLNFAEDGE", 0.0, &Model::PLNFAEDGE)
    .setUnit(U_NONE)
    .setDescription("PLNFAEDGE");
  p.addPar("PWNFAEDGE", 0.0, &Model::PWNFAEDGE)
    .setUnit(U_NONE)
    .setDescription("PWNFAEDGE");
  p.addPar("PLWNFAEDGE", 0.0, &Model::PLWNFAEDGE)
    .setUnit(U_NONE)
    .setDescription("PLWNFAEDGE");
  p.addPar("PONFBEDGE", 30000000.0, &Model::PONFBEDGE)
    .setUnit(U_NONE)
    .setDescription("PONFBEDGE");
  p.addPar("PLNFBEDGE", 0.0, &Model::PLNFBEDGE)
    .setUnit(U_NONE)
    .setDescription("PLNFBEDGE");
  p.addPar("PWNFBEDGE", 0.0, &Model::PWNFBEDGE)
    .setUnit(U_NONE)
    .setDescription("PWNFBEDGE");
  p.addPar("PLWNFBEDGE", 0.0, &Model::PLWNFBEDGE)
    .setUnit(U_NONE)
    .setDescription("PLWNFBEDGE");
  p.addPar("PONFCEDGE", 0.0, &Model::PONFCEDGE)
    .setUnit(U_NONE)
    .setDescription("PONFCEDGE");
  p.addPar("PLNFCEDGE", 0.0, &Model::PLNFCEDGE)
    .setUnit(U_NONE)
    .setDescription("PLNFCEDGE");
  p.addPar("PWNFCEDGE", 0.0, &Model::PWNFCEDGE)
    .setUnit(U_NONE)
    .setDescription("PWNFCEDGE");
  p.addPar("PLWNFCEDGE", 0.0, &Model::PLWNFCEDGE)
    .setUnit(U_NONE)
    .setDescription("PLWNFCEDGE");
  p.addPar("POEFEDGE", 1.0, &Model::POEFEDGE)
    .setUnit(U_NONE)
    .setDescription("POEFEDGE");
  p.addPar("POKVTHOWE", 0.0, &Model::POKVTHOWE)
    .setUnit(U_NONE)
    .setDescription("POKVTHOWE");
  p.addPar("PLKVTHOWE", 0.0, &Model::PLKVTHOWE)
    .setUnit(U_NONE)
    .setDescription("PLKVTHOWE");
  p.addPar("PWKVTHOWE", 0.0, &Model::PWKVTHOWE)
    .setUnit(U_NONE)
    .setDescription("PWKVTHOWE");
  p.addPar("PLWKVTHOWE", 0.0, &Model::PLWKVTHOWE)
    .setUnit(U_NONE)
    .setDescription("PLWKVTHOWE");
  p.addPar("POKUOWE", 0.0, &Model::POKUOWE)
    .setUnit(U_NONE)
    .setDescription("POKUOWE");
  p.addPar("PLKUOWE", 0.0, &Model::PLKUOWE)
    .setUnit(U_NONE)
    .setDescription("PLKUOWE");
  p.addPar("PWKUOWE", 0.0, &Model::PWKUOWE)
    .setUnit(U_NONE)
    .setDescription("PWKUOWE");
  p.addPar("PLWKUOWE", 0.0, &Model::PLWKUOWE)
    .setUnit(U_NONE)
    .setDescription("PLWKUOWE");
  p.addPar("LMIN", 0.0, &Model::LMIN)
    .setUnit(U_NONE)
    .setDescription("LMIN");
  p.addPar("LMAX", 1.0, &Model::LMAX)
    .setUnit(U_NONE)
    .setDescription("LMAX");
  p.addPar("WMIN", 0.0, &Model::WMIN)
    .setUnit(U_NONE)
    .setDescription("WMIN");
  p.addPar("WMAX", 1.0, &Model::WMAX)
    .setUnit(U_NONE)
    .setDescription("WMAX");
  p.addPar("LVARO", 0.0, &Model::LVARO)
    .setUnit(U_NONE)
    .setDescription("LVARO");
  p.addPar("LVARL", 0.0, &Model::LVARL)
    .setUnit(U_NONE)
    .setDescription("LVARL");
  p.addPar("LVARW", 0.0, &Model::LVARW)
    .setUnit(U_NONE)
    .setDescription("LVARW");
  p.addPar("LAP", 0.0, &Model::LAP)
    .setUnit(U_NONE)
    .setDescription("LAP");
  p.addPar("WVARO", 0.0, &Model::WVARO)
    .setUnit(U_NONE)
    .setDescription("WVARO");
  p.addPar("WVARL", 0.0, &Model::WVARL)
    .setUnit(U_NONE)
    .setDescription("WVARL");
  p.addPar("WVARW", 0.0, &Model::WVARW)
    .setUnit(U_NONE)
    .setDescription("WVARW");
  p.addPar("WOT", 0.0, &Model::WOT)
    .setUnit(U_NONE)
    .setDescription("WOT");
  p.addPar("DLQ", 0.0, &Model::DLQ)
    .setUnit(U_NONE)
    .setDescription("DLQ");
  p.addPar("DWQ", 0.0, &Model::DWQ)
    .setUnit(U_NONE)
    .setDescription("DWQ");
  p.addPar("VFBO", -1.0, &Model::VFBO)
    .setUnit(U_NONE)
    .setDescription("VFBO");
  p.addPar("VFBL", 0.0, &Model::VFBL)
    .setUnit(U_NONE)
    .setDescription("VFBL");
  p.addPar("VFBW", 0.0, &Model::VFBW)
    .setUnit(U_NONE)
    .setDescription("VFBW");
  p.addPar("VFBLW", 0.0, &Model::VFBLW)
    .setUnit(U_NONE)
    .setDescription("VFBLW");
  p.addPar("STVFBO", 0.0005, &Model::STVFBO)
    .setUnit(U_NONE)
    .setDescription("STVFBO");
  p.addPar("STVFBL", 0.0, &Model::STVFBL)
    .setUnit(U_NONE)
    .setDescription("STVFBL");
  p.addPar("STVFBW", 0.0, &Model::STVFBW)
    .setUnit(U_NONE)
    .setDescription("STVFBW");
  p.addPar("STVFBLW", 0.0, &Model::STVFBLW)
    .setUnit(U_NONE)
    .setDescription("STVFBLW");
  p.addPar("TOXO", 2e-09, &Model::TOXO)
    .setUnit(U_NONE)
    .setDescription("TOXO");
  p.addPar("EPSROXO", 3.9, &Model::EPSROXO)
    .setUnit(U_NONE)
    .setDescription("EPSROXO");
  p.addPar("NSUBO", 3e+23, &Model::NSUBO)
    .setUnit(U_NONE)
    .setDescription("NSUBO");
  p.addPar("NSUBW", 0.0, &Model::NSUBW)
    .setUnit(U_NONE)
    .setDescription("NSUBW");
  p.addPar("WSEG", 1e-08, &Model::WSEG)
    .setUnit(U_NONE)
    .setDescription("WSEG");
  p.addPar("NPCK", 1e+24, &Model::NPCK)
    .setUnit(U_NONE)
    .setDescription("NPCK");
  p.addPar("NPCKW", 0.0, &Model::NPCKW)
    .setUnit(U_NONE)
    .setDescription("NPCKW");
  p.addPar("WSEGP", 1e-08, &Model::WSEGP)
    .setUnit(U_NONE)
    .setDescription("WSEGP");
  p.addPar("LPCK", 1e-08, &Model::LPCK)
    .setUnit(U_NONE)
    .setDescription("LPCK");
  p.addPar("LPCKW", 0.0, &Model::LPCKW)
    .setUnit(U_NONE)
    .setDescription("LPCKW");
  p.addPar("FOL1", 0.0, &Model::FOL1)
    .setUnit(U_NONE)
    .setDescription("FOL1");
  p.addPar("FOL2", 0.0, &Model::FOL2)
    .setUnit(U_NONE)
    .setDescription("FOL2");
  p.addPar("FACNEFFACO", 1.0, &Model::FACNEFFACO)
    .setUnit(U_NONE)
    .setDescription("FACNEFFACO");
  p.addPar("FACNEFFACL", 0.0, &Model::FACNEFFACL)
    .setUnit(U_NONE)
    .setDescription("FACNEFFACL");
  p.addPar("FACNEFFACW", 0.0, &Model::FACNEFFACW)
    .setUnit(U_NONE)
    .setDescription("FACNEFFACW");
  p.addPar("FACNEFFACLW", 0.0, &Model::FACNEFFACLW)
    .setUnit(U_NONE)
    .setDescription("FACNEFFACLW");
  p.addPar("GFACNUDO", 1.0, &Model::GFACNUDO)
    .setUnit(U_NONE)
    .setDescription("GFACNUDO");
  p.addPar("GFACNUDL", 0.0, &Model::GFACNUDL)
    .setUnit(U_NONE)
    .setDescription("GFACNUDL");
  p.addPar("GFACNUDLEXP", 1.0, &Model::GFACNUDLEXP)
    .setUnit(U_NONE)
    .setDescription("GFACNUDLEXP");
  p.addPar("GFACNUDW", 0.0, &Model::GFACNUDW)
    .setUnit(U_NONE)
    .setDescription("GFACNUDW");
  p.addPar("GFACNUDLW", 0.0, &Model::GFACNUDLW)
    .setUnit(U_NONE)
    .setDescription("GFACNUDLW");
  p.addPar("VSBNUDO", 0.0, &Model::VSBNUDO)
    .setUnit(U_NONE)
    .setDescription("VSBNUDO");
  p.addPar("DVSBNUDO", 1.0, &Model::DVSBNUDO)
    .setUnit(U_NONE)
    .setDescription("DVSBNUDO");
  p.addPar("VNSUBO", 0.0, &Model::VNSUBO)
    .setUnit(U_NONE)
    .setDescription("VNSUBO");
  p.addPar("NSLPO", 0.05, &Model::NSLPO)
    .setUnit(U_NONE)
    .setDescription("NSLPO");
  p.addPar("DNSUBO", 0.0, &Model::DNSUBO)
    .setUnit(U_NONE)
    .setDescription("DNSUBO");
  p.addPar("DPHIBO", 0.0, &Model::DPHIBO)
    .setUnit(U_NONE)
    .setDescription("DPHIBO");
  p.addPar("DPHIBL", 0.0, &Model::DPHIBL)
    .setUnit(U_NONE)
    .setDescription("DPHIBL");
  p.addPar("DPHIBLEXP", 1.0, &Model::DPHIBLEXP)
    .setUnit(U_NONE)
    .setDescription("DPHIBLEXP");
  p.addPar("DPHIBW", 0.0, &Model::DPHIBW)
    .setUnit(U_NONE)
    .setDescription("DPHIBW");
  p.addPar("DPHIBLW", 0.0, &Model::DPHIBLW)
    .setUnit(U_NONE)
    .setDescription("DPHIBLW");
  p.addPar("DELVTACO", 0.0, &Model::DELVTACO)
    .setUnit(U_NONE)
    .setDescription("DELVTACO");
  p.addPar("DELVTACL", 0.0, &Model::DELVTACL)
    .setUnit(U_NONE)
    .setDescription("DELVTACL");
  p.addPar("DELVTACLEXP", 1.0, &Model::DELVTACLEXP)
    .setUnit(U_NONE)
    .setDescription("DELVTACLEXP");
  p.addPar("DELVTACW", 0.0, &Model::DELVTACW)
    .setUnit(U_NONE)
    .setDescription("DELVTACW");
  p.addPar("DELVTACLW", 0.0, &Model::DELVTACLW)
    .setUnit(U_NONE)
    .setDescription("DELVTACLW");
  p.addPar("NPO", 1e+26, &Model::NPO)
    .setUnit(U_NONE)
    .setDescription("NPO");
  p.addPar("NPL", 0.0, &Model::NPL)
    .setUnit(U_NONE)
    .setDescription("NPL");
  p.addPar("CTO", 0.0, &Model::CTO)
    .setUnit(U_NONE)
    .setDescription("CTO");
  p.addPar("CTL", 0.0, &Model::CTL)
    .setUnit(U_NONE)
    .setDescription("CTL");
  p.addPar("CTLEXP", 1.0, &Model::CTLEXP)
    .setUnit(U_NONE)
    .setDescription("CTLEXP");
  p.addPar("CTW", 0.0, &Model::CTW)
    .setUnit(U_NONE)
    .setDescription("CTW");
  p.addPar("CTLW", 0.0, &Model::CTLW)
    .setUnit(U_NONE)
    .setDescription("CTLW");
  p.addPar("TOXOVO", 2e-09, &Model::TOXOVO)
    .setUnit(U_NONE)
    .setDescription("TOXOVO");
  p.addPar("TOXOVDO", 2e-09, &Model::TOXOVDO)
    .setUnit(U_NONE)
    .setDescription("TOXOVDO");
  p.addPar("LOV", 0.0, &Model::LOV)
    .setUnit(U_NONE)
    .setDescription("LOV");
  p.addPar("LOVD", 0.0, &Model::LOVD)
    .setUnit(U_NONE)
    .setDescription("LOVD");
  p.addPar("NOVO", 5e+25, &Model::NOVO)
    .setUnit(U_NONE)
    .setDescription("NOVO");
  p.addPar("NOVDO", 5e+25, &Model::NOVDO)
    .setUnit(U_NONE)
    .setDescription("NOVDO");
  p.addPar("CFL", 0.0, &Model::CFL)
    .setUnit(U_NONE)
    .setDescription("CFL");
  p.addPar("CFLEXP", 2.0, &Model::CFLEXP)
    .setUnit(U_NONE)
    .setDescription("CFLEXP");
  p.addPar("CFW", 0.0, &Model::CFW)
    .setUnit(U_NONE)
    .setDescription("CFW");
  p.addPar("CFDO", 0.0, &Model::CFDO)
    .setUnit(U_NONE)
    .setDescription("CFDO");
  p.addPar("CFBO", 0.0, &Model::CFBO)
    .setUnit(U_NONE)
    .setDescription("CFBO");
  p.addPar("PSCEL", 0.0, &Model::PSCEL)
    .setUnit(U_NONE)
    .setDescription("PSCEL");
  p.addPar("PSCELEXP", 2.0, &Model::PSCELEXP)
    .setUnit(U_NONE)
    .setDescription("PSCELEXP");
  p.addPar("PSCEW", 0.0, &Model::PSCEW)
    .setUnit(U_NONE)
    .setDescription("PSCEW");
  p.addPar("PSCEBO", 0.0, &Model::PSCEBO)
    .setUnit(U_NONE)
    .setDescription("PSCEBO");
  p.addPar("PSCEDO", 0.0, &Model::PSCEDO)
    .setUnit(U_NONE)
    .setDescription("PSCEDO");
  p.addPar("UO", 0.05, &Model::UO)
    .setUnit(U_NONE)
    .setDescription("UO");
  p.addPar("FBET1", 0.0, &Model::FBET1)
    .setUnit(U_NONE)
    .setDescription("FBET1");
  p.addPar("FBET1W", 0.0, &Model::FBET1W)
    .setUnit(U_NONE)
    .setDescription("FBET1W");
  p.addPar("LP1", 1e-08, &Model::LP1)
    .setUnit(U_NONE)
    .setDescription("LP1");
  p.addPar("LP1W", 0.0, &Model::LP1W)
    .setUnit(U_NONE)
    .setDescription("LP1W");
  p.addPar("FBET2", 0.0, &Model::FBET2)
    .setUnit(U_NONE)
    .setDescription("FBET2");
  p.addPar("LP2", 1e-08, &Model::LP2)
    .setUnit(U_NONE)
    .setDescription("LP2");
  p.addPar("BETW1", 0.0, &Model::BETW1)
    .setUnit(U_NONE)
    .setDescription("BETW1");
  p.addPar("BETW2", 0.0, &Model::BETW2)
    .setUnit(U_NONE)
    .setDescription("BETW2");
  p.addPar("WBET", 1e-09, &Model::WBET)
    .setUnit(U_NONE)
    .setDescription("WBET");
  p.addPar("STBETO", 1.0, &Model::STBETO)
    .setUnit(U_NONE)
    .setDescription("STBETO");
  p.addPar("STBETL", 0.0, &Model::STBETL)
    .setUnit(U_NONE)
    .setDescription("STBETL");
  p.addPar("STBETW", 0.0, &Model::STBETW)
    .setUnit(U_NONE)
    .setDescription("STBETW");
  p.addPar("STBETLW", 0.0, &Model::STBETLW)
    .setUnit(U_NONE)
    .setDescription("STBETLW");
  p.addPar("MUEO", 0.5, &Model::MUEO)
    .setUnit(U_NONE)
    .setDescription("MUEO");
  p.addPar("MUEW", 0.0, &Model::MUEW)
    .setUnit(U_NONE)
    .setDescription("MUEW");
  p.addPar("STMUEO", 0.0, &Model::STMUEO)
    .setUnit(U_NONE)
    .setDescription("STMUEO");
  p.addPar("THEMUO", 1.5, &Model::THEMUO)
    .setUnit(U_NONE)
    .setDescription("THEMUO");
  p.addPar("STTHEMUO", 1.5, &Model::STTHEMUO)
    .setUnit(U_NONE)
    .setDescription("STTHEMUO");
  p.addPar("CSO", 0.0, &Model::CSO)
    .setUnit(U_NONE)
    .setDescription("CSO");
  p.addPar("CSL", 0.0, &Model::CSL)
    .setUnit(U_NONE)
    .setDescription("CSL");
  p.addPar("CSLEXP", 1.0, &Model::CSLEXP)
    .setUnit(U_NONE)
    .setDescription("CSLEXP");
  p.addPar("CSW", 0.0, &Model::CSW)
    .setUnit(U_NONE)
    .setDescription("CSW");
  p.addPar("CSLW", 0.0, &Model::CSLW)
    .setUnit(U_NONE)
    .setDescription("CSLW");
  p.addPar("STCSO", 0.0, &Model::STCSO)
    .setUnit(U_NONE)
    .setDescription("STCSO");
  p.addPar("XCORO", 0.0, &Model::XCORO)
    .setUnit(U_NONE)
    .setDescription("XCORO");
  p.addPar("XCORL", 0.0, &Model::XCORL)
    .setUnit(U_NONE)
    .setDescription("XCORL");
  p.addPar("XCORW", 0.0, &Model::XCORW)
    .setUnit(U_NONE)
    .setDescription("XCORW");
  p.addPar("XCORLW", 0.0, &Model::XCORLW)
    .setUnit(U_NONE)
    .setDescription("XCORLW");
  p.addPar("STXCORO", 0.0, &Model::STXCORO)
    .setUnit(U_NONE)
    .setDescription("STXCORO");
  p.addPar("FETAO", 1.0, &Model::FETAO)
    .setUnit(U_NONE)
    .setDescription("FETAO");
  p.addPar("RSW1", 50.0, &Model::RSW1)
    .setUnit(U_NONE)
    .setDescription("RSW1");
  p.addPar("RSW2", 0.0, &Model::RSW2)
    .setUnit(U_NONE)
    .setDescription("RSW2");
  p.addPar("STRSO", 1.0, &Model::STRSO)
    .setUnit(U_NONE)
    .setDescription("STRSO");
  p.addPar("RSBO", 0.0, &Model::RSBO)
    .setUnit(U_NONE)
    .setDescription("RSBO");
  p.addPar("RSGO", 0.0, &Model::RSGO)
    .setUnit(U_NONE)
    .setDescription("RSGO");
  p.addPar("THESATO", 0.0, &Model::THESATO)
    .setUnit(U_NONE)
    .setDescription("THESATO");
  p.addPar("THESATL", 0.05, &Model::THESATL)
    .setUnit(U_NONE)
    .setDescription("THESATL");
  p.addPar("THESATLEXP", 1.0, &Model::THESATLEXP)
    .setUnit(U_NONE)
    .setDescription("THESATLEXP");
  p.addPar("THESATW", 0.0, &Model::THESATW)
    .setUnit(U_NONE)
    .setDescription("THESATW");
  p.addPar("THESATLW", 0.0, &Model::THESATLW)
    .setUnit(U_NONE)
    .setDescription("THESATLW");
  p.addPar("STTHESATO", 1.0, &Model::STTHESATO)
    .setUnit(U_NONE)
    .setDescription("STTHESATO");
  p.addPar("STTHESATL", 0.0, &Model::STTHESATL)
    .setUnit(U_NONE)
    .setDescription("STTHESATL");
  p.addPar("STTHESATW", 0.0, &Model::STTHESATW)
    .setUnit(U_NONE)
    .setDescription("STTHESATW");
  p.addPar("STTHESATLW", 0.0, &Model::STTHESATLW)
    .setUnit(U_NONE)
    .setDescription("STTHESATLW");
  p.addPar("THESATBO", 0.0, &Model::THESATBO)
    .setUnit(U_NONE)
    .setDescription("THESATBO");
  p.addPar("THESATGO", 0.0, &Model::THESATGO)
    .setUnit(U_NONE)
    .setDescription("THESATGO");
  p.addPar("AXO", 18.0, &Model::AXO)
    .setUnit(U_NONE)
    .setDescription("AXO");
  p.addPar("AXL", 0.4, &Model::AXL)
    .setUnit(U_NONE)
    .setDescription("AXL");
  p.addPar("ALPL", 0.0005, &Model::ALPL)
    .setUnit(U_NONE)
    .setDescription("ALPL");
  p.addPar("ALPLEXP", 1.0, &Model::ALPLEXP)
    .setUnit(U_NONE)
    .setDescription("ALPLEXP");
  p.addPar("ALPW", 0.0, &Model::ALPW)
    .setUnit(U_NONE)
    .setDescription("ALPW");
  p.addPar("ALP1L1", 0.0, &Model::ALP1L1)
    .setUnit(U_NONE)
    .setDescription("ALP1L1");
  p.addPar("ALP1LEXP", 0.5, &Model::ALP1LEXP)
    .setUnit(U_NONE)
    .setDescription("ALP1LEXP");
  p.addPar("ALP1L2", 0.0, &Model::ALP1L2)
    .setUnit(U_NONE)
    .setDescription("ALP1L2");
  p.addPar("ALP1W", 0.0, &Model::ALP1W)
    .setUnit(U_NONE)
    .setDescription("ALP1W");
  p.addPar("ALP2L1", 0.0, &Model::ALP2L1)
    .setUnit(U_NONE)
    .setDescription("ALP2L1");
  p.addPar("ALP2LEXP", 0.5, &Model::ALP2LEXP)
    .setUnit(U_NONE)
    .setDescription("ALP2LEXP");
  p.addPar("ALP2L2", 0.0, &Model::ALP2L2)
    .setUnit(U_NONE)
    .setDescription("ALP2L2");
  p.addPar("ALP2W", 0.0, &Model::ALP2W)
    .setUnit(U_NONE)
    .setDescription("ALP2W");
  p.addPar("VPO", 0.05, &Model::VPO)
    .setUnit(U_NONE)
    .setDescription("VPO");
  p.addPar("A1O", 1.0, &Model::A1O)
    .setUnit(U_NONE)
    .setDescription("A1O");
  p.addPar("A1L", 0.0, &Model::A1L)
    .setUnit(U_NONE)
    .setDescription("A1L");
  p.addPar("A1W", 0.0, &Model::A1W)
    .setUnit(U_NONE)
    .setDescription("A1W");
  p.addPar("A2O", 10.0, &Model::A2O)
    .setUnit(U_NONE)
    .setDescription("A2O");
  p.addPar("STA2O", 0.0, &Model::STA2O)
    .setUnit(U_NONE)
    .setDescription("STA2O");
  p.addPar("A3O", 1.0, &Model::A3O)
    .setUnit(U_NONE)
    .setDescription("A3O");
  p.addPar("A3L", 0.0, &Model::A3L)
    .setUnit(U_NONE)
    .setDescription("A3L");
  p.addPar("A3W", 0.0, &Model::A3W)
    .setUnit(U_NONE)
    .setDescription("A3W");
  p.addPar("A4O", 0.0, &Model::A4O)
    .setUnit(U_NONE)
    .setDescription("A4O");
  p.addPar("A4L", 0.0, &Model::A4L)
    .setUnit(U_NONE)
    .setDescription("A4L");
  p.addPar("A4W", 0.0, &Model::A4W)
    .setUnit(U_NONE)
    .setDescription("A4W");
  p.addPar("GCOO", 0.0, &Model::GCOO)
    .setUnit(U_NONE)
    .setDescription("GCOO");
  p.addPar("IGINVLW", 0.0, &Model::IGINVLW)
    .setUnit(U_NONE)
    .setDescription("IGINVLW");
  p.addPar("IGOVW", 0.0, &Model::IGOVW)
    .setUnit(U_NONE)
    .setDescription("IGOVW");
  p.addPar("IGOVDW", 0.0, &Model::IGOVDW)
    .setUnit(U_NONE)
    .setDescription("IGOVDW");
  p.addPar("STIGO", 2.0, &Model::STIGO)
    .setUnit(U_NONE)
    .setDescription("STIGO");
  p.addPar("GC2O", 0.375, &Model::GC2O)
    .setUnit(U_NONE)
    .setDescription("GC2O");
  p.addPar("GC3O", 0.063, &Model::GC3O)
    .setUnit(U_NONE)
    .setDescription("GC3O");
  p.addPar("CHIBO", 3.1, &Model::CHIBO)
    .setUnit(U_NONE)
    .setDescription("CHIBO");
  p.addPar("AGIDLW", 0.0, &Model::AGIDLW)
    .setUnit(U_NONE)
    .setDescription("AGIDLW");
  p.addPar("AGIDLDW", 0.0, &Model::AGIDLDW)
    .setUnit(U_NONE)
    .setDescription("AGIDLDW");
  p.addPar("BGIDLO", 41.0, &Model::BGIDLO)
    .setUnit(U_NONE)
    .setDescription("BGIDLO");
  p.addPar("BGIDLDO", 41.0, &Model::BGIDLDO)
    .setUnit(U_NONE)
    .setDescription("BGIDLDO");
  p.addPar("STBGIDLO", 0.0, &Model::STBGIDLO)
    .setUnit(U_NONE)
    .setDescription("STBGIDLO");
  p.addPar("STBGIDLDO", 0.0, &Model::STBGIDLDO)
    .setUnit(U_NONE)
    .setDescription("STBGIDLDO");
  p.addPar("CGIDLO", 0.0, &Model::CGIDLO)
    .setUnit(U_NONE)
    .setDescription("CGIDLO");
  p.addPar("CGIDLDO", 0.0, &Model::CGIDLDO)
    .setUnit(U_NONE)
    .setDescription("CGIDLDO");
  p.addPar("CGBOVL", 0.0, &Model::CGBOVL)
    .setUnit(U_NONE)
    .setDescription("CGBOVL");
  p.addPar("CFRW", 0.0, &Model::CFRW)
    .setUnit(U_NONE)
    .setDescription("CFRW");
  p.addPar("CFRDW", 0.0, &Model::CFRDW)
    .setUnit(U_NONE)
    .setDescription("CFRDW");
  p.addPar("FNTO", 1.0, &Model::FNTO)
    .setUnit(U_NONE)
    .setDescription("FNTO");
  p.addPar("FNTEXCL", 0.0, &Model::FNTEXCL)
    .setUnit(U_NONE)
    .setDescription("FNTEXCL");
  p.addPar("NFALW", 8e+22, &Model::NFALW)
    .setUnit(U_NONE)
    .setDescription("NFALW");
  p.addPar("NFBLW", 30000000.0, &Model::NFBLW)
    .setUnit(U_NONE)
    .setDescription("NFBLW");
  p.addPar("NFCLW", 0.0, &Model::NFCLW)
    .setUnit(U_NONE)
    .setDescription("NFCLW");
  p.addPar("EFO", 1.0, &Model::EFO)
    .setUnit(U_NONE)
    .setDescription("EFO");
  p.addPar("LINTNOI", 0.0, &Model::LINTNOI)
    .setUnit(U_NONE)
    .setDescription("LINTNOI");
  p.addPar("ALPNOI", 2.0, &Model::ALPNOI)
    .setUnit(U_NONE)
    .setDescription("ALPNOI");
  p.addPar("WEDGE", 1e-08, &Model::WEDGE)
    .setUnit(U_NONE)
    .setDescription("WEDGE");
  p.addPar("WEDGEW", 0.0, &Model::WEDGEW)
    .setUnit(U_NONE)
    .setDescription("WEDGEW");
  p.addPar("VFBEDGEO", -1.0, &Model::VFBEDGEO)
    .setUnit(U_NONE)
    .setDescription("VFBEDGEO");
  p.addPar("STVFBEDGEO", 0.0005, &Model::STVFBEDGEO)
    .setUnit(U_NONE)
    .setDescription("STVFBEDGEO");
  p.addPar("STVFBEDGEL", 0.0, &Model::STVFBEDGEL)
    .setUnit(U_NONE)
    .setDescription("STVFBEDGEL");
  p.addPar("STVFBEDGEW", 0.0, &Model::STVFBEDGEW)
    .setUnit(U_NONE)
    .setDescription("STVFBEDGEW");
  p.addPar("STVFBEDGELW", 0.0, &Model::STVFBEDGELW)
    .setUnit(U_NONE)
    .setDescription("STVFBEDGELW");
  p.addPar("DPHIBEDGEO", 0.0, &Model::DPHIBEDGEO)
    .setUnit(U_NONE)
    .setDescription("DPHIBEDGEO");
  p.addPar("DPHIBEDGEL", 0.0, &Model::DPHIBEDGEL)
    .setUnit(U_NONE)
    .setDescription("DPHIBEDGEL");
  p.addPar("DPHIBEDGELEXP", 1.0, &Model::DPHIBEDGELEXP)
    .setUnit(U_NONE)
    .setDescription("DPHIBEDGELEXP");
  p.addPar("DPHIBEDGEW", 0.0, &Model::DPHIBEDGEW)
    .setUnit(U_NONE)
    .setDescription("DPHIBEDGEW");
  p.addPar("DPHIBEDGELW", 0.0, &Model::DPHIBEDGELW)
    .setUnit(U_NONE)
    .setDescription("DPHIBEDGELW");
  p.addPar("NSUBEDGEO", 5e+23, &Model::NSUBEDGEO)
    .setUnit(U_NONE)
    .setDescription("NSUBEDGEO");
  p.addPar("NSUBEDGEL", 0.0, &Model::NSUBEDGEL)
    .setUnit(U_NONE)
    .setDescription("NSUBEDGEL");
  p.addPar("NSUBEDGEW", 0.0, &Model::NSUBEDGEW)
    .setUnit(U_NONE)
    .setDescription("NSUBEDGEW");
  p.addPar("NSUBEDGELW", 0.0, &Model::NSUBEDGELW)
    .setUnit(U_NONE)
    .setDescription("NSUBEDGELW");
  p.addPar("CTEDGEO", 0.0, &Model::CTEDGEO)
    .setUnit(U_NONE)
    .setDescription("CTEDGEO");
  p.addPar("CTEDGEL", 0.0, &Model::CTEDGEL)
    .setUnit(U_NONE)
    .setDescription("CTEDGEL");
  p.addPar("CTEDGELEXP", 1.0, &Model::CTEDGELEXP)
    .setUnit(U_NONE)
    .setDescription("CTEDGELEXP");
  p.addPar("FBETEDGE", 0.0, &Model::FBETEDGE)
    .setUnit(U_NONE)
    .setDescription("FBETEDGE");
  p.addPar("LPEDGE", 1e-08, &Model::LPEDGE)
    .setUnit(U_NONE)
    .setDescription("LPEDGE");
  p.addPar("BETEDGEW", 0.0, &Model::BETEDGEW)
    .setUnit(U_NONE)
    .setDescription("BETEDGEW");
  p.addPar("STBETEDGEO", 1.0, &Model::STBETEDGEO)
    .setUnit(U_NONE)
    .setDescription("STBETEDGEO");
  p.addPar("STBETEDGEL", 0.0, &Model::STBETEDGEL)
    .setUnit(U_NONE)
    .setDescription("STBETEDGEL");
  p.addPar("STBETEDGEW", 0.0, &Model::STBETEDGEW)
    .setUnit(U_NONE)
    .setDescription("STBETEDGEW");
  p.addPar("STBETEDGELW", 0.0, &Model::STBETEDGELW)
    .setUnit(U_NONE)
    .setDescription("STBETEDGELW");
  p.addPar("PSCEEDGEL", 0.0, &Model::PSCEEDGEL)
    .setUnit(U_NONE)
    .setDescription("PSCEEDGEL");
  p.addPar("PSCEEDGELEXP", 2.0, &Model::PSCEEDGELEXP)
    .setUnit(U_NONE)
    .setDescription("PSCEEDGELEXP");
  p.addPar("PSCEEDGEW", 0.0, &Model::PSCEEDGEW)
    .setUnit(U_NONE)
    .setDescription("PSCEEDGEW");
  p.addPar("PSCEBEDGEO", 0.0, &Model::PSCEBEDGEO)
    .setUnit(U_NONE)
    .setDescription("PSCEBEDGEO");
  p.addPar("PSCEDEDGEO", 0.0, &Model::PSCEDEDGEO)
    .setUnit(U_NONE)
    .setDescription("PSCEDEDGEO");
  p.addPar("CFEDGEL", 0.0, &Model::CFEDGEL)
    .setUnit(U_NONE)
    .setDescription("CFEDGEL");
  p.addPar("CFEDGELEXP", 2.0, &Model::CFEDGELEXP)
    .setUnit(U_NONE)
    .setDescription("CFEDGELEXP");
  p.addPar("CFEDGEW", 0.0, &Model::CFEDGEW)
    .setUnit(U_NONE)
    .setDescription("CFEDGEW");
  p.addPar("CFDEDGEO", 0.0, &Model::CFDEDGEO)
    .setUnit(U_NONE)
    .setDescription("CFDEDGEO");
  p.addPar("CFBEDGEO", 0.0, &Model::CFBEDGEO)
    .setUnit(U_NONE)
    .setDescription("CFBEDGEO");
  p.addPar("FNTEDGEO", 1.0, &Model::FNTEDGEO)
    .setUnit(U_NONE)
    .setDescription("FNTEDGEO");
  p.addPar("NFAEDGELW", 8e+22, &Model::NFAEDGELW)
    .setUnit(U_NONE)
    .setDescription("NFAEDGELW");
  p.addPar("NFBEDGELW", 30000000.0, &Model::NFBEDGELW)
    .setUnit(U_NONE)
    .setDescription("NFBEDGELW");
  p.addPar("NFCEDGELW", 0.0, &Model::NFCEDGELW)
    .setUnit(U_NONE)
    .setDescription("NFCEDGELW");
  p.addPar("EFEDGEO", 1.0, &Model::EFEDGEO)
    .setUnit(U_NONE)
    .setDescription("EFEDGEO");
  p.addPar("KVTHOWEO", 0.0, &Model::KVTHOWEO)
    .setUnit(U_NONE)
    .setDescription("KVTHOWEO");
  p.addPar("KVTHOWEL", 0.0, &Model::KVTHOWEL)
    .setUnit(U_NONE)
    .setDescription("KVTHOWEL");
  p.addPar("KVTHOWEW", 0.0, &Model::KVTHOWEW)
    .setUnit(U_NONE)
    .setDescription("KVTHOWEW");
  p.addPar("KVTHOWELW", 0.0, &Model::KVTHOWELW)
    .setUnit(U_NONE)
    .setDescription("KVTHOWELW");
  p.addPar("KUOWEO", 0.0, &Model::KUOWEO)
    .setUnit(U_NONE)
    .setDescription("KUOWEO");
  p.addPar("KUOWEL", 0.0, &Model::KUOWEL)
    .setUnit(U_NONE)
    .setDescription("KUOWEL");
  p.addPar("KUOWEW", 0.0, &Model::KUOWEW)
    .setUnit(U_NONE)
    .setDescription("KUOWEW");
  p.addPar("KUOWELW", 0.0, &Model::KUOWELW)
    .setUnit(U_NONE)
    .setDescription("KUOWELW");
  p.addPar("RGO", 0.0, &Model::RGO)
    .setUnit(U_NONE)
    .setDescription("RGO");
  p.addPar("RINT", 0.0, &Model::RINT)
    .setUnit(U_NONE)
    .setDescription("RINT");
  p.addPar("RVPOLY", 0.0, &Model::RVPOLY)
    .setUnit(U_NONE)
    .setDescription("RVPOLY");
  p.addPar("RSHG", 0.0, &Model::RSHG)
    .setUnit(U_NONE)
    .setDescription("RSHG");
  p.addPar("DLSIL", 0.0, &Model::DLSIL)
    .setUnit(U_NONE)
    .setDescription("DLSIL");
  p.addPar("RSH", 0.0, &Model::RSH)
    .setUnit(U_NONE)
    .setDescription("RSH");
  p.addPar("RSHD", 0.0, &Model::RSHD)
    .setUnit(U_NONE)
    .setDescription("RSHD");
  p.addPar("RBULKO", 0.0, &Model::RBULKO)
    .setUnit(U_NONE)
    .setDescription("RBULKO");
  p.addPar("RWELLO", 0.0, &Model::RWELLO)
    .setUnit(U_NONE)
    .setDescription("RWELLO");
  p.addPar("RJUNSO", 0.0, &Model::RJUNSO)
    .setUnit(U_NONE)
    .setDescription("RJUNSO");
  p.addPar("RJUNDO", 0.0, &Model::RJUNDO)
    .setUnit(U_NONE)
    .setDescription("RJUNDO");
  p.addPar("SAREF", 1e-06, &Model::SAREF)
    .setUnit(U_NONE)
    .setDescription("SAREF");
  p.addPar("SBREF", 1e-06, &Model::SBREF)
    .setUnit(U_NONE)
    .setDescription("SBREF");
  p.addPar("WLOD", 0.0, &Model::WLOD)
    .setUnit(U_NONE)
    .setDescription("WLOD");
  p.addPar("KUO", 0.0, &Model::KUO)
    .setUnit(U_NONE)
    .setDescription("KUO");
  p.addPar("KVSAT", 0.0, &Model::KVSAT)
    .setUnit(U_NONE)
    .setDescription("KVSAT");
  p.addPar("TKUO", 0.0, &Model::TKUO)
    .setUnit(U_NONE)
    .setDescription("TKUO");
  p.addPar("LKUO", 0.0, &Model::LKUO)
    .setUnit(U_NONE)
    .setDescription("LKUO");
  p.addPar("WKUO", 0.0, &Model::WKUO)
    .setUnit(U_NONE)
    .setDescription("WKUO");
  p.addPar("PKUO", 0.0, &Model::PKUO)
    .setUnit(U_NONE)
    .setDescription("PKUO");
  p.addPar("LLODKUO", 0.0, &Model::LLODKUO)
    .setUnit(U_NONE)
    .setDescription("LLODKUO");
  p.addPar("WLODKUO", 0.0, &Model::WLODKUO)
    .setUnit(U_NONE)
    .setDescription("WLODKUO");
  p.addPar("KVTHO", 0.0, &Model::KVTHO)
    .setUnit(U_NONE)
    .setDescription("KVTHO");
  p.addPar("LKVTHO", 0.0, &Model::LKVTHO)
    .setUnit(U_NONE)
    .setDescription("LKVTHO");
  p.addPar("WKVTHO", 0.0, &Model::WKVTHO)
    .setUnit(U_NONE)
    .setDescription("WKVTHO");
  p.addPar("PKVTHO", 0.0, &Model::PKVTHO)
    .setUnit(U_NONE)
    .setDescription("PKVTHO");
  p.addPar("LLODVTH", 0.0, &Model::LLODVTH)
    .setUnit(U_NONE)
    .setDescription("LLODVTH");
  p.addPar("WLODVTH", 0.0, &Model::WLODVTH)
    .setUnit(U_NONE)
    .setDescription("WLODVTH");
  p.addPar("STETAO", 0.0, &Model::STETAO)
    .setUnit(U_NONE)
    .setDescription("STETAO");
  p.addPar("LODETAO", 1.0, &Model::LODETAO)
    .setUnit(U_NONE)
    .setDescription("LODETAO");
  p.addPar("SCREF", 1e-06, &Model::SCREF)
    .setUnit(U_NONE)
    .setDescription("SCREF");
  p.addPar("WEB", 0.0, &Model::WEB)
    .setUnit(U_NONE)
    .setDescription("WEB");
  p.addPar("WEC", 0.0, &Model::WEC)
    .setUnit(U_NONE)
    .setDescription("WEC");
  p.addPar("IMAX", 1000.0, &Model::IMAX)
    .setUnit(U_NONE)
    .setDescription("IMAX");
  p.addPar("TRJ", 21.0, &Model::TRJ)
    .setUnit(U_NONE)
    .setDescription("TRJ");
  p.addPar("FREV", 1000.0, &Model::FREV)
    .setUnit(U_NONE)
    .setDescription("FREV");
  p.addPar("CJORBOT", 0.001, &Model::CJORBOT)
    .setUnit(U_NONE)
    .setDescription("CJORBOT");
  p.addPar("CJORSTI", 1e-09, &Model::CJORSTI)
    .setUnit(U_NONE)
    .setDescription("CJORSTI");
  p.addPar("CJORGAT", 1e-09, &Model::CJORGAT)
    .setUnit(U_NONE)
    .setDescription("CJORGAT");
  p.addPar("VBIRBOT", 1.0, &Model::VBIRBOT)
    .setUnit(U_NONE)
    .setDescription("VBIRBOT");
  p.addPar("VBIRSTI", 1.0, &Model::VBIRSTI)
    .setUnit(U_NONE)
    .setDescription("VBIRSTI");
  p.addPar("VBIRGAT", 1.0, &Model::VBIRGAT)
    .setUnit(U_NONE)
    .setDescription("VBIRGAT");
  p.addPar("PBOT", 0.5, &Model::PBOT)
    .setUnit(U_NONE)
    .setDescription("PBOT");
  p.addPar("PSTI", 0.5, &Model::PSTI)
    .setUnit(U_NONE)
    .setDescription("PSTI");
  p.addPar("PGAT", 0.5, &Model::PGAT)
    .setUnit(U_NONE)
    .setDescription("PGAT");
  p.addPar("PHIGBOT", 1.16, &Model::PHIGBOT)
    .setUnit(U_NONE)
    .setDescription("PHIGBOT");
  p.addPar("PHIGSTI", 1.16, &Model::PHIGSTI)
    .setUnit(U_NONE)
    .setDescription("PHIGSTI");
  p.addPar("PHIGGAT", 1.16, &Model::PHIGGAT)
    .setUnit(U_NONE)
    .setDescription("PHIGGAT");
  p.addPar("IDSATRBOT", 1e-12, &Model::IDSATRBOT)
    .setUnit(U_NONE)
    .setDescription("IDSATRBOT");
  p.addPar("IDSATRSTI", 1e-18, &Model::IDSATRSTI)
    .setUnit(U_NONE)
    .setDescription("IDSATRSTI");
  p.addPar("IDSATRGAT", 1e-18, &Model::IDSATRGAT)
    .setUnit(U_NONE)
    .setDescription("IDSATRGAT");
  p.addPar("CSRHBOT", 100.0, &Model::CSRHBOT)
    .setUnit(U_NONE)
    .setDescription("CSRHBOT");
  p.addPar("CSRHSTI", 0.0001, &Model::CSRHSTI)
    .setUnit(U_NONE)
    .setDescription("CSRHSTI");
  p.addPar("CSRHGAT", 0.0001, &Model::CSRHGAT)
    .setUnit(U_NONE)
    .setDescription("CSRHGAT");
  p.addPar("XJUNSTI", 1e-07, &Model::XJUNSTI)
    .setUnit(U_NONE)
    .setDescription("XJUNSTI");
  p.addPar("XJUNGAT", 1e-07, &Model::XJUNGAT)
    .setUnit(U_NONE)
    .setDescription("XJUNGAT");
  p.addPar("CTATBOT", 100.0, &Model::CTATBOT)
    .setUnit(U_NONE)
    .setDescription("CTATBOT");
  p.addPar("CTATSTI", 0.0001, &Model::CTATSTI)
    .setUnit(U_NONE)
    .setDescription("CTATSTI");
  p.addPar("CTATGAT", 0.0001, &Model::CTATGAT)
    .setUnit(U_NONE)
    .setDescription("CTATGAT");
  p.addPar("MEFFTATBOT", 0.25, &Model::MEFFTATBOT)
    .setUnit(U_NONE)
    .setDescription("MEFFTATBOT");
  p.addPar("MEFFTATSTI", 0.25, &Model::MEFFTATSTI)
    .setUnit(U_NONE)
    .setDescription("MEFFTATSTI");
  p.addPar("MEFFTATGAT", 0.25, &Model::MEFFTATGAT)
    .setUnit(U_NONE)
    .setDescription("MEFFTATGAT");
  p.addPar("CBBTBOT", 1e-12, &Model::CBBTBOT)
    .setUnit(U_NONE)
    .setDescription("CBBTBOT");
  p.addPar("CBBTSTI", 1e-18, &Model::CBBTSTI)
    .setUnit(U_NONE)
    .setDescription("CBBTSTI");
  p.addPar("CBBTGAT", 1e-18, &Model::CBBTGAT)
    .setUnit(U_NONE)
    .setDescription("CBBTGAT");
  p.addPar("FBBTRBOT", 1000000000.0, &Model::FBBTRBOT)
    .setUnit(U_NONE)
    .setDescription("FBBTRBOT");
  p.addPar("FBBTRSTI", 1000000000.0, &Model::FBBTRSTI)
    .setUnit(U_NONE)
    .setDescription("FBBTRSTI");
  p.addPar("FBBTRGAT", 1000000000.0, &Model::FBBTRGAT)
    .setUnit(U_NONE)
    .setDescription("FBBTRGAT");
  p.addPar("STFBBTBOT", -0.001, &Model::STFBBTBOT)
    .setUnit(U_NONE)
    .setDescription("STFBBTBOT");
  p.addPar("STFBBTSTI", -0.001, &Model::STFBBTSTI)
    .setUnit(U_NONE)
    .setDescription("STFBBTSTI");
  p.addPar("STFBBTGAT", -0.001, &Model::STFBBTGAT)
    .setUnit(U_NONE)
    .setDescription("STFBBTGAT");
  p.addPar("VBRBOT", 10.0, &Model::VBRBOT)
    .setUnit(U_NONE)
    .setDescription("VBRBOT");
  p.addPar("VBRSTI", 10.0, &Model::VBRSTI)
    .setUnit(U_NONE)
    .setDescription("VBRSTI");
  p.addPar("VBRGAT", 10.0, &Model::VBRGAT)
    .setUnit(U_NONE)
    .setDescription("VBRGAT");
  p.addPar("PBRBOT", 4.0, &Model::PBRBOT)
    .setUnit(U_NONE)
    .setDescription("PBRBOT");
  p.addPar("PBRSTI", 4.0, &Model::PBRSTI)
    .setUnit(U_NONE)
    .setDescription("PBRSTI");
  p.addPar("PBRGAT", 4.0, &Model::PBRGAT)
    .setUnit(U_NONE)
    .setDescription("PBRGAT");
  p.addPar("CJORBOTD", 0.001, &Model::CJORBOTD)
    .setUnit(U_NONE)
    .setDescription("CJORBOTD");
  p.addPar("CJORSTID", 1e-09, &Model::CJORSTID)
    .setUnit(U_NONE)
    .setDescription("CJORSTID");
  p.addPar("CJORGATD", 1e-09, &Model::CJORGATD)
    .setUnit(U_NONE)
    .setDescription("CJORGATD");
  p.addPar("VBIRBOTD", 1.0, &Model::VBIRBOTD)
    .setUnit(U_NONE)
    .setDescription("VBIRBOTD");
  p.addPar("VBIRSTID", 1.0, &Model::VBIRSTID)
    .setUnit(U_NONE)
    .setDescription("VBIRSTID");
  p.addPar("VBIRGATD", 1.0, &Model::VBIRGATD)
    .setUnit(U_NONE)
    .setDescription("VBIRGATD");
  p.addPar("PBOTD", 0.5, &Model::PBOTD)
    .setUnit(U_NONE)
    .setDescription("PBOTD");
  p.addPar("PSTID", 0.5, &Model::PSTID)
    .setUnit(U_NONE)
    .setDescription("PSTID");
  p.addPar("PGATD", 0.5, &Model::PGATD)
    .setUnit(U_NONE)
    .setDescription("PGATD");
  p.addPar("PHIGBOTD", 1.16, &Model::PHIGBOTD)
    .setUnit(U_NONE)
    .setDescription("PHIGBOTD");
  p.addPar("PHIGSTID", 1.16, &Model::PHIGSTID)
    .setUnit(U_NONE)
    .setDescription("PHIGSTID");
  p.addPar("PHIGGATD", 1.16, &Model::PHIGGATD)
    .setUnit(U_NONE)
    .setDescription("PHIGGATD");
  p.addPar("IDSATRBOTD", 1e-12, &Model::IDSATRBOTD)
    .setUnit(U_NONE)
    .setDescription("IDSATRBOTD");
  p.addPar("IDSATRSTID", 1e-18, &Model::IDSATRSTID)
    .setUnit(U_NONE)
    .setDescription("IDSATRSTID");
  p.addPar("IDSATRGATD", 1e-18, &Model::IDSATRGATD)
    .setUnit(U_NONE)
    .setDescription("IDSATRGATD");
  p.addPar("CSRHBOTD", 100.0, &Model::CSRHBOTD)
    .setUnit(U_NONE)
    .setDescription("CSRHBOTD");
  p.addPar("CSRHSTID", 0.0001, &Model::CSRHSTID)
    .setUnit(U_NONE)
    .setDescription("CSRHSTID");
  p.addPar("CSRHGATD", 0.0001, &Model::CSRHGATD)
    .setUnit(U_NONE)
    .setDescription("CSRHGATD");
  p.addPar("XJUNSTID", 1e-07, &Model::XJUNSTID)
    .setUnit(U_NONE)
    .setDescription("XJUNSTID");
  p.addPar("XJUNGATD", 1e-07, &Model::XJUNGATD)
    .setUnit(U_NONE)
    .setDescription("XJUNGATD");
  p.addPar("CTATBOTD", 100.0, &Model::CTATBOTD)
    .setUnit(U_NONE)
    .setDescription("CTATBOTD");
  p.addPar("CTATSTID", 0.0001, &Model::CTATSTID)
    .setUnit(U_NONE)
    .setDescription("CTATSTID");
  p.addPar("CTATGATD", 0.0001, &Model::CTATGATD)
    .setUnit(U_NONE)
    .setDescription("CTATGATD");
  p.addPar("MEFFTATBOTD", 0.25, &Model::MEFFTATBOTD)
    .setUnit(U_NONE)
    .setDescription("MEFFTATBOTD");
  p.addPar("MEFFTATSTID", 0.25, &Model::MEFFTATSTID)
    .setUnit(U_NONE)
    .setDescription("MEFFTATSTID");
  p.addPar("MEFFTATGATD", 0.25, &Model::MEFFTATGATD)
    .setUnit(U_NONE)
    .setDescription("MEFFTATGATD");
  p.addPar("CBBTBOTD", 1e-12, &Model::CBBTBOTD)
    .setUnit(U_NONE)
    .setDescription("CBBTBOTD");
  p.addPar("CBBTSTID", 1e-18, &Model::CBBTSTID)
    .setUnit(U_NONE)
    .setDescription("CBBTSTID");
  p.addPar("CBBTGATD", 1e-18, &Model::CBBTGATD)
    .setUnit(U_NONE)
    .setDescription("CBBTGATD");
  p.addPar("FBBTRBOTD", 1000000000.0, &Model::FBBTRBOTD)
    .setUnit(U_NONE)
    .setDescription("FBBTRBOTD");
  p.addPar("FBBTRSTID", 1000000000.0, &Model::FBBTRSTID)
    .setUnit(U_NONE)
    .setDescription("FBBTRSTID");
  p.addPar("FBBTRGATD", 1000000000.0, &Model::FBBTRGATD)
    .setUnit(U_NONE)
    .setDescription("FBBTRGATD");
  p.addPar("STFBBTBOTD", -0.001, &Model::STFBBTBOTD)
    .setUnit(U_NONE)
    .setDescription("STFBBTBOTD");
  p.addPar("STFBBTSTID", -0.001, &Model::STFBBTSTID)
    .setUnit(U_NONE)
    .setDescription("STFBBTSTID");
  p.addPar("STFBBTGATD", -0.001, &Model::STFBBTGATD)
    .setUnit(U_NONE)
    .setDescription("STFBBTGATD");
  p.addPar("VBRBOTD", 10.0, &Model::VBRBOTD)
    .setUnit(U_NONE)
    .setDescription("VBRBOTD");
  p.addPar("VBRSTID", 10.0, &Model::VBRSTID)
    .setUnit(U_NONE)
    .setDescription("VBRSTID");
  p.addPar("VBRGATD", 10.0, &Model::VBRGATD)
    .setUnit(U_NONE)
    .setDescription("VBRGATD");
  p.addPar("PBRBOTD", 4.0, &Model::PBRBOTD)
    .setUnit(U_NONE)
    .setDescription("PBRBOTD");
  p.addPar("PBRSTID", 4.0, &Model::PBRSTID)
    .setUnit(U_NONE)
    .setDescription("PBRSTID");
  p.addPar("PBRGATD", 4.0, &Model::PBRGATD)
    .setUnit(U_NONE)
    .setDescription("PBRGATD");
  p.addPar("SWJUNEXP", 0.0, &Model::SWJUNEXP)
    .setUnit(U_NONE)
    .setDescription("SWJUNEXP");
  p.addPar("VJUNREF", 2.5, &Model::VJUNREF)
    .setUnit(U_NONE)
    .setDescription("VJUNREF");
  p.addPar("FJUNQ", 0.03, &Model::FJUNQ)
    .setUnit(U_NONE)
    .setDescription("FJUNQ");
  p.addPar("VJUNREFD", 2.5, &Model::VJUNREFD)
    .setUnit(U_NONE)
    .setDescription("VJUNREFD");
  p.addPar("FJUNQD", 0.03, &Model::FJUNQD)
    .setUnit(U_NONE)
    .setDescription("FJUNQD");
}

Instance::Instance(const Configuration &config,
                   const InstanceBlock &ib,
                   Model &model, const FactoryBlock &fb)
  : DeviceInstance(ib, config.getInstanceParameters(), fb),
    model_(model),
    vae_dl_(nullptr), vae_eval_(nullptr), vae_jac_(nullptr),
    hasPrevV_(true)  // start with zero as "previous" for limiting
{
  numExtVars = 4;
  numIntVars = 1;
  numStateVars = 0;
  numStoreVars = 0;

  jacStamp_.resize(numNodes);
  for (int i = 0; i < numNodes; i++) {
    jacStamp_[i].resize(numNodes);
    for (int j = 0; j < numNodes; j++)
      jacStamp_[i][j] = j;
  }

  setDefaultParams();
  setParams(ib.params);

  processParams();
}

Instance::~Instance() {
  if (vae_dl_) dlclose(vae_dl_);
}

double Instance::getCbParam(const char* nm) const {
  if (!strcmp(nm, "L")) return L;
  if (!strcmp(nm, "W")) return W;
  if (!strcmp(nm, "SA")) return SA;
  if (!strcmp(nm, "SB")) return SB;
  if (!strcmp(nm, "SD")) return SD;
  if (!strcmp(nm, "SCA")) return SCA;
  if (!strcmp(nm, "SCB")) return SCB;
  if (!strcmp(nm, "SCC")) return SCC;
  if (!strcmp(nm, "SC")) return SC;
  if (!strcmp(nm, "NF")) return NF;
  if (!strcmp(nm, "NGCON")) return NGCON;
  if (!strcmp(nm, "XGW")) return XGW;
  if (!strcmp(nm, "NRS")) return NRS;
  if (!strcmp(nm, "NRD")) return NRD;
  if (!strcmp(nm, "JW")) return JW;
  if (!strcmp(nm, "DELVTO")) return DELVTO;
  if (!strcmp(nm, "FACTUO")) return FACTUO;
  if (!strcmp(nm, "DELVTOEDGE")) return DELVTOEDGE;
  if (!strcmp(nm, "FACTUOEDGE")) return FACTUOEDGE;
  if (!strcmp(nm, "ABSOURCE")) return ABSOURCE;
  if (!strcmp(nm, "LSSOURCE")) return LSSOURCE;
  if (!strcmp(nm, "LGSOURCE")) return LGSOURCE;
  if (!strcmp(nm, "ABDRAIN")) return ABDRAIN;
  if (!strcmp(nm, "LSDRAIN")) return LSDRAIN;
  if (!strcmp(nm, "LGDRAIN")) return LGDRAIN;
  if (!strcmp(nm, "AS")) return AS;
  if (!strcmp(nm, "PS")) return PS;
  if (!strcmp(nm, "AD")) return AD;
  if (!strcmp(nm, "PD")) return PD;
  if (!strcmp(nm, "MULT")) return MULT;
  if (!strcmp(nm, "DTA")) return DTA;
  if (!strcmp(nm, "LEVEL")) return model_.LEVEL;
  if (!strcmp(nm, "TYPE")) return model_.TYPE;
  if (!strcmp(nm, "TR")) return model_.TR;
  if (!strcmp(nm, "SWGEO")) return model_.SWGEO;
  if (!strcmp(nm, "SWIGATE")) return model_.SWIGATE;
  if (!strcmp(nm, "SWIMPACT")) return model_.SWIMPACT;
  if (!strcmp(nm, "SWGIDL")) return model_.SWGIDL;
  if (!strcmp(nm, "SWJUNCAP")) return model_.SWJUNCAP;
  if (!strcmp(nm, "SWJUNASYM")) return model_.SWJUNASYM;
  if (!strcmp(nm, "SWNUD")) return model_.SWNUD;
  if (!strcmp(nm, "SWEDGE")) return model_.SWEDGE;
  if (!strcmp(nm, "SWDELVTAC")) return model_.SWDELVTAC;
  if (!strcmp(nm, "SWIGN")) return model_.SWIGN;
  if (!strcmp(nm, "QMC")) return model_.QMC;
  if (!strcmp(nm, "VFB")) return model_.VFB;
  if (!strcmp(nm, "STVFB")) return model_.STVFB;
  if (!strcmp(nm, "TOX")) return model_.TOX;
  if (!strcmp(nm, "EPSROX")) return model_.EPSROX;
  if (!strcmp(nm, "NEFF")) return model_.NEFF;
  if (!strcmp(nm, "FACNEFFAC")) return model_.FACNEFFAC;
  if (!strcmp(nm, "GFACNUD")) return model_.GFACNUD;
  if (!strcmp(nm, "VSBNUD")) return model_.VSBNUD;
  if (!strcmp(nm, "DVSBNUD")) return model_.DVSBNUD;
  if (!strcmp(nm, "VNSUB")) return model_.VNSUB;
  if (!strcmp(nm, "NSLP")) return model_.NSLP;
  if (!strcmp(nm, "DNSUB")) return model_.DNSUB;
  if (!strcmp(nm, "DPHIB")) return model_.DPHIB;
  if (!strcmp(nm, "DELVTAC")) return model_.DELVTAC;
  if (!strcmp(nm, "NP")) return model_.NP;
  if (!strcmp(nm, "CT")) return model_.CT;
  if (!strcmp(nm, "TOXOV")) return model_.TOXOV;
  if (!strcmp(nm, "TOXOVD")) return model_.TOXOVD;
  if (!strcmp(nm, "NOV")) return model_.NOV;
  if (!strcmp(nm, "NOVD")) return model_.NOVD;
  if (!strcmp(nm, "CF")) return model_.CF;
  if (!strcmp(nm, "CFD")) return model_.CFD;
  if (!strcmp(nm, "CFB")) return model_.CFB;
  if (!strcmp(nm, "PSCE")) return model_.PSCE;
  if (!strcmp(nm, "PSCEB")) return model_.PSCEB;
  if (!strcmp(nm, "PSCED")) return model_.PSCED;
  if (!strcmp(nm, "BETN")) return model_.BETN;
  if (!strcmp(nm, "STBET")) return model_.STBET;
  if (!strcmp(nm, "MUE")) return model_.MUE;
  if (!strcmp(nm, "STMUE")) return model_.STMUE;
  if (!strcmp(nm, "THEMU")) return model_.THEMU;
  if (!strcmp(nm, "STTHEMU")) return model_.STTHEMU;
  if (!strcmp(nm, "CS")) return model_.CS;
  if (!strcmp(nm, "STCS")) return model_.STCS;
  if (!strcmp(nm, "XCOR")) return model_.XCOR;
  if (!strcmp(nm, "STXCOR")) return model_.STXCOR;
  if (!strcmp(nm, "FETA")) return model_.FETA;
  if (!strcmp(nm, "RS")) return model_.RS;
  if (!strcmp(nm, "STRS")) return model_.STRS;
  if (!strcmp(nm, "RSB")) return model_.RSB;
  if (!strcmp(nm, "RSG")) return model_.RSG;
  if (!strcmp(nm, "THESAT")) return model_.THESAT;
  if (!strcmp(nm, "STTHESAT")) return model_.STTHESAT;
  if (!strcmp(nm, "THESATB")) return model_.THESATB;
  if (!strcmp(nm, "THESATG")) return model_.THESATG;
  if (!strcmp(nm, "AX")) return model_.AX;
  if (!strcmp(nm, "ALP")) return model_.ALP;
  if (!strcmp(nm, "ALP1")) return model_.ALP1;
  if (!strcmp(nm, "ALP2")) return model_.ALP2;
  if (!strcmp(nm, "VP")) return model_.VP;
  if (!strcmp(nm, "A1")) return model_.A1;
  if (!strcmp(nm, "A2")) return model_.A2;
  if (!strcmp(nm, "STA2")) return model_.STA2;
  if (!strcmp(nm, "A3")) return model_.A3;
  if (!strcmp(nm, "A4")) return model_.A4;
  if (!strcmp(nm, "GCO")) return model_.GCO;
  if (!strcmp(nm, "IGINV")) return model_.IGINV;
  if (!strcmp(nm, "IGOV")) return model_.IGOV;
  if (!strcmp(nm, "IGOVD")) return model_.IGOVD;
  if (!strcmp(nm, "STIG")) return model_.STIG;
  if (!strcmp(nm, "GC2")) return model_.GC2;
  if (!strcmp(nm, "GC3")) return model_.GC3;
  if (!strcmp(nm, "CHIB")) return model_.CHIB;
  if (!strcmp(nm, "AGIDL")) return model_.AGIDL;
  if (!strcmp(nm, "AGIDLD")) return model_.AGIDLD;
  if (!strcmp(nm, "BGIDL")) return model_.BGIDL;
  if (!strcmp(nm, "BGIDLD")) return model_.BGIDLD;
  if (!strcmp(nm, "STBGIDL")) return model_.STBGIDL;
  if (!strcmp(nm, "STBGIDLD")) return model_.STBGIDLD;
  if (!strcmp(nm, "CGIDL")) return model_.CGIDL;
  if (!strcmp(nm, "CGIDLD")) return model_.CGIDLD;
  if (!strcmp(nm, "COX")) return model_.COX;
  if (!strcmp(nm, "CGOV")) return model_.CGOV;
  if (!strcmp(nm, "CGOVD")) return model_.CGOVD;
  if (!strcmp(nm, "CGBOV")) return model_.CGBOV;
  if (!strcmp(nm, "CFR")) return model_.CFR;
  if (!strcmp(nm, "CFRD")) return model_.CFRD;
  if (!strcmp(nm, "FNT")) return model_.FNT;
  if (!strcmp(nm, "FNTEXC")) return model_.FNTEXC;
  if (!strcmp(nm, "NFA")) return model_.NFA;
  if (!strcmp(nm, "NFB")) return model_.NFB;
  if (!strcmp(nm, "NFC")) return model_.NFC;
  if (!strcmp(nm, "EF")) return model_.EF;
  if (!strcmp(nm, "VFBEDGE")) return model_.VFBEDGE;
  if (!strcmp(nm, "STVFBEDGE")) return model_.STVFBEDGE;
  if (!strcmp(nm, "DPHIBEDGE")) return model_.DPHIBEDGE;
  if (!strcmp(nm, "NEFFEDGE")) return model_.NEFFEDGE;
  if (!strcmp(nm, "CTEDGE")) return model_.CTEDGE;
  if (!strcmp(nm, "BETNEDGE")) return model_.BETNEDGE;
  if (!strcmp(nm, "STBETEDGE")) return model_.STBETEDGE;
  if (!strcmp(nm, "PSCEEDGE")) return model_.PSCEEDGE;
  if (!strcmp(nm, "PSCEBEDGE")) return model_.PSCEBEDGE;
  if (!strcmp(nm, "PSCEDEDGE")) return model_.PSCEDEDGE;
  if (!strcmp(nm, "CFEDGE")) return model_.CFEDGE;
  if (!strcmp(nm, "CFDEDGE")) return model_.CFDEDGE;
  if (!strcmp(nm, "CFBEDGE")) return model_.CFBEDGE;
  if (!strcmp(nm, "FNTEDGE")) return model_.FNTEDGE;
  if (!strcmp(nm, "NFAEDGE")) return model_.NFAEDGE;
  if (!strcmp(nm, "NFBEDGE")) return model_.NFBEDGE;
  if (!strcmp(nm, "NFCEDGE")) return model_.NFCEDGE;
  if (!strcmp(nm, "EFEDGE")) return model_.EFEDGE;
  if (!strcmp(nm, "RG")) return model_.RG;
  if (!strcmp(nm, "RSE")) return model_.RSE;
  if (!strcmp(nm, "RDE")) return model_.RDE;
  if (!strcmp(nm, "RBULK")) return model_.RBULK;
  if (!strcmp(nm, "RWELL")) return model_.RWELL;
  if (!strcmp(nm, "RJUNS")) return model_.RJUNS;
  if (!strcmp(nm, "RJUND")) return model_.RJUND;
  if (!strcmp(nm, "POVFB")) return model_.POVFB;
  if (!strcmp(nm, "PLVFB")) return model_.PLVFB;
  if (!strcmp(nm, "PWVFB")) return model_.PWVFB;
  if (!strcmp(nm, "PLWVFB")) return model_.PLWVFB;
  if (!strcmp(nm, "POSTVFB")) return model_.POSTVFB;
  if (!strcmp(nm, "PLSTVFB")) return model_.PLSTVFB;
  if (!strcmp(nm, "PWSTVFB")) return model_.PWSTVFB;
  if (!strcmp(nm, "PLWSTVFB")) return model_.PLWSTVFB;
  if (!strcmp(nm, "POTOX")) return model_.POTOX;
  if (!strcmp(nm, "POEPSROX")) return model_.POEPSROX;
  if (!strcmp(nm, "PONEFF")) return model_.PONEFF;
  if (!strcmp(nm, "PLNEFF")) return model_.PLNEFF;
  if (!strcmp(nm, "PWNEFF")) return model_.PWNEFF;
  if (!strcmp(nm, "PLWNEFF")) return model_.PLWNEFF;
  if (!strcmp(nm, "POFACNEFFAC")) return model_.POFACNEFFAC;
  if (!strcmp(nm, "PLFACNEFFAC")) return model_.PLFACNEFFAC;
  if (!strcmp(nm, "PWFACNEFFAC")) return model_.PWFACNEFFAC;
  if (!strcmp(nm, "PLWFACNEFFAC")) return model_.PLWFACNEFFAC;
  if (!strcmp(nm, "POGFACNUD")) return model_.POGFACNUD;
  if (!strcmp(nm, "PLGFACNUD")) return model_.PLGFACNUD;
  if (!strcmp(nm, "PWGFACNUD")) return model_.PWGFACNUD;
  if (!strcmp(nm, "PLWGFACNUD")) return model_.PLWGFACNUD;
  if (!strcmp(nm, "POVSBNUD")) return model_.POVSBNUD;
  if (!strcmp(nm, "PODVSBNUD")) return model_.PODVSBNUD;
  if (!strcmp(nm, "POVNSUB")) return model_.POVNSUB;
  if (!strcmp(nm, "PONSLP")) return model_.PONSLP;
  if (!strcmp(nm, "PODNSUB")) return model_.PODNSUB;
  if (!strcmp(nm, "PODPHIB")) return model_.PODPHIB;
  if (!strcmp(nm, "PLDPHIB")) return model_.PLDPHIB;
  if (!strcmp(nm, "PWDPHIB")) return model_.PWDPHIB;
  if (!strcmp(nm, "PLWDPHIB")) return model_.PLWDPHIB;
  if (!strcmp(nm, "PODELVTAC")) return model_.PODELVTAC;
  if (!strcmp(nm, "PLDELVTAC")) return model_.PLDELVTAC;
  if (!strcmp(nm, "PWDELVTAC")) return model_.PWDELVTAC;
  if (!strcmp(nm, "PLWDELVTAC")) return model_.PLWDELVTAC;
  if (!strcmp(nm, "PONP")) return model_.PONP;
  if (!strcmp(nm, "PLNP")) return model_.PLNP;
  if (!strcmp(nm, "PWNP")) return model_.PWNP;
  if (!strcmp(nm, "PLWNP")) return model_.PLWNP;
  if (!strcmp(nm, "POCT")) return model_.POCT;
  if (!strcmp(nm, "PLCT")) return model_.PLCT;
  if (!strcmp(nm, "PWCT")) return model_.PWCT;
  if (!strcmp(nm, "PLWCT")) return model_.PLWCT;
  if (!strcmp(nm, "POTOXOV")) return model_.POTOXOV;
  if (!strcmp(nm, "POTOXOVD")) return model_.POTOXOVD;
  if (!strcmp(nm, "PONOV")) return model_.PONOV;
  if (!strcmp(nm, "PLNOV")) return model_.PLNOV;
  if (!strcmp(nm, "PWNOV")) return model_.PWNOV;
  if (!strcmp(nm, "PLWNOV")) return model_.PLWNOV;
  if (!strcmp(nm, "PONOVD")) return model_.PONOVD;
  if (!strcmp(nm, "PLNOVD")) return model_.PLNOVD;
  if (!strcmp(nm, "PWNOVD")) return model_.PWNOVD;
  if (!strcmp(nm, "PLWNOVD")) return model_.PLWNOVD;
  if (!strcmp(nm, "POCF")) return model_.POCF;
  if (!strcmp(nm, "PLCF")) return model_.PLCF;
  if (!strcmp(nm, "PWCF")) return model_.PWCF;
  if (!strcmp(nm, "PLWCF")) return model_.PLWCF;
  if (!strcmp(nm, "POCFD")) return model_.POCFD;
  if (!strcmp(nm, "POCFB")) return model_.POCFB;
  if (!strcmp(nm, "POPSCE")) return model_.POPSCE;
  if (!strcmp(nm, "PLPSCE")) return model_.PLPSCE;
  if (!strcmp(nm, "PWPSCE")) return model_.PWPSCE;
  if (!strcmp(nm, "PLWPSCE")) return model_.PLWPSCE;
  if (!strcmp(nm, "POPSCEB")) return model_.POPSCEB;
  if (!strcmp(nm, "POPSCED")) return model_.POPSCED;
  if (!strcmp(nm, "POBETN")) return model_.POBETN;
  if (!strcmp(nm, "PLBETN")) return model_.PLBETN;
  if (!strcmp(nm, "PWBETN")) return model_.PWBETN;
  if (!strcmp(nm, "PLWBETN")) return model_.PLWBETN;
  if (!strcmp(nm, "POSTBET")) return model_.POSTBET;
  if (!strcmp(nm, "PLSTBET")) return model_.PLSTBET;
  if (!strcmp(nm, "PWSTBET")) return model_.PWSTBET;
  if (!strcmp(nm, "PLWSTBET")) return model_.PLWSTBET;
  if (!strcmp(nm, "POMUE")) return model_.POMUE;
  if (!strcmp(nm, "PLMUE")) return model_.PLMUE;
  if (!strcmp(nm, "PWMUE")) return model_.PWMUE;
  if (!strcmp(nm, "PLWMUE")) return model_.PLWMUE;
  if (!strcmp(nm, "POSTMUE")) return model_.POSTMUE;
  if (!strcmp(nm, "POTHEMU")) return model_.POTHEMU;
  if (!strcmp(nm, "POSTTHEMU")) return model_.POSTTHEMU;
  if (!strcmp(nm, "POCS")) return model_.POCS;
  if (!strcmp(nm, "PLCS")) return model_.PLCS;
  if (!strcmp(nm, "PWCS")) return model_.PWCS;
  if (!strcmp(nm, "PLWCS")) return model_.PLWCS;
  if (!strcmp(nm, "POSTCS")) return model_.POSTCS;
  if (!strcmp(nm, "POXCOR")) return model_.POXCOR;
  if (!strcmp(nm, "PLXCOR")) return model_.PLXCOR;
  if (!strcmp(nm, "PWXCOR")) return model_.PWXCOR;
  if (!strcmp(nm, "PLWXCOR")) return model_.PLWXCOR;
  if (!strcmp(nm, "POSTXCOR")) return model_.POSTXCOR;
  if (!strcmp(nm, "POFETA")) return model_.POFETA;
  if (!strcmp(nm, "PORS")) return model_.PORS;
  if (!strcmp(nm, "PLRS")) return model_.PLRS;
  if (!strcmp(nm, "PWRS")) return model_.PWRS;
  if (!strcmp(nm, "PLWRS")) return model_.PLWRS;
  if (!strcmp(nm, "POSTRS")) return model_.POSTRS;
  if (!strcmp(nm, "PORSB")) return model_.PORSB;
  if (!strcmp(nm, "PORSG")) return model_.PORSG;
  if (!strcmp(nm, "POTHESAT")) return model_.POTHESAT;
  if (!strcmp(nm, "PLTHESAT")) return model_.PLTHESAT;
  if (!strcmp(nm, "PWTHESAT")) return model_.PWTHESAT;
  if (!strcmp(nm, "PLWTHESAT")) return model_.PLWTHESAT;
  if (!strcmp(nm, "POSTTHESAT")) return model_.POSTTHESAT;
  if (!strcmp(nm, "PLSTTHESAT")) return model_.PLSTTHESAT;
  if (!strcmp(nm, "PWSTTHESAT")) return model_.PWSTTHESAT;
  if (!strcmp(nm, "PLWSTTHESAT")) return model_.PLWSTTHESAT;
  if (!strcmp(nm, "POTHESATB")) return model_.POTHESATB;
  if (!strcmp(nm, "PLTHESATB")) return model_.PLTHESATB;
  if (!strcmp(nm, "PWTHESATB")) return model_.PWTHESATB;
  if (!strcmp(nm, "PLWTHESATB")) return model_.PLWTHESATB;
  if (!strcmp(nm, "POTHESATG")) return model_.POTHESATG;
  if (!strcmp(nm, "PLTHESATG")) return model_.PLTHESATG;
  if (!strcmp(nm, "PWTHESATG")) return model_.PWTHESATG;
  if (!strcmp(nm, "PLWTHESATG")) return model_.PLWTHESATG;
  if (!strcmp(nm, "POAX")) return model_.POAX;
  if (!strcmp(nm, "PLAX")) return model_.PLAX;
  if (!strcmp(nm, "PWAX")) return model_.PWAX;
  if (!strcmp(nm, "PLWAX")) return model_.PLWAX;
  if (!strcmp(nm, "POALP")) return model_.POALP;
  if (!strcmp(nm, "PLALP")) return model_.PLALP;
  if (!strcmp(nm, "PWALP")) return model_.PWALP;
  if (!strcmp(nm, "PLWALP")) return model_.PLWALP;
  if (!strcmp(nm, "POALP1")) return model_.POALP1;
  if (!strcmp(nm, "PLALP1")) return model_.PLALP1;
  if (!strcmp(nm, "PWALP1")) return model_.PWALP1;
  if (!strcmp(nm, "PLWALP1")) return model_.PLWALP1;
  if (!strcmp(nm, "POALP2")) return model_.POALP2;
  if (!strcmp(nm, "PLALP2")) return model_.PLALP2;
  if (!strcmp(nm, "PWALP2")) return model_.PWALP2;
  if (!strcmp(nm, "PLWALP2")) return model_.PLWALP2;
  if (!strcmp(nm, "POVP")) return model_.POVP;
  if (!strcmp(nm, "POA1")) return model_.POA1;
  if (!strcmp(nm, "PLA1")) return model_.PLA1;
  if (!strcmp(nm, "PWA1")) return model_.PWA1;
  if (!strcmp(nm, "PLWA1")) return model_.PLWA1;
  if (!strcmp(nm, "POA2")) return model_.POA2;
  if (!strcmp(nm, "POSTA2")) return model_.POSTA2;
  if (!strcmp(nm, "POA3")) return model_.POA3;
  if (!strcmp(nm, "PLA3")) return model_.PLA3;
  if (!strcmp(nm, "PWA3")) return model_.PWA3;
  if (!strcmp(nm, "PLWA3")) return model_.PLWA3;
  if (!strcmp(nm, "POA4")) return model_.POA4;
  if (!strcmp(nm, "PLA4")) return model_.PLA4;
  if (!strcmp(nm, "PWA4")) return model_.PWA4;
  if (!strcmp(nm, "PLWA4")) return model_.PLWA4;
  if (!strcmp(nm, "POGCO")) return model_.POGCO;
  if (!strcmp(nm, "POIGINV")) return model_.POIGINV;
  if (!strcmp(nm, "PLIGINV")) return model_.PLIGINV;
  if (!strcmp(nm, "PWIGINV")) return model_.PWIGINV;
  if (!strcmp(nm, "PLWIGINV")) return model_.PLWIGINV;
  if (!strcmp(nm, "POIGOV")) return model_.POIGOV;
  if (!strcmp(nm, "PLIGOV")) return model_.PLIGOV;
  if (!strcmp(nm, "PWIGOV")) return model_.PWIGOV;
  if (!strcmp(nm, "PLWIGOV")) return model_.PLWIGOV;
  if (!strcmp(nm, "POIGOVD")) return model_.POIGOVD;
  if (!strcmp(nm, "PLIGOVD")) return model_.PLIGOVD;
  if (!strcmp(nm, "PWIGOVD")) return model_.PWIGOVD;
  if (!strcmp(nm, "PLWIGOVD")) return model_.PLWIGOVD;
  if (!strcmp(nm, "POSTIG")) return model_.POSTIG;
  if (!strcmp(nm, "POGC2")) return model_.POGC2;
  if (!strcmp(nm, "POGC3")) return model_.POGC3;
  if (!strcmp(nm, "POCHIB")) return model_.POCHIB;
  if (!strcmp(nm, "POAGIDL")) return model_.POAGIDL;
  if (!strcmp(nm, "PLAGIDL")) return model_.PLAGIDL;
  if (!strcmp(nm, "PWAGIDL")) return model_.PWAGIDL;
  if (!strcmp(nm, "PLWAGIDL")) return model_.PLWAGIDL;
  if (!strcmp(nm, "POAGIDLD")) return model_.POAGIDLD;
  if (!strcmp(nm, "PLAGIDLD")) return model_.PLAGIDLD;
  if (!strcmp(nm, "PWAGIDLD")) return model_.PWAGIDLD;
  if (!strcmp(nm, "PLWAGIDLD")) return model_.PLWAGIDLD;
  if (!strcmp(nm, "POBGIDL")) return model_.POBGIDL;
  if (!strcmp(nm, "POBGIDLD")) return model_.POBGIDLD;
  if (!strcmp(nm, "POSTBGIDL")) return model_.POSTBGIDL;
  if (!strcmp(nm, "POSTBGIDLD")) return model_.POSTBGIDLD;
  if (!strcmp(nm, "POCGIDL")) return model_.POCGIDL;
  if (!strcmp(nm, "POCGIDLD")) return model_.POCGIDLD;
  if (!strcmp(nm, "POCOX")) return model_.POCOX;
  if (!strcmp(nm, "PLCOX")) return model_.PLCOX;
  if (!strcmp(nm, "PWCOX")) return model_.PWCOX;
  if (!strcmp(nm, "PLWCOX")) return model_.PLWCOX;
  if (!strcmp(nm, "POCGOV")) return model_.POCGOV;
  if (!strcmp(nm, "PLCGOV")) return model_.PLCGOV;
  if (!strcmp(nm, "PWCGOV")) return model_.PWCGOV;
  if (!strcmp(nm, "PLWCGOV")) return model_.PLWCGOV;
  if (!strcmp(nm, "POCGOVD")) return model_.POCGOVD;
  if (!strcmp(nm, "PLCGOVD")) return model_.PLCGOVD;
  if (!strcmp(nm, "PWCGOVD")) return model_.PWCGOVD;
  if (!strcmp(nm, "PLWCGOVD")) return model_.PLWCGOVD;
  if (!strcmp(nm, "POCGBOV")) return model_.POCGBOV;
  if (!strcmp(nm, "PLCGBOV")) return model_.PLCGBOV;
  if (!strcmp(nm, "PWCGBOV")) return model_.PWCGBOV;
  if (!strcmp(nm, "PLWCGBOV")) return model_.PLWCGBOV;
  if (!strcmp(nm, "POCFR")) return model_.POCFR;
  if (!strcmp(nm, "PLCFR")) return model_.PLCFR;
  if (!strcmp(nm, "PWCFR")) return model_.PWCFR;
  if (!strcmp(nm, "PLWCFR")) return model_.PLWCFR;
  if (!strcmp(nm, "POCFRD")) return model_.POCFRD;
  if (!strcmp(nm, "PLCFRD")) return model_.PLCFRD;
  if (!strcmp(nm, "PWCFRD")) return model_.PWCFRD;
  if (!strcmp(nm, "PLWCFRD")) return model_.PLWCFRD;
  if (!strcmp(nm, "POFNT")) return model_.POFNT;
  if (!strcmp(nm, "POFNTEXC")) return model_.POFNTEXC;
  if (!strcmp(nm, "PLFNTEXC")) return model_.PLFNTEXC;
  if (!strcmp(nm, "PWFNTEXC")) return model_.PWFNTEXC;
  if (!strcmp(nm, "PLWFNTEXC")) return model_.PLWFNTEXC;
  if (!strcmp(nm, "PONFA")) return model_.PONFA;
  if (!strcmp(nm, "PLNFA")) return model_.PLNFA;
  if (!strcmp(nm, "PWNFA")) return model_.PWNFA;
  if (!strcmp(nm, "PLWNFA")) return model_.PLWNFA;
  if (!strcmp(nm, "PONFB")) return model_.PONFB;
  if (!strcmp(nm, "PLNFB")) return model_.PLNFB;
  if (!strcmp(nm, "PWNFB")) return model_.PWNFB;
  if (!strcmp(nm, "PLWNFB")) return model_.PLWNFB;
  if (!strcmp(nm, "PONFC")) return model_.PONFC;
  if (!strcmp(nm, "PLNFC")) return model_.PLNFC;
  if (!strcmp(nm, "PWNFC")) return model_.PWNFC;
  if (!strcmp(nm, "PLWNFC")) return model_.PLWNFC;
  if (!strcmp(nm, "POEF")) return model_.POEF;
  if (!strcmp(nm, "POVFBEDGE")) return model_.POVFBEDGE;
  if (!strcmp(nm, "POSTVFBEDGE")) return model_.POSTVFBEDGE;
  if (!strcmp(nm, "PLSTVFBEDGE")) return model_.PLSTVFBEDGE;
  if (!strcmp(nm, "PWSTVFBEDGE")) return model_.PWSTVFBEDGE;
  if (!strcmp(nm, "PLWSTVFBEDGE")) return model_.PLWSTVFBEDGE;
  if (!strcmp(nm, "PODPHIBEDGE")) return model_.PODPHIBEDGE;
  if (!strcmp(nm, "PLDPHIBEDGE")) return model_.PLDPHIBEDGE;
  if (!strcmp(nm, "PWDPHIBEDGE")) return model_.PWDPHIBEDGE;
  if (!strcmp(nm, "PLWDPHIBEDGE")) return model_.PLWDPHIBEDGE;
  if (!strcmp(nm, "PONEFFEDGE")) return model_.PONEFFEDGE;
  if (!strcmp(nm, "PLNEFFEDGE")) return model_.PLNEFFEDGE;
  if (!strcmp(nm, "PWNEFFEDGE")) return model_.PWNEFFEDGE;
  if (!strcmp(nm, "PLWNEFFEDGE")) return model_.PLWNEFFEDGE;
  if (!strcmp(nm, "POCTEDGE")) return model_.POCTEDGE;
  if (!strcmp(nm, "PLCTEDGE")) return model_.PLCTEDGE;
  if (!strcmp(nm, "PWCTEDGE")) return model_.PWCTEDGE;
  if (!strcmp(nm, "PLWCTEDGE")) return model_.PLWCTEDGE;
  if (!strcmp(nm, "POBETNEDGE")) return model_.POBETNEDGE;
  if (!strcmp(nm, "PLBETNEDGE")) return model_.PLBETNEDGE;
  if (!strcmp(nm, "PWBETNEDGE")) return model_.PWBETNEDGE;
  if (!strcmp(nm, "PLWBETNEDGE")) return model_.PLWBETNEDGE;
  if (!strcmp(nm, "POSTBETEDGE")) return model_.POSTBETEDGE;
  if (!strcmp(nm, "PLSTBETEDGE")) return model_.PLSTBETEDGE;
  if (!strcmp(nm, "PWSTBETEDGE")) return model_.PWSTBETEDGE;
  if (!strcmp(nm, "PLWSTBETEDGE")) return model_.PLWSTBETEDGE;
  if (!strcmp(nm, "POPSCEEDGE")) return model_.POPSCEEDGE;
  if (!strcmp(nm, "PLPSCEEDGE")) return model_.PLPSCEEDGE;
  if (!strcmp(nm, "PWPSCEEDGE")) return model_.PWPSCEEDGE;
  if (!strcmp(nm, "PLWPSCEEDGE")) return model_.PLWPSCEEDGE;
  if (!strcmp(nm, "POPSCEBEDGE")) return model_.POPSCEBEDGE;
  if (!strcmp(nm, "POPSCEDEDGE")) return model_.POPSCEDEDGE;
  if (!strcmp(nm, "POCFEDGE")) return model_.POCFEDGE;
  if (!strcmp(nm, "PLCFEDGE")) return model_.PLCFEDGE;
  if (!strcmp(nm, "PWCFEDGE")) return model_.PWCFEDGE;
  if (!strcmp(nm, "PLWCFEDGE")) return model_.PLWCFEDGE;
  if (!strcmp(nm, "POCFDEDGE")) return model_.POCFDEDGE;
  if (!strcmp(nm, "POCFBEDGE")) return model_.POCFBEDGE;
  if (!strcmp(nm, "POFNTEDGE")) return model_.POFNTEDGE;
  if (!strcmp(nm, "PONFAEDGE")) return model_.PONFAEDGE;
  if (!strcmp(nm, "PLNFAEDGE")) return model_.PLNFAEDGE;
  if (!strcmp(nm, "PWNFAEDGE")) return model_.PWNFAEDGE;
  if (!strcmp(nm, "PLWNFAEDGE")) return model_.PLWNFAEDGE;
  if (!strcmp(nm, "PONFBEDGE")) return model_.PONFBEDGE;
  if (!strcmp(nm, "PLNFBEDGE")) return model_.PLNFBEDGE;
  if (!strcmp(nm, "PWNFBEDGE")) return model_.PWNFBEDGE;
  if (!strcmp(nm, "PLWNFBEDGE")) return model_.PLWNFBEDGE;
  if (!strcmp(nm, "PONFCEDGE")) return model_.PONFCEDGE;
  if (!strcmp(nm, "PLNFCEDGE")) return model_.PLNFCEDGE;
  if (!strcmp(nm, "PWNFCEDGE")) return model_.PWNFCEDGE;
  if (!strcmp(nm, "PLWNFCEDGE")) return model_.PLWNFCEDGE;
  if (!strcmp(nm, "POEFEDGE")) return model_.POEFEDGE;
  if (!strcmp(nm, "POKVTHOWE")) return model_.POKVTHOWE;
  if (!strcmp(nm, "PLKVTHOWE")) return model_.PLKVTHOWE;
  if (!strcmp(nm, "PWKVTHOWE")) return model_.PWKVTHOWE;
  if (!strcmp(nm, "PLWKVTHOWE")) return model_.PLWKVTHOWE;
  if (!strcmp(nm, "POKUOWE")) return model_.POKUOWE;
  if (!strcmp(nm, "PLKUOWE")) return model_.PLKUOWE;
  if (!strcmp(nm, "PWKUOWE")) return model_.PWKUOWE;
  if (!strcmp(nm, "PLWKUOWE")) return model_.PLWKUOWE;
  if (!strcmp(nm, "LMIN")) return model_.LMIN;
  if (!strcmp(nm, "LMAX")) return model_.LMAX;
  if (!strcmp(nm, "WMIN")) return model_.WMIN;
  if (!strcmp(nm, "WMAX")) return model_.WMAX;
  if (!strcmp(nm, "LVARO")) return model_.LVARO;
  if (!strcmp(nm, "LVARL")) return model_.LVARL;
  if (!strcmp(nm, "LVARW")) return model_.LVARW;
  if (!strcmp(nm, "LAP")) return model_.LAP;
  if (!strcmp(nm, "WVARO")) return model_.WVARO;
  if (!strcmp(nm, "WVARL")) return model_.WVARL;
  if (!strcmp(nm, "WVARW")) return model_.WVARW;
  if (!strcmp(nm, "WOT")) return model_.WOT;
  if (!strcmp(nm, "DLQ")) return model_.DLQ;
  if (!strcmp(nm, "DWQ")) return model_.DWQ;
  if (!strcmp(nm, "VFBO")) return model_.VFBO;
  if (!strcmp(nm, "VFBL")) return model_.VFBL;
  if (!strcmp(nm, "VFBW")) return model_.VFBW;
  if (!strcmp(nm, "VFBLW")) return model_.VFBLW;
  if (!strcmp(nm, "STVFBO")) return model_.STVFBO;
  if (!strcmp(nm, "STVFBL")) return model_.STVFBL;
  if (!strcmp(nm, "STVFBW")) return model_.STVFBW;
  if (!strcmp(nm, "STVFBLW")) return model_.STVFBLW;
  if (!strcmp(nm, "TOXO")) return model_.TOXO;
  if (!strcmp(nm, "EPSROXO")) return model_.EPSROXO;
  if (!strcmp(nm, "NSUBO")) return model_.NSUBO;
  if (!strcmp(nm, "NSUBW")) return model_.NSUBW;
  if (!strcmp(nm, "WSEG")) return model_.WSEG;
  if (!strcmp(nm, "NPCK")) return model_.NPCK;
  if (!strcmp(nm, "NPCKW")) return model_.NPCKW;
  if (!strcmp(nm, "WSEGP")) return model_.WSEGP;
  if (!strcmp(nm, "LPCK")) return model_.LPCK;
  if (!strcmp(nm, "LPCKW")) return model_.LPCKW;
  if (!strcmp(nm, "FOL1")) return model_.FOL1;
  if (!strcmp(nm, "FOL2")) return model_.FOL2;
  if (!strcmp(nm, "FACNEFFACO")) return model_.FACNEFFACO;
  if (!strcmp(nm, "FACNEFFACL")) return model_.FACNEFFACL;
  if (!strcmp(nm, "FACNEFFACW")) return model_.FACNEFFACW;
  if (!strcmp(nm, "FACNEFFACLW")) return model_.FACNEFFACLW;
  if (!strcmp(nm, "GFACNUDO")) return model_.GFACNUDO;
  if (!strcmp(nm, "GFACNUDL")) return model_.GFACNUDL;
  if (!strcmp(nm, "GFACNUDLEXP")) return model_.GFACNUDLEXP;
  if (!strcmp(nm, "GFACNUDW")) return model_.GFACNUDW;
  if (!strcmp(nm, "GFACNUDLW")) return model_.GFACNUDLW;
  if (!strcmp(nm, "VSBNUDO")) return model_.VSBNUDO;
  if (!strcmp(nm, "DVSBNUDO")) return model_.DVSBNUDO;
  if (!strcmp(nm, "VNSUBO")) return model_.VNSUBO;
  if (!strcmp(nm, "NSLPO")) return model_.NSLPO;
  if (!strcmp(nm, "DNSUBO")) return model_.DNSUBO;
  if (!strcmp(nm, "DPHIBO")) return model_.DPHIBO;
  if (!strcmp(nm, "DPHIBL")) return model_.DPHIBL;
  if (!strcmp(nm, "DPHIBLEXP")) return model_.DPHIBLEXP;
  if (!strcmp(nm, "DPHIBW")) return model_.DPHIBW;
  if (!strcmp(nm, "DPHIBLW")) return model_.DPHIBLW;
  if (!strcmp(nm, "DELVTACO")) return model_.DELVTACO;
  if (!strcmp(nm, "DELVTACL")) return model_.DELVTACL;
  if (!strcmp(nm, "DELVTACLEXP")) return model_.DELVTACLEXP;
  if (!strcmp(nm, "DELVTACW")) return model_.DELVTACW;
  if (!strcmp(nm, "DELVTACLW")) return model_.DELVTACLW;
  if (!strcmp(nm, "NPO")) return model_.NPO;
  if (!strcmp(nm, "NPL")) return model_.NPL;
  if (!strcmp(nm, "CTO")) return model_.CTO;
  if (!strcmp(nm, "CTL")) return model_.CTL;
  if (!strcmp(nm, "CTLEXP")) return model_.CTLEXP;
  if (!strcmp(nm, "CTW")) return model_.CTW;
  if (!strcmp(nm, "CTLW")) return model_.CTLW;
  if (!strcmp(nm, "TOXOVO")) return model_.TOXOVO;
  if (!strcmp(nm, "TOXOVDO")) return model_.TOXOVDO;
  if (!strcmp(nm, "LOV")) return model_.LOV;
  if (!strcmp(nm, "LOVD")) return model_.LOVD;
  if (!strcmp(nm, "NOVO")) return model_.NOVO;
  if (!strcmp(nm, "NOVDO")) return model_.NOVDO;
  if (!strcmp(nm, "CFL")) return model_.CFL;
  if (!strcmp(nm, "CFLEXP")) return model_.CFLEXP;
  if (!strcmp(nm, "CFW")) return model_.CFW;
  if (!strcmp(nm, "CFDO")) return model_.CFDO;
  if (!strcmp(nm, "CFBO")) return model_.CFBO;
  if (!strcmp(nm, "PSCEL")) return model_.PSCEL;
  if (!strcmp(nm, "PSCELEXP")) return model_.PSCELEXP;
  if (!strcmp(nm, "PSCEW")) return model_.PSCEW;
  if (!strcmp(nm, "PSCEBO")) return model_.PSCEBO;
  if (!strcmp(nm, "PSCEDO")) return model_.PSCEDO;
  if (!strcmp(nm, "UO")) return model_.UO;
  if (!strcmp(nm, "FBET1")) return model_.FBET1;
  if (!strcmp(nm, "FBET1W")) return model_.FBET1W;
  if (!strcmp(nm, "LP1")) return model_.LP1;
  if (!strcmp(nm, "LP1W")) return model_.LP1W;
  if (!strcmp(nm, "FBET2")) return model_.FBET2;
  if (!strcmp(nm, "LP2")) return model_.LP2;
  if (!strcmp(nm, "BETW1")) return model_.BETW1;
  if (!strcmp(nm, "BETW2")) return model_.BETW2;
  if (!strcmp(nm, "WBET")) return model_.WBET;
  if (!strcmp(nm, "STBETO")) return model_.STBETO;
  if (!strcmp(nm, "STBETL")) return model_.STBETL;
  if (!strcmp(nm, "STBETW")) return model_.STBETW;
  if (!strcmp(nm, "STBETLW")) return model_.STBETLW;
  if (!strcmp(nm, "MUEO")) return model_.MUEO;
  if (!strcmp(nm, "MUEW")) return model_.MUEW;
  if (!strcmp(nm, "STMUEO")) return model_.STMUEO;
  if (!strcmp(nm, "THEMUO")) return model_.THEMUO;
  if (!strcmp(nm, "STTHEMUO")) return model_.STTHEMUO;
  if (!strcmp(nm, "CSO")) return model_.CSO;
  if (!strcmp(nm, "CSL")) return model_.CSL;
  if (!strcmp(nm, "CSLEXP")) return model_.CSLEXP;
  if (!strcmp(nm, "CSW")) return model_.CSW;
  if (!strcmp(nm, "CSLW")) return model_.CSLW;
  if (!strcmp(nm, "STCSO")) return model_.STCSO;
  if (!strcmp(nm, "XCORO")) return model_.XCORO;
  if (!strcmp(nm, "XCORL")) return model_.XCORL;
  if (!strcmp(nm, "XCORW")) return model_.XCORW;
  if (!strcmp(nm, "XCORLW")) return model_.XCORLW;
  if (!strcmp(nm, "STXCORO")) return model_.STXCORO;
  if (!strcmp(nm, "FETAO")) return model_.FETAO;
  if (!strcmp(nm, "RSW1")) return model_.RSW1;
  if (!strcmp(nm, "RSW2")) return model_.RSW2;
  if (!strcmp(nm, "STRSO")) return model_.STRSO;
  if (!strcmp(nm, "RSBO")) return model_.RSBO;
  if (!strcmp(nm, "RSGO")) return model_.RSGO;
  if (!strcmp(nm, "THESATO")) return model_.THESATO;
  if (!strcmp(nm, "THESATL")) return model_.THESATL;
  if (!strcmp(nm, "THESATLEXP")) return model_.THESATLEXP;
  if (!strcmp(nm, "THESATW")) return model_.THESATW;
  if (!strcmp(nm, "THESATLW")) return model_.THESATLW;
  if (!strcmp(nm, "STTHESATO")) return model_.STTHESATO;
  if (!strcmp(nm, "STTHESATL")) return model_.STTHESATL;
  if (!strcmp(nm, "STTHESATW")) return model_.STTHESATW;
  if (!strcmp(nm, "STTHESATLW")) return model_.STTHESATLW;
  if (!strcmp(nm, "THESATBO")) return model_.THESATBO;
  if (!strcmp(nm, "THESATGO")) return model_.THESATGO;
  if (!strcmp(nm, "AXO")) return model_.AXO;
  if (!strcmp(nm, "AXL")) return model_.AXL;
  if (!strcmp(nm, "ALPL")) return model_.ALPL;
  if (!strcmp(nm, "ALPLEXP")) return model_.ALPLEXP;
  if (!strcmp(nm, "ALPW")) return model_.ALPW;
  if (!strcmp(nm, "ALP1L1")) return model_.ALP1L1;
  if (!strcmp(nm, "ALP1LEXP")) return model_.ALP1LEXP;
  if (!strcmp(nm, "ALP1L2")) return model_.ALP1L2;
  if (!strcmp(nm, "ALP1W")) return model_.ALP1W;
  if (!strcmp(nm, "ALP2L1")) return model_.ALP2L1;
  if (!strcmp(nm, "ALP2LEXP")) return model_.ALP2LEXP;
  if (!strcmp(nm, "ALP2L2")) return model_.ALP2L2;
  if (!strcmp(nm, "ALP2W")) return model_.ALP2W;
  if (!strcmp(nm, "VPO")) return model_.VPO;
  if (!strcmp(nm, "A1O")) return model_.A1O;
  if (!strcmp(nm, "A1L")) return model_.A1L;
  if (!strcmp(nm, "A1W")) return model_.A1W;
  if (!strcmp(nm, "A2O")) return model_.A2O;
  if (!strcmp(nm, "STA2O")) return model_.STA2O;
  if (!strcmp(nm, "A3O")) return model_.A3O;
  if (!strcmp(nm, "A3L")) return model_.A3L;
  if (!strcmp(nm, "A3W")) return model_.A3W;
  if (!strcmp(nm, "A4O")) return model_.A4O;
  if (!strcmp(nm, "A4L")) return model_.A4L;
  if (!strcmp(nm, "A4W")) return model_.A4W;
  if (!strcmp(nm, "GCOO")) return model_.GCOO;
  if (!strcmp(nm, "IGINVLW")) return model_.IGINVLW;
  if (!strcmp(nm, "IGOVW")) return model_.IGOVW;
  if (!strcmp(nm, "IGOVDW")) return model_.IGOVDW;
  if (!strcmp(nm, "STIGO")) return model_.STIGO;
  if (!strcmp(nm, "GC2O")) return model_.GC2O;
  if (!strcmp(nm, "GC3O")) return model_.GC3O;
  if (!strcmp(nm, "CHIBO")) return model_.CHIBO;
  if (!strcmp(nm, "AGIDLW")) return model_.AGIDLW;
  if (!strcmp(nm, "AGIDLDW")) return model_.AGIDLDW;
  if (!strcmp(nm, "BGIDLO")) return model_.BGIDLO;
  if (!strcmp(nm, "BGIDLDO")) return model_.BGIDLDO;
  if (!strcmp(nm, "STBGIDLO")) return model_.STBGIDLO;
  if (!strcmp(nm, "STBGIDLDO")) return model_.STBGIDLDO;
  if (!strcmp(nm, "CGIDLO")) return model_.CGIDLO;
  if (!strcmp(nm, "CGIDLDO")) return model_.CGIDLDO;
  if (!strcmp(nm, "CGBOVL")) return model_.CGBOVL;
  if (!strcmp(nm, "CFRW")) return model_.CFRW;
  if (!strcmp(nm, "CFRDW")) return model_.CFRDW;
  if (!strcmp(nm, "FNTO")) return model_.FNTO;
  if (!strcmp(nm, "FNTEXCL")) return model_.FNTEXCL;
  if (!strcmp(nm, "NFALW")) return model_.NFALW;
  if (!strcmp(nm, "NFBLW")) return model_.NFBLW;
  if (!strcmp(nm, "NFCLW")) return model_.NFCLW;
  if (!strcmp(nm, "EFO")) return model_.EFO;
  if (!strcmp(nm, "LINTNOI")) return model_.LINTNOI;
  if (!strcmp(nm, "ALPNOI")) return model_.ALPNOI;
  if (!strcmp(nm, "WEDGE")) return model_.WEDGE;
  if (!strcmp(nm, "WEDGEW")) return model_.WEDGEW;
  if (!strcmp(nm, "VFBEDGEO")) return model_.VFBEDGEO;
  if (!strcmp(nm, "STVFBEDGEO")) return model_.STVFBEDGEO;
  if (!strcmp(nm, "STVFBEDGEL")) return model_.STVFBEDGEL;
  if (!strcmp(nm, "STVFBEDGEW")) return model_.STVFBEDGEW;
  if (!strcmp(nm, "STVFBEDGELW")) return model_.STVFBEDGELW;
  if (!strcmp(nm, "DPHIBEDGEO")) return model_.DPHIBEDGEO;
  if (!strcmp(nm, "DPHIBEDGEL")) return model_.DPHIBEDGEL;
  if (!strcmp(nm, "DPHIBEDGELEXP")) return model_.DPHIBEDGELEXP;
  if (!strcmp(nm, "DPHIBEDGEW")) return model_.DPHIBEDGEW;
  if (!strcmp(nm, "DPHIBEDGELW")) return model_.DPHIBEDGELW;
  if (!strcmp(nm, "NSUBEDGEO")) return model_.NSUBEDGEO;
  if (!strcmp(nm, "NSUBEDGEL")) return model_.NSUBEDGEL;
  if (!strcmp(nm, "NSUBEDGEW")) return model_.NSUBEDGEW;
  if (!strcmp(nm, "NSUBEDGELW")) return model_.NSUBEDGELW;
  if (!strcmp(nm, "CTEDGEO")) return model_.CTEDGEO;
  if (!strcmp(nm, "CTEDGEL")) return model_.CTEDGEL;
  if (!strcmp(nm, "CTEDGELEXP")) return model_.CTEDGELEXP;
  if (!strcmp(nm, "FBETEDGE")) return model_.FBETEDGE;
  if (!strcmp(nm, "LPEDGE")) return model_.LPEDGE;
  if (!strcmp(nm, "BETEDGEW")) return model_.BETEDGEW;
  if (!strcmp(nm, "STBETEDGEO")) return model_.STBETEDGEO;
  if (!strcmp(nm, "STBETEDGEL")) return model_.STBETEDGEL;
  if (!strcmp(nm, "STBETEDGEW")) return model_.STBETEDGEW;
  if (!strcmp(nm, "STBETEDGELW")) return model_.STBETEDGELW;
  if (!strcmp(nm, "PSCEEDGEL")) return model_.PSCEEDGEL;
  if (!strcmp(nm, "PSCEEDGELEXP")) return model_.PSCEEDGELEXP;
  if (!strcmp(nm, "PSCEEDGEW")) return model_.PSCEEDGEW;
  if (!strcmp(nm, "PSCEBEDGEO")) return model_.PSCEBEDGEO;
  if (!strcmp(nm, "PSCEDEDGEO")) return model_.PSCEDEDGEO;
  if (!strcmp(nm, "CFEDGEL")) return model_.CFEDGEL;
  if (!strcmp(nm, "CFEDGELEXP")) return model_.CFEDGELEXP;
  if (!strcmp(nm, "CFEDGEW")) return model_.CFEDGEW;
  if (!strcmp(nm, "CFDEDGEO")) return model_.CFDEDGEO;
  if (!strcmp(nm, "CFBEDGEO")) return model_.CFBEDGEO;
  if (!strcmp(nm, "FNTEDGEO")) return model_.FNTEDGEO;
  if (!strcmp(nm, "NFAEDGELW")) return model_.NFAEDGELW;
  if (!strcmp(nm, "NFBEDGELW")) return model_.NFBEDGELW;
  if (!strcmp(nm, "NFCEDGELW")) return model_.NFCEDGELW;
  if (!strcmp(nm, "EFEDGEO")) return model_.EFEDGEO;
  if (!strcmp(nm, "KVTHOWEO")) return model_.KVTHOWEO;
  if (!strcmp(nm, "KVTHOWEL")) return model_.KVTHOWEL;
  if (!strcmp(nm, "KVTHOWEW")) return model_.KVTHOWEW;
  if (!strcmp(nm, "KVTHOWELW")) return model_.KVTHOWELW;
  if (!strcmp(nm, "KUOWEO")) return model_.KUOWEO;
  if (!strcmp(nm, "KUOWEL")) return model_.KUOWEL;
  if (!strcmp(nm, "KUOWEW")) return model_.KUOWEW;
  if (!strcmp(nm, "KUOWELW")) return model_.KUOWELW;
  if (!strcmp(nm, "RGO")) return model_.RGO;
  if (!strcmp(nm, "RINT")) return model_.RINT;
  if (!strcmp(nm, "RVPOLY")) return model_.RVPOLY;
  if (!strcmp(nm, "RSHG")) return model_.RSHG;
  if (!strcmp(nm, "DLSIL")) return model_.DLSIL;
  if (!strcmp(nm, "RSH")) return model_.RSH;
  if (!strcmp(nm, "RSHD")) return model_.RSHD;
  if (!strcmp(nm, "RBULKO")) return model_.RBULKO;
  if (!strcmp(nm, "RWELLO")) return model_.RWELLO;
  if (!strcmp(nm, "RJUNSO")) return model_.RJUNSO;
  if (!strcmp(nm, "RJUNDO")) return model_.RJUNDO;
  if (!strcmp(nm, "SAREF")) return model_.SAREF;
  if (!strcmp(nm, "SBREF")) return model_.SBREF;
  if (!strcmp(nm, "WLOD")) return model_.WLOD;
  if (!strcmp(nm, "KUO")) return model_.KUO;
  if (!strcmp(nm, "KVSAT")) return model_.KVSAT;
  if (!strcmp(nm, "TKUO")) return model_.TKUO;
  if (!strcmp(nm, "LKUO")) return model_.LKUO;
  if (!strcmp(nm, "WKUO")) return model_.WKUO;
  if (!strcmp(nm, "PKUO")) return model_.PKUO;
  if (!strcmp(nm, "LLODKUO")) return model_.LLODKUO;
  if (!strcmp(nm, "WLODKUO")) return model_.WLODKUO;
  if (!strcmp(nm, "KVTHO")) return model_.KVTHO;
  if (!strcmp(nm, "LKVTHO")) return model_.LKVTHO;
  if (!strcmp(nm, "WKVTHO")) return model_.WKVTHO;
  if (!strcmp(nm, "PKVTHO")) return model_.PKVTHO;
  if (!strcmp(nm, "LLODVTH")) return model_.LLODVTH;
  if (!strcmp(nm, "WLODVTH")) return model_.WLODVTH;
  if (!strcmp(nm, "STETAO")) return model_.STETAO;
  if (!strcmp(nm, "LODETAO")) return model_.LODETAO;
  if (!strcmp(nm, "SCREF")) return model_.SCREF;
  if (!strcmp(nm, "WEB")) return model_.WEB;
  if (!strcmp(nm, "WEC")) return model_.WEC;
  if (!strcmp(nm, "IMAX")) return model_.IMAX;
  if (!strcmp(nm, "TRJ")) return model_.TRJ;
  if (!strcmp(nm, "FREV")) return model_.FREV;
  if (!strcmp(nm, "CJORBOT")) return model_.CJORBOT;
  if (!strcmp(nm, "CJORSTI")) return model_.CJORSTI;
  if (!strcmp(nm, "CJORGAT")) return model_.CJORGAT;
  if (!strcmp(nm, "VBIRBOT")) return model_.VBIRBOT;
  if (!strcmp(nm, "VBIRSTI")) return model_.VBIRSTI;
  if (!strcmp(nm, "VBIRGAT")) return model_.VBIRGAT;
  if (!strcmp(nm, "PBOT")) return model_.PBOT;
  if (!strcmp(nm, "PSTI")) return model_.PSTI;
  if (!strcmp(nm, "PGAT")) return model_.PGAT;
  if (!strcmp(nm, "PHIGBOT")) return model_.PHIGBOT;
  if (!strcmp(nm, "PHIGSTI")) return model_.PHIGSTI;
  if (!strcmp(nm, "PHIGGAT")) return model_.PHIGGAT;
  if (!strcmp(nm, "IDSATRBOT")) return model_.IDSATRBOT;
  if (!strcmp(nm, "IDSATRSTI")) return model_.IDSATRSTI;
  if (!strcmp(nm, "IDSATRGAT")) return model_.IDSATRGAT;
  if (!strcmp(nm, "CSRHBOT")) return model_.CSRHBOT;
  if (!strcmp(nm, "CSRHSTI")) return model_.CSRHSTI;
  if (!strcmp(nm, "CSRHGAT")) return model_.CSRHGAT;
  if (!strcmp(nm, "XJUNSTI")) return model_.XJUNSTI;
  if (!strcmp(nm, "XJUNGAT")) return model_.XJUNGAT;
  if (!strcmp(nm, "CTATBOT")) return model_.CTATBOT;
  if (!strcmp(nm, "CTATSTI")) return model_.CTATSTI;
  if (!strcmp(nm, "CTATGAT")) return model_.CTATGAT;
  if (!strcmp(nm, "MEFFTATBOT")) return model_.MEFFTATBOT;
  if (!strcmp(nm, "MEFFTATSTI")) return model_.MEFFTATSTI;
  if (!strcmp(nm, "MEFFTATGAT")) return model_.MEFFTATGAT;
  if (!strcmp(nm, "CBBTBOT")) return model_.CBBTBOT;
  if (!strcmp(nm, "CBBTSTI")) return model_.CBBTSTI;
  if (!strcmp(nm, "CBBTGAT")) return model_.CBBTGAT;
  if (!strcmp(nm, "FBBTRBOT")) return model_.FBBTRBOT;
  if (!strcmp(nm, "FBBTRSTI")) return model_.FBBTRSTI;
  if (!strcmp(nm, "FBBTRGAT")) return model_.FBBTRGAT;
  if (!strcmp(nm, "STFBBTBOT")) return model_.STFBBTBOT;
  if (!strcmp(nm, "STFBBTSTI")) return model_.STFBBTSTI;
  if (!strcmp(nm, "STFBBTGAT")) return model_.STFBBTGAT;
  if (!strcmp(nm, "VBRBOT")) return model_.VBRBOT;
  if (!strcmp(nm, "VBRSTI")) return model_.VBRSTI;
  if (!strcmp(nm, "VBRGAT")) return model_.VBRGAT;
  if (!strcmp(nm, "PBRBOT")) return model_.PBRBOT;
  if (!strcmp(nm, "PBRSTI")) return model_.PBRSTI;
  if (!strcmp(nm, "PBRGAT")) return model_.PBRGAT;
  if (!strcmp(nm, "CJORBOTD")) return model_.CJORBOTD;
  if (!strcmp(nm, "CJORSTID")) return model_.CJORSTID;
  if (!strcmp(nm, "CJORGATD")) return model_.CJORGATD;
  if (!strcmp(nm, "VBIRBOTD")) return model_.VBIRBOTD;
  if (!strcmp(nm, "VBIRSTID")) return model_.VBIRSTID;
  if (!strcmp(nm, "VBIRGATD")) return model_.VBIRGATD;
  if (!strcmp(nm, "PBOTD")) return model_.PBOTD;
  if (!strcmp(nm, "PSTID")) return model_.PSTID;
  if (!strcmp(nm, "PGATD")) return model_.PGATD;
  if (!strcmp(nm, "PHIGBOTD")) return model_.PHIGBOTD;
  if (!strcmp(nm, "PHIGSTID")) return model_.PHIGSTID;
  if (!strcmp(nm, "PHIGGATD")) return model_.PHIGGATD;
  if (!strcmp(nm, "IDSATRBOTD")) return model_.IDSATRBOTD;
  if (!strcmp(nm, "IDSATRSTID")) return model_.IDSATRSTID;
  if (!strcmp(nm, "IDSATRGATD")) return model_.IDSATRGATD;
  if (!strcmp(nm, "CSRHBOTD")) return model_.CSRHBOTD;
  if (!strcmp(nm, "CSRHSTID")) return model_.CSRHSTID;
  if (!strcmp(nm, "CSRHGATD")) return model_.CSRHGATD;
  if (!strcmp(nm, "XJUNSTID")) return model_.XJUNSTID;
  if (!strcmp(nm, "XJUNGATD")) return model_.XJUNGATD;
  if (!strcmp(nm, "CTATBOTD")) return model_.CTATBOTD;
  if (!strcmp(nm, "CTATSTID")) return model_.CTATSTID;
  if (!strcmp(nm, "CTATGATD")) return model_.CTATGATD;
  if (!strcmp(nm, "MEFFTATBOTD")) return model_.MEFFTATBOTD;
  if (!strcmp(nm, "MEFFTATSTID")) return model_.MEFFTATSTID;
  if (!strcmp(nm, "MEFFTATGATD")) return model_.MEFFTATGATD;
  if (!strcmp(nm, "CBBTBOTD")) return model_.CBBTBOTD;
  if (!strcmp(nm, "CBBTSTID")) return model_.CBBTSTID;
  if (!strcmp(nm, "CBBTGATD")) return model_.CBBTGATD;
  if (!strcmp(nm, "FBBTRBOTD")) return model_.FBBTRBOTD;
  if (!strcmp(nm, "FBBTRSTID")) return model_.FBBTRSTID;
  if (!strcmp(nm, "FBBTRGATD")) return model_.FBBTRGATD;
  if (!strcmp(nm, "STFBBTBOTD")) return model_.STFBBTBOTD;
  if (!strcmp(nm, "STFBBTSTID")) return model_.STFBBTSTID;
  if (!strcmp(nm, "STFBBTGATD")) return model_.STFBBTGATD;
  if (!strcmp(nm, "VBRBOTD")) return model_.VBRBOTD;
  if (!strcmp(nm, "VBRSTID")) return model_.VBRSTID;
  if (!strcmp(nm, "VBRGATD")) return model_.VBRGATD;
  if (!strcmp(nm, "PBRBOTD")) return model_.PBRBOTD;
  if (!strcmp(nm, "PBRSTID")) return model_.PBRSTID;
  if (!strcmp(nm, "PBRGATD")) return model_.PBRGATD;
  if (!strcmp(nm, "SWJUNEXP")) return model_.SWJUNEXP;
  if (!strcmp(nm, "VJUNREF")) return model_.VJUNREF;
  if (!strcmp(nm, "FJUNQ")) return model_.FJUNQ;
  if (!strcmp(nm, "VJUNREFD")) return model_.VJUNREFD;
  if (!strcmp(nm, "FJUNQD")) return model_.FJUNQD;
  return 0.0;
}
static Instance* g_pyms_cur = nullptr;
static double pyms_param_cb(const char* nm) { return g_pyms_cur ? g_pyms_cur->getCbParam(nm) : 0.0; }

bool Instance::processParams() {
  if (!vae_eval_) {
    // (1) explicit override: VAE_SO_PATH, or VAE_SO_DIR/<MODEL>.so
    std::string so_path;
    const char *so = getenv("VAE_SO_PATH");
    const char *dir = getenv("VAE_SO_DIR");
    if (so) so_path = so;
    else if (dir) so_path = std::string(dir) + "/" + model_.getName() + ".so";
    if (!so_path.empty()) {
      vae_dl_ = dlopen(so_path.c_str(), RTLD_NOW);
      if (vae_dl_) { vae_eval_ = (VaeEvalFn)dlsym(vae_dl_, "vae_eval");
                     vae_jac_ = (VaeEvalFn)dlsym(vae_dl_, "vae_jacobian"); }
    }
    // (2) JIT per-instance build: bake THIS instance's params into a
    // GiNaC vae_eval .so via build_vae_so.py, cached by (va, params) hash.
    if (!vae_eval_) {
      const char *_va = "/usr/local/share/xyce/verilog-a/psp103/psp103.va";
      std::string _p; char _pb[96];
      std::string _cbwrap;
      { const char* _cbe = getenv("PYMS_CALLBACK_PARAMS");
        if (_cbe) { std::string _s=_cbe; for(char&ch:_s) ch=toupper((unsigned char)ch); _cbwrap = "," + _s + ","; } }
      snprintf(_pb,sizeof(_pb),"LEVEL=%.12g\n",(_cbwrap.find(",LEVEL,")!=std::string::npos)?0.0:(double)(model_.LEVEL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"TYPE=%.12g\n",(_cbwrap.find(",TYPE,")!=std::string::npos)?0.0:(double)(model_.TYPE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"TR=%.12g\n",(_cbwrap.find(",TR,")!=std::string::npos)?0.0:(double)(model_.TR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SWGEO=%.12g\n",(_cbwrap.find(",SWGEO,")!=std::string::npos)?0.0:(double)(model_.SWGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SWIGATE=%.12g\n",(_cbwrap.find(",SWIGATE,")!=std::string::npos)?0.0:(double)(model_.SWIGATE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SWIMPACT=%.12g\n",(_cbwrap.find(",SWIMPACT,")!=std::string::npos)?0.0:(double)(model_.SWIMPACT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SWGIDL=%.12g\n",(_cbwrap.find(",SWGIDL,")!=std::string::npos)?0.0:(double)(model_.SWGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SWJUNCAP=%.12g\n",(_cbwrap.find(",SWJUNCAP,")!=std::string::npos)?0.0:(double)(model_.SWJUNCAP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SWJUNASYM=%.12g\n",(_cbwrap.find(",SWJUNASYM,")!=std::string::npos)?0.0:(double)(model_.SWJUNASYM)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SWNUD=%.12g\n",(_cbwrap.find(",SWNUD,")!=std::string::npos)?0.0:(double)(model_.SWNUD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SWEDGE=%.12g\n",(_cbwrap.find(",SWEDGE,")!=std::string::npos)?0.0:(double)(model_.SWEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SWDELVTAC=%.12g\n",(_cbwrap.find(",SWDELVTAC,")!=std::string::npos)?0.0:(double)(model_.SWDELVTAC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SWIGN=%.12g\n",(_cbwrap.find(",SWIGN,")!=std::string::npos)?0.0:(double)(model_.SWIGN)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"QMC=%.12g\n",(_cbwrap.find(",QMC,")!=std::string::npos)?0.0:(double)(model_.QMC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"L=%.12g\n",(_cbwrap.find(",L,")!=std::string::npos)?0.0:(double)(L)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"W=%.12g\n",(_cbwrap.find(",W,")!=std::string::npos)?0.0:(double)(W)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SA=%.12g\n",(_cbwrap.find(",SA,")!=std::string::npos)?0.0:(double)(SA)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SB=%.12g\n",(_cbwrap.find(",SB,")!=std::string::npos)?0.0:(double)(SB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SD=%.12g\n",(_cbwrap.find(",SD,")!=std::string::npos)?0.0:(double)(SD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SCA=%.12g\n",(_cbwrap.find(",SCA,")!=std::string::npos)?0.0:(double)(SCA)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SCB=%.12g\n",(_cbwrap.find(",SCB,")!=std::string::npos)?0.0:(double)(SCB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SCC=%.12g\n",(_cbwrap.find(",SCC,")!=std::string::npos)?0.0:(double)(SCC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SC=%.12g\n",(_cbwrap.find(",SC,")!=std::string::npos)?0.0:(double)(SC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NF=%.12g\n",(_cbwrap.find(",NF,")!=std::string::npos)?0.0:(double)(NF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NGCON=%.12g\n",(_cbwrap.find(",NGCON,")!=std::string::npos)?0.0:(double)(NGCON)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"XGW=%.12g\n",(_cbwrap.find(",XGW,")!=std::string::npos)?0.0:(double)(XGW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NRS=%.12g\n",(_cbwrap.find(",NRS,")!=std::string::npos)?0.0:(double)(NRS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NRD=%.12g\n",(_cbwrap.find(",NRD,")!=std::string::npos)?0.0:(double)(NRD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"JW=%.12g\n",(_cbwrap.find(",JW,")!=std::string::npos)?0.0:(double)(JW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DELVTO=%.12g\n",(_cbwrap.find(",DELVTO,")!=std::string::npos)?0.0:(double)(DELVTO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FACTUO=%.12g\n",(_cbwrap.find(",FACTUO,")!=std::string::npos)?0.0:(double)(FACTUO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DELVTOEDGE=%.12g\n",(_cbwrap.find(",DELVTOEDGE,")!=std::string::npos)?0.0:(double)(DELVTOEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FACTUOEDGE=%.12g\n",(_cbwrap.find(",FACTUOEDGE,")!=std::string::npos)?0.0:(double)(FACTUOEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ABSOURCE=%.12g\n",(_cbwrap.find(",ABSOURCE,")!=std::string::npos)?0.0:(double)(ABSOURCE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LSSOURCE=%.12g\n",(_cbwrap.find(",LSSOURCE,")!=std::string::npos)?0.0:(double)(LSSOURCE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LGSOURCE=%.12g\n",(_cbwrap.find(",LGSOURCE,")!=std::string::npos)?0.0:(double)(LGSOURCE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ABDRAIN=%.12g\n",(_cbwrap.find(",ABDRAIN,")!=std::string::npos)?0.0:(double)(ABDRAIN)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LSDRAIN=%.12g\n",(_cbwrap.find(",LSDRAIN,")!=std::string::npos)?0.0:(double)(LSDRAIN)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LGDRAIN=%.12g\n",(_cbwrap.find(",LGDRAIN,")!=std::string::npos)?0.0:(double)(LGDRAIN)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"AS=%.12g\n",(_cbwrap.find(",AS,")!=std::string::npos)?0.0:(double)(AS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PS=%.12g\n",(_cbwrap.find(",PS,")!=std::string::npos)?0.0:(double)(PS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"AD=%.12g\n",(_cbwrap.find(",AD,")!=std::string::npos)?0.0:(double)(AD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PD=%.12g\n",(_cbwrap.find(",PD,")!=std::string::npos)?0.0:(double)(PD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"MULT=%.12g\n",(_cbwrap.find(",MULT,")!=std::string::npos)?0.0:(double)(MULT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VFB=%.12g\n",(_cbwrap.find(",VFB,")!=std::string::npos)?0.0:(double)(model_.VFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STVFB=%.12g\n",(_cbwrap.find(",STVFB,")!=std::string::npos)?0.0:(double)(model_.STVFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"TOX=%.12g\n",(_cbwrap.find(",TOX,")!=std::string::npos)?0.0:(double)(model_.TOX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"EPSROX=%.12g\n",(_cbwrap.find(",EPSROX,")!=std::string::npos)?0.0:(double)(model_.EPSROX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NEFF=%.12g\n",(_cbwrap.find(",NEFF,")!=std::string::npos)?0.0:(double)(model_.NEFF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FACNEFFAC=%.12g\n",(_cbwrap.find(",FACNEFFAC,")!=std::string::npos)?0.0:(double)(model_.FACNEFFAC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GFACNUD=%.12g\n",(_cbwrap.find(",GFACNUD,")!=std::string::npos)?0.0:(double)(model_.GFACNUD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VSBNUD=%.12g\n",(_cbwrap.find(",VSBNUD,")!=std::string::npos)?0.0:(double)(model_.VSBNUD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DVSBNUD=%.12g\n",(_cbwrap.find(",DVSBNUD,")!=std::string::npos)?0.0:(double)(model_.DVSBNUD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VNSUB=%.12g\n",(_cbwrap.find(",VNSUB,")!=std::string::npos)?0.0:(double)(model_.VNSUB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NSLP=%.12g\n",(_cbwrap.find(",NSLP,")!=std::string::npos)?0.0:(double)(model_.NSLP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DNSUB=%.12g\n",(_cbwrap.find(",DNSUB,")!=std::string::npos)?0.0:(double)(model_.DNSUB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIB=%.12g\n",(_cbwrap.find(",DPHIB,")!=std::string::npos)?0.0:(double)(model_.DPHIB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DELVTAC=%.12g\n",(_cbwrap.find(",DELVTAC,")!=std::string::npos)?0.0:(double)(model_.DELVTAC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NP=%.12g\n",(_cbwrap.find(",NP,")!=std::string::npos)?0.0:(double)(model_.NP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CT=%.12g\n",(_cbwrap.find(",CT,")!=std::string::npos)?0.0:(double)(model_.CT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"TOXOV=%.12g\n",(_cbwrap.find(",TOXOV,")!=std::string::npos)?0.0:(double)(model_.TOXOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"TOXOVD=%.12g\n",(_cbwrap.find(",TOXOVD,")!=std::string::npos)?0.0:(double)(model_.TOXOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NOV=%.12g\n",(_cbwrap.find(",NOV,")!=std::string::npos)?0.0:(double)(model_.NOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NOVD=%.12g\n",(_cbwrap.find(",NOVD,")!=std::string::npos)?0.0:(double)(model_.NOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CF=%.12g\n",(_cbwrap.find(",CF,")!=std::string::npos)?0.0:(double)(model_.CF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFD=%.12g\n",(_cbwrap.find(",CFD,")!=std::string::npos)?0.0:(double)(model_.CFD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFB=%.12g\n",(_cbwrap.find(",CFB,")!=std::string::npos)?0.0:(double)(model_.CFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCE=%.12g\n",(_cbwrap.find(",PSCE,")!=std::string::npos)?0.0:(double)(model_.PSCE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEB=%.12g\n",(_cbwrap.find(",PSCEB,")!=std::string::npos)?0.0:(double)(model_.PSCEB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCED=%.12g\n",(_cbwrap.find(",PSCED,")!=std::string::npos)?0.0:(double)(model_.PSCED)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"BETN=%.12g\n",(_cbwrap.find(",BETN,")!=std::string::npos)?0.0:(double)(model_.BETN)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBET=%.12g\n",(_cbwrap.find(",STBET,")!=std::string::npos)?0.0:(double)(model_.STBET)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"MUE=%.12g\n",(_cbwrap.find(",MUE,")!=std::string::npos)?0.0:(double)(model_.MUE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STMUE=%.12g\n",(_cbwrap.find(",STMUE,")!=std::string::npos)?0.0:(double)(model_.STMUE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THEMU=%.12g\n",(_cbwrap.find(",THEMU,")!=std::string::npos)?0.0:(double)(model_.THEMU)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STTHEMU=%.12g\n",(_cbwrap.find(",STTHEMU,")!=std::string::npos)?0.0:(double)(model_.STTHEMU)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CS=%.12g\n",(_cbwrap.find(",CS,")!=std::string::npos)?0.0:(double)(model_.CS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STCS=%.12g\n",(_cbwrap.find(",STCS,")!=std::string::npos)?0.0:(double)(model_.STCS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"XCOR=%.12g\n",(_cbwrap.find(",XCOR,")!=std::string::npos)?0.0:(double)(model_.XCOR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STXCOR=%.12g\n",(_cbwrap.find(",STXCOR,")!=std::string::npos)?0.0:(double)(model_.STXCOR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FETA=%.12g\n",(_cbwrap.find(",FETA,")!=std::string::npos)?0.0:(double)(model_.FETA)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RS=%.12g\n",(_cbwrap.find(",RS,")!=std::string::npos)?0.0:(double)(model_.RS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STRS=%.12g\n",(_cbwrap.find(",STRS,")!=std::string::npos)?0.0:(double)(model_.STRS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RSB=%.12g\n",(_cbwrap.find(",RSB,")!=std::string::npos)?0.0:(double)(model_.RSB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RSG=%.12g\n",(_cbwrap.find(",RSG,")!=std::string::npos)?0.0:(double)(model_.RSG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THESAT=%.12g\n",(_cbwrap.find(",THESAT,")!=std::string::npos)?0.0:(double)(model_.THESAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STTHESAT=%.12g\n",(_cbwrap.find(",STTHESAT,")!=std::string::npos)?0.0:(double)(model_.STTHESAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THESATB=%.12g\n",(_cbwrap.find(",THESATB,")!=std::string::npos)?0.0:(double)(model_.THESATB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THESATG=%.12g\n",(_cbwrap.find(",THESATG,")!=std::string::npos)?0.0:(double)(model_.THESATG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"AX=%.12g\n",(_cbwrap.find(",AX,")!=std::string::npos)?0.0:(double)(model_.AX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALP=%.12g\n",(_cbwrap.find(",ALP,")!=std::string::npos)?0.0:(double)(model_.ALP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALP1=%.12g\n",(_cbwrap.find(",ALP1,")!=std::string::npos)?0.0:(double)(model_.ALP1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALP2=%.12g\n",(_cbwrap.find(",ALP2,")!=std::string::npos)?0.0:(double)(model_.ALP2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VP=%.12g\n",(_cbwrap.find(",VP,")!=std::string::npos)?0.0:(double)(model_.VP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A1=%.12g\n",(_cbwrap.find(",A1,")!=std::string::npos)?0.0:(double)(model_.A1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A2=%.12g\n",(_cbwrap.find(",A2,")!=std::string::npos)?0.0:(double)(model_.A2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STA2=%.12g\n",(_cbwrap.find(",STA2,")!=std::string::npos)?0.0:(double)(model_.STA2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A3=%.12g\n",(_cbwrap.find(",A3,")!=std::string::npos)?0.0:(double)(model_.A3)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A4=%.12g\n",(_cbwrap.find(",A4,")!=std::string::npos)?0.0:(double)(model_.A4)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GCO=%.12g\n",(_cbwrap.find(",GCO,")!=std::string::npos)?0.0:(double)(model_.GCO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IGINV=%.12g\n",(_cbwrap.find(",IGINV,")!=std::string::npos)?0.0:(double)(model_.IGINV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IGOV=%.12g\n",(_cbwrap.find(",IGOV,")!=std::string::npos)?0.0:(double)(model_.IGOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IGOVD=%.12g\n",(_cbwrap.find(",IGOVD,")!=std::string::npos)?0.0:(double)(model_.IGOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STIG=%.12g\n",(_cbwrap.find(",STIG,")!=std::string::npos)?0.0:(double)(model_.STIG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GC2=%.12g\n",(_cbwrap.find(",GC2,")!=std::string::npos)?0.0:(double)(model_.GC2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GC3=%.12g\n",(_cbwrap.find(",GC3,")!=std::string::npos)?0.0:(double)(model_.GC3)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CHIB=%.12g\n",(_cbwrap.find(",CHIB,")!=std::string::npos)?0.0:(double)(model_.CHIB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"AGIDL=%.12g\n",(_cbwrap.find(",AGIDL,")!=std::string::npos)?0.0:(double)(model_.AGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"AGIDLD=%.12g\n",(_cbwrap.find(",AGIDLD,")!=std::string::npos)?0.0:(double)(model_.AGIDLD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"BGIDL=%.12g\n",(_cbwrap.find(",BGIDL,")!=std::string::npos)?0.0:(double)(model_.BGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"BGIDLD=%.12g\n",(_cbwrap.find(",BGIDLD,")!=std::string::npos)?0.0:(double)(model_.BGIDLD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBGIDL=%.12g\n",(_cbwrap.find(",STBGIDL,")!=std::string::npos)?0.0:(double)(model_.STBGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBGIDLD=%.12g\n",(_cbwrap.find(",STBGIDLD,")!=std::string::npos)?0.0:(double)(model_.STBGIDLD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CGIDL=%.12g\n",(_cbwrap.find(",CGIDL,")!=std::string::npos)?0.0:(double)(model_.CGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CGIDLD=%.12g\n",(_cbwrap.find(",CGIDLD,")!=std::string::npos)?0.0:(double)(model_.CGIDLD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"COX=%.12g\n",(_cbwrap.find(",COX,")!=std::string::npos)?0.0:(double)(model_.COX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CGOV=%.12g\n",(_cbwrap.find(",CGOV,")!=std::string::npos)?0.0:(double)(model_.CGOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CGOVD=%.12g\n",(_cbwrap.find(",CGOVD,")!=std::string::npos)?0.0:(double)(model_.CGOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CGBOV=%.12g\n",(_cbwrap.find(",CGBOV,")!=std::string::npos)?0.0:(double)(model_.CGBOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFR=%.12g\n",(_cbwrap.find(",CFR,")!=std::string::npos)?0.0:(double)(model_.CFR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFRD=%.12g\n",(_cbwrap.find(",CFRD,")!=std::string::npos)?0.0:(double)(model_.CFRD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FNT=%.12g\n",(_cbwrap.find(",FNT,")!=std::string::npos)?0.0:(double)(model_.FNT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FNTEXC=%.12g\n",(_cbwrap.find(",FNTEXC,")!=std::string::npos)?0.0:(double)(model_.FNTEXC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFA=%.12g\n",(_cbwrap.find(",NFA,")!=std::string::npos)?0.0:(double)(model_.NFA)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFB=%.12g\n",(_cbwrap.find(",NFB,")!=std::string::npos)?0.0:(double)(model_.NFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFC=%.12g\n",(_cbwrap.find(",NFC,")!=std::string::npos)?0.0:(double)(model_.NFC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"EF=%.12g\n",(_cbwrap.find(",EF,")!=std::string::npos)?0.0:(double)(model_.EF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VFBEDGE=%.12g\n",(_cbwrap.find(",VFBEDGE,")!=std::string::npos)?0.0:(double)(model_.VFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STVFBEDGE=%.12g\n",(_cbwrap.find(",STVFBEDGE,")!=std::string::npos)?0.0:(double)(model_.STVFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIBEDGE=%.12g\n",(_cbwrap.find(",DPHIBEDGE,")!=std::string::npos)?0.0:(double)(model_.DPHIBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NEFFEDGE=%.12g\n",(_cbwrap.find(",NEFFEDGE,")!=std::string::npos)?0.0:(double)(model_.NEFFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTEDGE=%.12g\n",(_cbwrap.find(",CTEDGE,")!=std::string::npos)?0.0:(double)(model_.CTEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"BETNEDGE=%.12g\n",(_cbwrap.find(",BETNEDGE,")!=std::string::npos)?0.0:(double)(model_.BETNEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBETEDGE=%.12g\n",(_cbwrap.find(",STBETEDGE,")!=std::string::npos)?0.0:(double)(model_.STBETEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEEDGE=%.12g\n",(_cbwrap.find(",PSCEEDGE,")!=std::string::npos)?0.0:(double)(model_.PSCEEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEBEDGE=%.12g\n",(_cbwrap.find(",PSCEBEDGE,")!=std::string::npos)?0.0:(double)(model_.PSCEBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEDEDGE=%.12g\n",(_cbwrap.find(",PSCEDEDGE,")!=std::string::npos)?0.0:(double)(model_.PSCEDEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFEDGE=%.12g\n",(_cbwrap.find(",CFEDGE,")!=std::string::npos)?0.0:(double)(model_.CFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFDEDGE=%.12g\n",(_cbwrap.find(",CFDEDGE,")!=std::string::npos)?0.0:(double)(model_.CFDEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFBEDGE=%.12g\n",(_cbwrap.find(",CFBEDGE,")!=std::string::npos)?0.0:(double)(model_.CFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FNTEDGE=%.12g\n",(_cbwrap.find(",FNTEDGE,")!=std::string::npos)?0.0:(double)(model_.FNTEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFAEDGE=%.12g\n",(_cbwrap.find(",NFAEDGE,")!=std::string::npos)?0.0:(double)(model_.NFAEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFBEDGE=%.12g\n",(_cbwrap.find(",NFBEDGE,")!=std::string::npos)?0.0:(double)(model_.NFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFCEDGE=%.12g\n",(_cbwrap.find(",NFCEDGE,")!=std::string::npos)?0.0:(double)(model_.NFCEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"EFEDGE=%.12g\n",(_cbwrap.find(",EFEDGE,")!=std::string::npos)?0.0:(double)(model_.EFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RG=%.12g\n",(_cbwrap.find(",RG,")!=std::string::npos)?0.0:(double)(model_.RG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RSE=%.12g\n",(_cbwrap.find(",RSE,")!=std::string::npos)?0.0:(double)(model_.RSE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RDE=%.12g\n",(_cbwrap.find(",RDE,")!=std::string::npos)?0.0:(double)(model_.RDE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RBULK=%.12g\n",(_cbwrap.find(",RBULK,")!=std::string::npos)?0.0:(double)(model_.RBULK)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RWELL=%.12g\n",(_cbwrap.find(",RWELL,")!=std::string::npos)?0.0:(double)(model_.RWELL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RJUNS=%.12g\n",(_cbwrap.find(",RJUNS,")!=std::string::npos)?0.0:(double)(model_.RJUNS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RJUND=%.12g\n",(_cbwrap.find(",RJUND,")!=std::string::npos)?0.0:(double)(model_.RJUND)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POVFB=%.12g\n",(_cbwrap.find(",POVFB,")!=std::string::npos)?0.0:(double)(model_.POVFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLVFB=%.12g\n",(_cbwrap.find(",PLVFB,")!=std::string::npos)?0.0:(double)(model_.PLVFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWVFB=%.12g\n",(_cbwrap.find(",PWVFB,")!=std::string::npos)?0.0:(double)(model_.PWVFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWVFB=%.12g\n",(_cbwrap.find(",PLWVFB,")!=std::string::npos)?0.0:(double)(model_.PLWVFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTVFB=%.12g\n",(_cbwrap.find(",POSTVFB,")!=std::string::npos)?0.0:(double)(model_.POSTVFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLSTVFB=%.12g\n",(_cbwrap.find(",PLSTVFB,")!=std::string::npos)?0.0:(double)(model_.PLSTVFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWSTVFB=%.12g\n",(_cbwrap.find(",PWSTVFB,")!=std::string::npos)?0.0:(double)(model_.PWSTVFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWSTVFB=%.12g\n",(_cbwrap.find(",PLWSTVFB,")!=std::string::npos)?0.0:(double)(model_.PLWSTVFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POTOX=%.12g\n",(_cbwrap.find(",POTOX,")!=std::string::npos)?0.0:(double)(model_.POTOX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POEPSROX=%.12g\n",(_cbwrap.find(",POEPSROX,")!=std::string::npos)?0.0:(double)(model_.POEPSROX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONEFF=%.12g\n",(_cbwrap.find(",PONEFF,")!=std::string::npos)?0.0:(double)(model_.PONEFF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLNEFF=%.12g\n",(_cbwrap.find(",PLNEFF,")!=std::string::npos)?0.0:(double)(model_.PLNEFF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWNEFF=%.12g\n",(_cbwrap.find(",PWNEFF,")!=std::string::npos)?0.0:(double)(model_.PWNEFF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWNEFF=%.12g\n",(_cbwrap.find(",PLWNEFF,")!=std::string::npos)?0.0:(double)(model_.PLWNEFF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POFACNEFFAC=%.12g\n",(_cbwrap.find(",POFACNEFFAC,")!=std::string::npos)?0.0:(double)(model_.POFACNEFFAC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLFACNEFFAC=%.12g\n",(_cbwrap.find(",PLFACNEFFAC,")!=std::string::npos)?0.0:(double)(model_.PLFACNEFFAC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWFACNEFFAC=%.12g\n",(_cbwrap.find(",PWFACNEFFAC,")!=std::string::npos)?0.0:(double)(model_.PWFACNEFFAC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWFACNEFFAC=%.12g\n",(_cbwrap.find(",PLWFACNEFFAC,")!=std::string::npos)?0.0:(double)(model_.PLWFACNEFFAC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POGFACNUD=%.12g\n",(_cbwrap.find(",POGFACNUD,")!=std::string::npos)?0.0:(double)(model_.POGFACNUD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLGFACNUD=%.12g\n",(_cbwrap.find(",PLGFACNUD,")!=std::string::npos)?0.0:(double)(model_.PLGFACNUD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWGFACNUD=%.12g\n",(_cbwrap.find(",PWGFACNUD,")!=std::string::npos)?0.0:(double)(model_.PWGFACNUD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWGFACNUD=%.12g\n",(_cbwrap.find(",PLWGFACNUD,")!=std::string::npos)?0.0:(double)(model_.PLWGFACNUD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POVSBNUD=%.12g\n",(_cbwrap.find(",POVSBNUD,")!=std::string::npos)?0.0:(double)(model_.POVSBNUD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PODVSBNUD=%.12g\n",(_cbwrap.find(",PODVSBNUD,")!=std::string::npos)?0.0:(double)(model_.PODVSBNUD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POVNSUB=%.12g\n",(_cbwrap.find(",POVNSUB,")!=std::string::npos)?0.0:(double)(model_.POVNSUB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONSLP=%.12g\n",(_cbwrap.find(",PONSLP,")!=std::string::npos)?0.0:(double)(model_.PONSLP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PODNSUB=%.12g\n",(_cbwrap.find(",PODNSUB,")!=std::string::npos)?0.0:(double)(model_.PODNSUB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PODPHIB=%.12g\n",(_cbwrap.find(",PODPHIB,")!=std::string::npos)?0.0:(double)(model_.PODPHIB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLDPHIB=%.12g\n",(_cbwrap.find(",PLDPHIB,")!=std::string::npos)?0.0:(double)(model_.PLDPHIB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWDPHIB=%.12g\n",(_cbwrap.find(",PWDPHIB,")!=std::string::npos)?0.0:(double)(model_.PWDPHIB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWDPHIB=%.12g\n",(_cbwrap.find(",PLWDPHIB,")!=std::string::npos)?0.0:(double)(model_.PLWDPHIB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PODELVTAC=%.12g\n",(_cbwrap.find(",PODELVTAC,")!=std::string::npos)?0.0:(double)(model_.PODELVTAC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLDELVTAC=%.12g\n",(_cbwrap.find(",PLDELVTAC,")!=std::string::npos)?0.0:(double)(model_.PLDELVTAC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWDELVTAC=%.12g\n",(_cbwrap.find(",PWDELVTAC,")!=std::string::npos)?0.0:(double)(model_.PWDELVTAC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWDELVTAC=%.12g\n",(_cbwrap.find(",PLWDELVTAC,")!=std::string::npos)?0.0:(double)(model_.PLWDELVTAC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONP=%.12g\n",(_cbwrap.find(",PONP,")!=std::string::npos)?0.0:(double)(model_.PONP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLNP=%.12g\n",(_cbwrap.find(",PLNP,")!=std::string::npos)?0.0:(double)(model_.PLNP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWNP=%.12g\n",(_cbwrap.find(",PWNP,")!=std::string::npos)?0.0:(double)(model_.PWNP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWNP=%.12g\n",(_cbwrap.find(",PLWNP,")!=std::string::npos)?0.0:(double)(model_.PLWNP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCT=%.12g\n",(_cbwrap.find(",POCT,")!=std::string::npos)?0.0:(double)(model_.POCT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLCT=%.12g\n",(_cbwrap.find(",PLCT,")!=std::string::npos)?0.0:(double)(model_.PLCT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWCT=%.12g\n",(_cbwrap.find(",PWCT,")!=std::string::npos)?0.0:(double)(model_.PWCT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWCT=%.12g\n",(_cbwrap.find(",PLWCT,")!=std::string::npos)?0.0:(double)(model_.PLWCT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POTOXOV=%.12g\n",(_cbwrap.find(",POTOXOV,")!=std::string::npos)?0.0:(double)(model_.POTOXOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POTOXOVD=%.12g\n",(_cbwrap.find(",POTOXOVD,")!=std::string::npos)?0.0:(double)(model_.POTOXOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONOV=%.12g\n",(_cbwrap.find(",PONOV,")!=std::string::npos)?0.0:(double)(model_.PONOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLNOV=%.12g\n",(_cbwrap.find(",PLNOV,")!=std::string::npos)?0.0:(double)(model_.PLNOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWNOV=%.12g\n",(_cbwrap.find(",PWNOV,")!=std::string::npos)?0.0:(double)(model_.PWNOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWNOV=%.12g\n",(_cbwrap.find(",PLWNOV,")!=std::string::npos)?0.0:(double)(model_.PLWNOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONOVD=%.12g\n",(_cbwrap.find(",PONOVD,")!=std::string::npos)?0.0:(double)(model_.PONOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLNOVD=%.12g\n",(_cbwrap.find(",PLNOVD,")!=std::string::npos)?0.0:(double)(model_.PLNOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWNOVD=%.12g\n",(_cbwrap.find(",PWNOVD,")!=std::string::npos)?0.0:(double)(model_.PWNOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWNOVD=%.12g\n",(_cbwrap.find(",PLWNOVD,")!=std::string::npos)?0.0:(double)(model_.PLWNOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCF=%.12g\n",(_cbwrap.find(",POCF,")!=std::string::npos)?0.0:(double)(model_.POCF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLCF=%.12g\n",(_cbwrap.find(",PLCF,")!=std::string::npos)?0.0:(double)(model_.PLCF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWCF=%.12g\n",(_cbwrap.find(",PWCF,")!=std::string::npos)?0.0:(double)(model_.PWCF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWCF=%.12g\n",(_cbwrap.find(",PLWCF,")!=std::string::npos)?0.0:(double)(model_.PLWCF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCFD=%.12g\n",(_cbwrap.find(",POCFD,")!=std::string::npos)?0.0:(double)(model_.POCFD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCFB=%.12g\n",(_cbwrap.find(",POCFB,")!=std::string::npos)?0.0:(double)(model_.POCFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POPSCE=%.12g\n",(_cbwrap.find(",POPSCE,")!=std::string::npos)?0.0:(double)(model_.POPSCE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLPSCE=%.12g\n",(_cbwrap.find(",PLPSCE,")!=std::string::npos)?0.0:(double)(model_.PLPSCE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWPSCE=%.12g\n",(_cbwrap.find(",PWPSCE,")!=std::string::npos)?0.0:(double)(model_.PWPSCE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWPSCE=%.12g\n",(_cbwrap.find(",PLWPSCE,")!=std::string::npos)?0.0:(double)(model_.PLWPSCE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POPSCEB=%.12g\n",(_cbwrap.find(",POPSCEB,")!=std::string::npos)?0.0:(double)(model_.POPSCEB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POPSCED=%.12g\n",(_cbwrap.find(",POPSCED,")!=std::string::npos)?0.0:(double)(model_.POPSCED)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POBETN=%.12g\n",(_cbwrap.find(",POBETN,")!=std::string::npos)?0.0:(double)(model_.POBETN)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLBETN=%.12g\n",(_cbwrap.find(",PLBETN,")!=std::string::npos)?0.0:(double)(model_.PLBETN)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWBETN=%.12g\n",(_cbwrap.find(",PWBETN,")!=std::string::npos)?0.0:(double)(model_.PWBETN)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWBETN=%.12g\n",(_cbwrap.find(",PLWBETN,")!=std::string::npos)?0.0:(double)(model_.PLWBETN)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTBET=%.12g\n",(_cbwrap.find(",POSTBET,")!=std::string::npos)?0.0:(double)(model_.POSTBET)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLSTBET=%.12g\n",(_cbwrap.find(",PLSTBET,")!=std::string::npos)?0.0:(double)(model_.PLSTBET)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWSTBET=%.12g\n",(_cbwrap.find(",PWSTBET,")!=std::string::npos)?0.0:(double)(model_.PWSTBET)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWSTBET=%.12g\n",(_cbwrap.find(",PLWSTBET,")!=std::string::npos)?0.0:(double)(model_.PLWSTBET)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POMUE=%.12g\n",(_cbwrap.find(",POMUE,")!=std::string::npos)?0.0:(double)(model_.POMUE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLMUE=%.12g\n",(_cbwrap.find(",PLMUE,")!=std::string::npos)?0.0:(double)(model_.PLMUE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWMUE=%.12g\n",(_cbwrap.find(",PWMUE,")!=std::string::npos)?0.0:(double)(model_.PWMUE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWMUE=%.12g\n",(_cbwrap.find(",PLWMUE,")!=std::string::npos)?0.0:(double)(model_.PLWMUE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTMUE=%.12g\n",(_cbwrap.find(",POSTMUE,")!=std::string::npos)?0.0:(double)(model_.POSTMUE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POTHEMU=%.12g\n",(_cbwrap.find(",POTHEMU,")!=std::string::npos)?0.0:(double)(model_.POTHEMU)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTTHEMU=%.12g\n",(_cbwrap.find(",POSTTHEMU,")!=std::string::npos)?0.0:(double)(model_.POSTTHEMU)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCS=%.12g\n",(_cbwrap.find(",POCS,")!=std::string::npos)?0.0:(double)(model_.POCS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLCS=%.12g\n",(_cbwrap.find(",PLCS,")!=std::string::npos)?0.0:(double)(model_.PLCS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWCS=%.12g\n",(_cbwrap.find(",PWCS,")!=std::string::npos)?0.0:(double)(model_.PWCS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWCS=%.12g\n",(_cbwrap.find(",PLWCS,")!=std::string::npos)?0.0:(double)(model_.PLWCS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTCS=%.12g\n",(_cbwrap.find(",POSTCS,")!=std::string::npos)?0.0:(double)(model_.POSTCS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POXCOR=%.12g\n",(_cbwrap.find(",POXCOR,")!=std::string::npos)?0.0:(double)(model_.POXCOR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLXCOR=%.12g\n",(_cbwrap.find(",PLXCOR,")!=std::string::npos)?0.0:(double)(model_.PLXCOR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWXCOR=%.12g\n",(_cbwrap.find(",PWXCOR,")!=std::string::npos)?0.0:(double)(model_.PWXCOR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWXCOR=%.12g\n",(_cbwrap.find(",PLWXCOR,")!=std::string::npos)?0.0:(double)(model_.PLWXCOR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTXCOR=%.12g\n",(_cbwrap.find(",POSTXCOR,")!=std::string::npos)?0.0:(double)(model_.POSTXCOR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POFETA=%.12g\n",(_cbwrap.find(",POFETA,")!=std::string::npos)?0.0:(double)(model_.POFETA)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PORS=%.12g\n",(_cbwrap.find(",PORS,")!=std::string::npos)?0.0:(double)(model_.PORS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLRS=%.12g\n",(_cbwrap.find(",PLRS,")!=std::string::npos)?0.0:(double)(model_.PLRS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWRS=%.12g\n",(_cbwrap.find(",PWRS,")!=std::string::npos)?0.0:(double)(model_.PWRS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWRS=%.12g\n",(_cbwrap.find(",PLWRS,")!=std::string::npos)?0.0:(double)(model_.PLWRS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTRS=%.12g\n",(_cbwrap.find(",POSTRS,")!=std::string::npos)?0.0:(double)(model_.POSTRS)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PORSB=%.12g\n",(_cbwrap.find(",PORSB,")!=std::string::npos)?0.0:(double)(model_.PORSB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PORSG=%.12g\n",(_cbwrap.find(",PORSG,")!=std::string::npos)?0.0:(double)(model_.PORSG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POTHESAT=%.12g\n",(_cbwrap.find(",POTHESAT,")!=std::string::npos)?0.0:(double)(model_.POTHESAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLTHESAT=%.12g\n",(_cbwrap.find(",PLTHESAT,")!=std::string::npos)?0.0:(double)(model_.PLTHESAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWTHESAT=%.12g\n",(_cbwrap.find(",PWTHESAT,")!=std::string::npos)?0.0:(double)(model_.PWTHESAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWTHESAT=%.12g\n",(_cbwrap.find(",PLWTHESAT,")!=std::string::npos)?0.0:(double)(model_.PLWTHESAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTTHESAT=%.12g\n",(_cbwrap.find(",POSTTHESAT,")!=std::string::npos)?0.0:(double)(model_.POSTTHESAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLSTTHESAT=%.12g\n",(_cbwrap.find(",PLSTTHESAT,")!=std::string::npos)?0.0:(double)(model_.PLSTTHESAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWSTTHESAT=%.12g\n",(_cbwrap.find(",PWSTTHESAT,")!=std::string::npos)?0.0:(double)(model_.PWSTTHESAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWSTTHESAT=%.12g\n",(_cbwrap.find(",PLWSTTHESAT,")!=std::string::npos)?0.0:(double)(model_.PLWSTTHESAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POTHESATB=%.12g\n",(_cbwrap.find(",POTHESATB,")!=std::string::npos)?0.0:(double)(model_.POTHESATB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLTHESATB=%.12g\n",(_cbwrap.find(",PLTHESATB,")!=std::string::npos)?0.0:(double)(model_.PLTHESATB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWTHESATB=%.12g\n",(_cbwrap.find(",PWTHESATB,")!=std::string::npos)?0.0:(double)(model_.PWTHESATB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWTHESATB=%.12g\n",(_cbwrap.find(",PLWTHESATB,")!=std::string::npos)?0.0:(double)(model_.PLWTHESATB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POTHESATG=%.12g\n",(_cbwrap.find(",POTHESATG,")!=std::string::npos)?0.0:(double)(model_.POTHESATG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLTHESATG=%.12g\n",(_cbwrap.find(",PLTHESATG,")!=std::string::npos)?0.0:(double)(model_.PLTHESATG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWTHESATG=%.12g\n",(_cbwrap.find(",PWTHESATG,")!=std::string::npos)?0.0:(double)(model_.PWTHESATG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWTHESATG=%.12g\n",(_cbwrap.find(",PLWTHESATG,")!=std::string::npos)?0.0:(double)(model_.PLWTHESATG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POAX=%.12g\n",(_cbwrap.find(",POAX,")!=std::string::npos)?0.0:(double)(model_.POAX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLAX=%.12g\n",(_cbwrap.find(",PLAX,")!=std::string::npos)?0.0:(double)(model_.PLAX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWAX=%.12g\n",(_cbwrap.find(",PWAX,")!=std::string::npos)?0.0:(double)(model_.PWAX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWAX=%.12g\n",(_cbwrap.find(",PLWAX,")!=std::string::npos)?0.0:(double)(model_.PLWAX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POALP=%.12g\n",(_cbwrap.find(",POALP,")!=std::string::npos)?0.0:(double)(model_.POALP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLALP=%.12g\n",(_cbwrap.find(",PLALP,")!=std::string::npos)?0.0:(double)(model_.PLALP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWALP=%.12g\n",(_cbwrap.find(",PWALP,")!=std::string::npos)?0.0:(double)(model_.PWALP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWALP=%.12g\n",(_cbwrap.find(",PLWALP,")!=std::string::npos)?0.0:(double)(model_.PLWALP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POALP1=%.12g\n",(_cbwrap.find(",POALP1,")!=std::string::npos)?0.0:(double)(model_.POALP1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLALP1=%.12g\n",(_cbwrap.find(",PLALP1,")!=std::string::npos)?0.0:(double)(model_.PLALP1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWALP1=%.12g\n",(_cbwrap.find(",PWALP1,")!=std::string::npos)?0.0:(double)(model_.PWALP1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWALP1=%.12g\n",(_cbwrap.find(",PLWALP1,")!=std::string::npos)?0.0:(double)(model_.PLWALP1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POALP2=%.12g\n",(_cbwrap.find(",POALP2,")!=std::string::npos)?0.0:(double)(model_.POALP2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLALP2=%.12g\n",(_cbwrap.find(",PLALP2,")!=std::string::npos)?0.0:(double)(model_.PLALP2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWALP2=%.12g\n",(_cbwrap.find(",PWALP2,")!=std::string::npos)?0.0:(double)(model_.PWALP2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWALP2=%.12g\n",(_cbwrap.find(",PLWALP2,")!=std::string::npos)?0.0:(double)(model_.PLWALP2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POVP=%.12g\n",(_cbwrap.find(",POVP,")!=std::string::npos)?0.0:(double)(model_.POVP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POA1=%.12g\n",(_cbwrap.find(",POA1,")!=std::string::npos)?0.0:(double)(model_.POA1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLA1=%.12g\n",(_cbwrap.find(",PLA1,")!=std::string::npos)?0.0:(double)(model_.PLA1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWA1=%.12g\n",(_cbwrap.find(",PWA1,")!=std::string::npos)?0.0:(double)(model_.PWA1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWA1=%.12g\n",(_cbwrap.find(",PLWA1,")!=std::string::npos)?0.0:(double)(model_.PLWA1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POA2=%.12g\n",(_cbwrap.find(",POA2,")!=std::string::npos)?0.0:(double)(model_.POA2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTA2=%.12g\n",(_cbwrap.find(",POSTA2,")!=std::string::npos)?0.0:(double)(model_.POSTA2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POA3=%.12g\n",(_cbwrap.find(",POA3,")!=std::string::npos)?0.0:(double)(model_.POA3)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLA3=%.12g\n",(_cbwrap.find(",PLA3,")!=std::string::npos)?0.0:(double)(model_.PLA3)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWA3=%.12g\n",(_cbwrap.find(",PWA3,")!=std::string::npos)?0.0:(double)(model_.PWA3)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWA3=%.12g\n",(_cbwrap.find(",PLWA3,")!=std::string::npos)?0.0:(double)(model_.PLWA3)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POA4=%.12g\n",(_cbwrap.find(",POA4,")!=std::string::npos)?0.0:(double)(model_.POA4)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLA4=%.12g\n",(_cbwrap.find(",PLA4,")!=std::string::npos)?0.0:(double)(model_.PLA4)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWA4=%.12g\n",(_cbwrap.find(",PWA4,")!=std::string::npos)?0.0:(double)(model_.PWA4)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWA4=%.12g\n",(_cbwrap.find(",PLWA4,")!=std::string::npos)?0.0:(double)(model_.PLWA4)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POGCO=%.12g\n",(_cbwrap.find(",POGCO,")!=std::string::npos)?0.0:(double)(model_.POGCO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POIGINV=%.12g\n",(_cbwrap.find(",POIGINV,")!=std::string::npos)?0.0:(double)(model_.POIGINV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLIGINV=%.12g\n",(_cbwrap.find(",PLIGINV,")!=std::string::npos)?0.0:(double)(model_.PLIGINV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWIGINV=%.12g\n",(_cbwrap.find(",PWIGINV,")!=std::string::npos)?0.0:(double)(model_.PWIGINV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWIGINV=%.12g\n",(_cbwrap.find(",PLWIGINV,")!=std::string::npos)?0.0:(double)(model_.PLWIGINV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POIGOV=%.12g\n",(_cbwrap.find(",POIGOV,")!=std::string::npos)?0.0:(double)(model_.POIGOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLIGOV=%.12g\n",(_cbwrap.find(",PLIGOV,")!=std::string::npos)?0.0:(double)(model_.PLIGOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWIGOV=%.12g\n",(_cbwrap.find(",PWIGOV,")!=std::string::npos)?0.0:(double)(model_.PWIGOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWIGOV=%.12g\n",(_cbwrap.find(",PLWIGOV,")!=std::string::npos)?0.0:(double)(model_.PLWIGOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POIGOVD=%.12g\n",(_cbwrap.find(",POIGOVD,")!=std::string::npos)?0.0:(double)(model_.POIGOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLIGOVD=%.12g\n",(_cbwrap.find(",PLIGOVD,")!=std::string::npos)?0.0:(double)(model_.PLIGOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWIGOVD=%.12g\n",(_cbwrap.find(",PWIGOVD,")!=std::string::npos)?0.0:(double)(model_.PWIGOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWIGOVD=%.12g\n",(_cbwrap.find(",PLWIGOVD,")!=std::string::npos)?0.0:(double)(model_.PLWIGOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTIG=%.12g\n",(_cbwrap.find(",POSTIG,")!=std::string::npos)?0.0:(double)(model_.POSTIG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POGC2=%.12g\n",(_cbwrap.find(",POGC2,")!=std::string::npos)?0.0:(double)(model_.POGC2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POGC3=%.12g\n",(_cbwrap.find(",POGC3,")!=std::string::npos)?0.0:(double)(model_.POGC3)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCHIB=%.12g\n",(_cbwrap.find(",POCHIB,")!=std::string::npos)?0.0:(double)(model_.POCHIB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POAGIDL=%.12g\n",(_cbwrap.find(",POAGIDL,")!=std::string::npos)?0.0:(double)(model_.POAGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLAGIDL=%.12g\n",(_cbwrap.find(",PLAGIDL,")!=std::string::npos)?0.0:(double)(model_.PLAGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWAGIDL=%.12g\n",(_cbwrap.find(",PWAGIDL,")!=std::string::npos)?0.0:(double)(model_.PWAGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWAGIDL=%.12g\n",(_cbwrap.find(",PLWAGIDL,")!=std::string::npos)?0.0:(double)(model_.PLWAGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POAGIDLD=%.12g\n",(_cbwrap.find(",POAGIDLD,")!=std::string::npos)?0.0:(double)(model_.POAGIDLD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLAGIDLD=%.12g\n",(_cbwrap.find(",PLAGIDLD,")!=std::string::npos)?0.0:(double)(model_.PLAGIDLD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWAGIDLD=%.12g\n",(_cbwrap.find(",PWAGIDLD,")!=std::string::npos)?0.0:(double)(model_.PWAGIDLD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWAGIDLD=%.12g\n",(_cbwrap.find(",PLWAGIDLD,")!=std::string::npos)?0.0:(double)(model_.PLWAGIDLD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POBGIDL=%.12g\n",(_cbwrap.find(",POBGIDL,")!=std::string::npos)?0.0:(double)(model_.POBGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POBGIDLD=%.12g\n",(_cbwrap.find(",POBGIDLD,")!=std::string::npos)?0.0:(double)(model_.POBGIDLD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTBGIDL=%.12g\n",(_cbwrap.find(",POSTBGIDL,")!=std::string::npos)?0.0:(double)(model_.POSTBGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTBGIDLD=%.12g\n",(_cbwrap.find(",POSTBGIDLD,")!=std::string::npos)?0.0:(double)(model_.POSTBGIDLD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCGIDL=%.12g\n",(_cbwrap.find(",POCGIDL,")!=std::string::npos)?0.0:(double)(model_.POCGIDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCGIDLD=%.12g\n",(_cbwrap.find(",POCGIDLD,")!=std::string::npos)?0.0:(double)(model_.POCGIDLD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCOX=%.12g\n",(_cbwrap.find(",POCOX,")!=std::string::npos)?0.0:(double)(model_.POCOX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLCOX=%.12g\n",(_cbwrap.find(",PLCOX,")!=std::string::npos)?0.0:(double)(model_.PLCOX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWCOX=%.12g\n",(_cbwrap.find(",PWCOX,")!=std::string::npos)?0.0:(double)(model_.PWCOX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWCOX=%.12g\n",(_cbwrap.find(",PLWCOX,")!=std::string::npos)?0.0:(double)(model_.PLWCOX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCGOV=%.12g\n",(_cbwrap.find(",POCGOV,")!=std::string::npos)?0.0:(double)(model_.POCGOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLCGOV=%.12g\n",(_cbwrap.find(",PLCGOV,")!=std::string::npos)?0.0:(double)(model_.PLCGOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWCGOV=%.12g\n",(_cbwrap.find(",PWCGOV,")!=std::string::npos)?0.0:(double)(model_.PWCGOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWCGOV=%.12g\n",(_cbwrap.find(",PLWCGOV,")!=std::string::npos)?0.0:(double)(model_.PLWCGOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCGOVD=%.12g\n",(_cbwrap.find(",POCGOVD,")!=std::string::npos)?0.0:(double)(model_.POCGOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLCGOVD=%.12g\n",(_cbwrap.find(",PLCGOVD,")!=std::string::npos)?0.0:(double)(model_.PLCGOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWCGOVD=%.12g\n",(_cbwrap.find(",PWCGOVD,")!=std::string::npos)?0.0:(double)(model_.PWCGOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWCGOVD=%.12g\n",(_cbwrap.find(",PLWCGOVD,")!=std::string::npos)?0.0:(double)(model_.PLWCGOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCGBOV=%.12g\n",(_cbwrap.find(",POCGBOV,")!=std::string::npos)?0.0:(double)(model_.POCGBOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLCGBOV=%.12g\n",(_cbwrap.find(",PLCGBOV,")!=std::string::npos)?0.0:(double)(model_.PLCGBOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWCGBOV=%.12g\n",(_cbwrap.find(",PWCGBOV,")!=std::string::npos)?0.0:(double)(model_.PWCGBOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWCGBOV=%.12g\n",(_cbwrap.find(",PLWCGBOV,")!=std::string::npos)?0.0:(double)(model_.PLWCGBOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCFR=%.12g\n",(_cbwrap.find(",POCFR,")!=std::string::npos)?0.0:(double)(model_.POCFR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLCFR=%.12g\n",(_cbwrap.find(",PLCFR,")!=std::string::npos)?0.0:(double)(model_.PLCFR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWCFR=%.12g\n",(_cbwrap.find(",PWCFR,")!=std::string::npos)?0.0:(double)(model_.PWCFR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWCFR=%.12g\n",(_cbwrap.find(",PLWCFR,")!=std::string::npos)?0.0:(double)(model_.PLWCFR)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCFRD=%.12g\n",(_cbwrap.find(",POCFRD,")!=std::string::npos)?0.0:(double)(model_.POCFRD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLCFRD=%.12g\n",(_cbwrap.find(",PLCFRD,")!=std::string::npos)?0.0:(double)(model_.PLCFRD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWCFRD=%.12g\n",(_cbwrap.find(",PWCFRD,")!=std::string::npos)?0.0:(double)(model_.PWCFRD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWCFRD=%.12g\n",(_cbwrap.find(",PLWCFRD,")!=std::string::npos)?0.0:(double)(model_.PLWCFRD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POFNT=%.12g\n",(_cbwrap.find(",POFNT,")!=std::string::npos)?0.0:(double)(model_.POFNT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POFNTEXC=%.12g\n",(_cbwrap.find(",POFNTEXC,")!=std::string::npos)?0.0:(double)(model_.POFNTEXC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLFNTEXC=%.12g\n",(_cbwrap.find(",PLFNTEXC,")!=std::string::npos)?0.0:(double)(model_.PLFNTEXC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWFNTEXC=%.12g\n",(_cbwrap.find(",PWFNTEXC,")!=std::string::npos)?0.0:(double)(model_.PWFNTEXC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWFNTEXC=%.12g\n",(_cbwrap.find(",PLWFNTEXC,")!=std::string::npos)?0.0:(double)(model_.PLWFNTEXC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONFA=%.12g\n",(_cbwrap.find(",PONFA,")!=std::string::npos)?0.0:(double)(model_.PONFA)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLNFA=%.12g\n",(_cbwrap.find(",PLNFA,")!=std::string::npos)?0.0:(double)(model_.PLNFA)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWNFA=%.12g\n",(_cbwrap.find(",PWNFA,")!=std::string::npos)?0.0:(double)(model_.PWNFA)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWNFA=%.12g\n",(_cbwrap.find(",PLWNFA,")!=std::string::npos)?0.0:(double)(model_.PLWNFA)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONFB=%.12g\n",(_cbwrap.find(",PONFB,")!=std::string::npos)?0.0:(double)(model_.PONFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLNFB=%.12g\n",(_cbwrap.find(",PLNFB,")!=std::string::npos)?0.0:(double)(model_.PLNFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWNFB=%.12g\n",(_cbwrap.find(",PWNFB,")!=std::string::npos)?0.0:(double)(model_.PWNFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWNFB=%.12g\n",(_cbwrap.find(",PLWNFB,")!=std::string::npos)?0.0:(double)(model_.PLWNFB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONFC=%.12g\n",(_cbwrap.find(",PONFC,")!=std::string::npos)?0.0:(double)(model_.PONFC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLNFC=%.12g\n",(_cbwrap.find(",PLNFC,")!=std::string::npos)?0.0:(double)(model_.PLNFC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWNFC=%.12g\n",(_cbwrap.find(",PWNFC,")!=std::string::npos)?0.0:(double)(model_.PWNFC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWNFC=%.12g\n",(_cbwrap.find(",PLWNFC,")!=std::string::npos)?0.0:(double)(model_.PLWNFC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POEF=%.12g\n",(_cbwrap.find(",POEF,")!=std::string::npos)?0.0:(double)(model_.POEF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POVFBEDGE=%.12g\n",(_cbwrap.find(",POVFBEDGE,")!=std::string::npos)?0.0:(double)(model_.POVFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTVFBEDGE=%.12g\n",(_cbwrap.find(",POSTVFBEDGE,")!=std::string::npos)?0.0:(double)(model_.POSTVFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLSTVFBEDGE=%.12g\n",(_cbwrap.find(",PLSTVFBEDGE,")!=std::string::npos)?0.0:(double)(model_.PLSTVFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWSTVFBEDGE=%.12g\n",(_cbwrap.find(",PWSTVFBEDGE,")!=std::string::npos)?0.0:(double)(model_.PWSTVFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWSTVFBEDGE=%.12g\n",(_cbwrap.find(",PLWSTVFBEDGE,")!=std::string::npos)?0.0:(double)(model_.PLWSTVFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PODPHIBEDGE=%.12g\n",(_cbwrap.find(",PODPHIBEDGE,")!=std::string::npos)?0.0:(double)(model_.PODPHIBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLDPHIBEDGE=%.12g\n",(_cbwrap.find(",PLDPHIBEDGE,")!=std::string::npos)?0.0:(double)(model_.PLDPHIBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWDPHIBEDGE=%.12g\n",(_cbwrap.find(",PWDPHIBEDGE,")!=std::string::npos)?0.0:(double)(model_.PWDPHIBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWDPHIBEDGE=%.12g\n",(_cbwrap.find(",PLWDPHIBEDGE,")!=std::string::npos)?0.0:(double)(model_.PLWDPHIBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONEFFEDGE=%.12g\n",(_cbwrap.find(",PONEFFEDGE,")!=std::string::npos)?0.0:(double)(model_.PONEFFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLNEFFEDGE=%.12g\n",(_cbwrap.find(",PLNEFFEDGE,")!=std::string::npos)?0.0:(double)(model_.PLNEFFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWNEFFEDGE=%.12g\n",(_cbwrap.find(",PWNEFFEDGE,")!=std::string::npos)?0.0:(double)(model_.PWNEFFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWNEFFEDGE=%.12g\n",(_cbwrap.find(",PLWNEFFEDGE,")!=std::string::npos)?0.0:(double)(model_.PLWNEFFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCTEDGE=%.12g\n",(_cbwrap.find(",POCTEDGE,")!=std::string::npos)?0.0:(double)(model_.POCTEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLCTEDGE=%.12g\n",(_cbwrap.find(",PLCTEDGE,")!=std::string::npos)?0.0:(double)(model_.PLCTEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWCTEDGE=%.12g\n",(_cbwrap.find(",PWCTEDGE,")!=std::string::npos)?0.0:(double)(model_.PWCTEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWCTEDGE=%.12g\n",(_cbwrap.find(",PLWCTEDGE,")!=std::string::npos)?0.0:(double)(model_.PLWCTEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POBETNEDGE=%.12g\n",(_cbwrap.find(",POBETNEDGE,")!=std::string::npos)?0.0:(double)(model_.POBETNEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLBETNEDGE=%.12g\n",(_cbwrap.find(",PLBETNEDGE,")!=std::string::npos)?0.0:(double)(model_.PLBETNEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWBETNEDGE=%.12g\n",(_cbwrap.find(",PWBETNEDGE,")!=std::string::npos)?0.0:(double)(model_.PWBETNEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWBETNEDGE=%.12g\n",(_cbwrap.find(",PLWBETNEDGE,")!=std::string::npos)?0.0:(double)(model_.PLWBETNEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POSTBETEDGE=%.12g\n",(_cbwrap.find(",POSTBETEDGE,")!=std::string::npos)?0.0:(double)(model_.POSTBETEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLSTBETEDGE=%.12g\n",(_cbwrap.find(",PLSTBETEDGE,")!=std::string::npos)?0.0:(double)(model_.PLSTBETEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWSTBETEDGE=%.12g\n",(_cbwrap.find(",PWSTBETEDGE,")!=std::string::npos)?0.0:(double)(model_.PWSTBETEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWSTBETEDGE=%.12g\n",(_cbwrap.find(",PLWSTBETEDGE,")!=std::string::npos)?0.0:(double)(model_.PLWSTBETEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POPSCEEDGE=%.12g\n",(_cbwrap.find(",POPSCEEDGE,")!=std::string::npos)?0.0:(double)(model_.POPSCEEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLPSCEEDGE=%.12g\n",(_cbwrap.find(",PLPSCEEDGE,")!=std::string::npos)?0.0:(double)(model_.PLPSCEEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWPSCEEDGE=%.12g\n",(_cbwrap.find(",PWPSCEEDGE,")!=std::string::npos)?0.0:(double)(model_.PWPSCEEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWPSCEEDGE=%.12g\n",(_cbwrap.find(",PLWPSCEEDGE,")!=std::string::npos)?0.0:(double)(model_.PLWPSCEEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POPSCEBEDGE=%.12g\n",(_cbwrap.find(",POPSCEBEDGE,")!=std::string::npos)?0.0:(double)(model_.POPSCEBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POPSCEDEDGE=%.12g\n",(_cbwrap.find(",POPSCEDEDGE,")!=std::string::npos)?0.0:(double)(model_.POPSCEDEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCFEDGE=%.12g\n",(_cbwrap.find(",POCFEDGE,")!=std::string::npos)?0.0:(double)(model_.POCFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLCFEDGE=%.12g\n",(_cbwrap.find(",PLCFEDGE,")!=std::string::npos)?0.0:(double)(model_.PLCFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWCFEDGE=%.12g\n",(_cbwrap.find(",PWCFEDGE,")!=std::string::npos)?0.0:(double)(model_.PWCFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWCFEDGE=%.12g\n",(_cbwrap.find(",PLWCFEDGE,")!=std::string::npos)?0.0:(double)(model_.PLWCFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCFDEDGE=%.12g\n",(_cbwrap.find(",POCFDEDGE,")!=std::string::npos)?0.0:(double)(model_.POCFDEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POCFBEDGE=%.12g\n",(_cbwrap.find(",POCFBEDGE,")!=std::string::npos)?0.0:(double)(model_.POCFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POFNTEDGE=%.12g\n",(_cbwrap.find(",POFNTEDGE,")!=std::string::npos)?0.0:(double)(model_.POFNTEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONFAEDGE=%.12g\n",(_cbwrap.find(",PONFAEDGE,")!=std::string::npos)?0.0:(double)(model_.PONFAEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLNFAEDGE=%.12g\n",(_cbwrap.find(",PLNFAEDGE,")!=std::string::npos)?0.0:(double)(model_.PLNFAEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWNFAEDGE=%.12g\n",(_cbwrap.find(",PWNFAEDGE,")!=std::string::npos)?0.0:(double)(model_.PWNFAEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWNFAEDGE=%.12g\n",(_cbwrap.find(",PLWNFAEDGE,")!=std::string::npos)?0.0:(double)(model_.PLWNFAEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONFBEDGE=%.12g\n",(_cbwrap.find(",PONFBEDGE,")!=std::string::npos)?0.0:(double)(model_.PONFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLNFBEDGE=%.12g\n",(_cbwrap.find(",PLNFBEDGE,")!=std::string::npos)?0.0:(double)(model_.PLNFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWNFBEDGE=%.12g\n",(_cbwrap.find(",PWNFBEDGE,")!=std::string::npos)?0.0:(double)(model_.PWNFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWNFBEDGE=%.12g\n",(_cbwrap.find(",PLWNFBEDGE,")!=std::string::npos)?0.0:(double)(model_.PLWNFBEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PONFCEDGE=%.12g\n",(_cbwrap.find(",PONFCEDGE,")!=std::string::npos)?0.0:(double)(model_.PONFCEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLNFCEDGE=%.12g\n",(_cbwrap.find(",PLNFCEDGE,")!=std::string::npos)?0.0:(double)(model_.PLNFCEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWNFCEDGE=%.12g\n",(_cbwrap.find(",PWNFCEDGE,")!=std::string::npos)?0.0:(double)(model_.PWNFCEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWNFCEDGE=%.12g\n",(_cbwrap.find(",PLWNFCEDGE,")!=std::string::npos)?0.0:(double)(model_.PLWNFCEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POEFEDGE=%.12g\n",(_cbwrap.find(",POEFEDGE,")!=std::string::npos)?0.0:(double)(model_.POEFEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POKVTHOWE=%.12g\n",(_cbwrap.find(",POKVTHOWE,")!=std::string::npos)?0.0:(double)(model_.POKVTHOWE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLKVTHOWE=%.12g\n",(_cbwrap.find(",PLKVTHOWE,")!=std::string::npos)?0.0:(double)(model_.PLKVTHOWE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWKVTHOWE=%.12g\n",(_cbwrap.find(",PWKVTHOWE,")!=std::string::npos)?0.0:(double)(model_.PWKVTHOWE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWKVTHOWE=%.12g\n",(_cbwrap.find(",PLWKVTHOWE,")!=std::string::npos)?0.0:(double)(model_.PLWKVTHOWE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"POKUOWE=%.12g\n",(_cbwrap.find(",POKUOWE,")!=std::string::npos)?0.0:(double)(model_.POKUOWE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLKUOWE=%.12g\n",(_cbwrap.find(",PLKUOWE,")!=std::string::npos)?0.0:(double)(model_.PLKUOWE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PWKUOWE=%.12g\n",(_cbwrap.find(",PWKUOWE,")!=std::string::npos)?0.0:(double)(model_.PWKUOWE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PLWKUOWE=%.12g\n",(_cbwrap.find(",PLWKUOWE,")!=std::string::npos)?0.0:(double)(model_.PLWKUOWE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LMIN=%.12g\n",(_cbwrap.find(",LMIN,")!=std::string::npos)?0.0:(double)(model_.LMIN)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LMAX=%.12g\n",(_cbwrap.find(",LMAX,")!=std::string::npos)?0.0:(double)(model_.LMAX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WMIN=%.12g\n",(_cbwrap.find(",WMIN,")!=std::string::npos)?0.0:(double)(model_.WMIN)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WMAX=%.12g\n",(_cbwrap.find(",WMAX,")!=std::string::npos)?0.0:(double)(model_.WMAX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LVARO=%.12g\n",(_cbwrap.find(",LVARO,")!=std::string::npos)?0.0:(double)(model_.LVARO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LVARL=%.12g\n",(_cbwrap.find(",LVARL,")!=std::string::npos)?0.0:(double)(model_.LVARL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LVARW=%.12g\n",(_cbwrap.find(",LVARW,")!=std::string::npos)?0.0:(double)(model_.LVARW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LAP=%.12g\n",(_cbwrap.find(",LAP,")!=std::string::npos)?0.0:(double)(model_.LAP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WVARO=%.12g\n",(_cbwrap.find(",WVARO,")!=std::string::npos)?0.0:(double)(model_.WVARO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WVARL=%.12g\n",(_cbwrap.find(",WVARL,")!=std::string::npos)?0.0:(double)(model_.WVARL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WVARW=%.12g\n",(_cbwrap.find(",WVARW,")!=std::string::npos)?0.0:(double)(model_.WVARW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WOT=%.12g\n",(_cbwrap.find(",WOT,")!=std::string::npos)?0.0:(double)(model_.WOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DLQ=%.12g\n",(_cbwrap.find(",DLQ,")!=std::string::npos)?0.0:(double)(model_.DLQ)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DWQ=%.12g\n",(_cbwrap.find(",DWQ,")!=std::string::npos)?0.0:(double)(model_.DWQ)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VFBO=%.12g\n",(_cbwrap.find(",VFBO,")!=std::string::npos)?0.0:(double)(model_.VFBO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VFBL=%.12g\n",(_cbwrap.find(",VFBL,")!=std::string::npos)?0.0:(double)(model_.VFBL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VFBW=%.12g\n",(_cbwrap.find(",VFBW,")!=std::string::npos)?0.0:(double)(model_.VFBW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VFBLW=%.12g\n",(_cbwrap.find(",VFBLW,")!=std::string::npos)?0.0:(double)(model_.VFBLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STVFBO=%.12g\n",(_cbwrap.find(",STVFBO,")!=std::string::npos)?0.0:(double)(model_.STVFBO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STVFBL=%.12g\n",(_cbwrap.find(",STVFBL,")!=std::string::npos)?0.0:(double)(model_.STVFBL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STVFBW=%.12g\n",(_cbwrap.find(",STVFBW,")!=std::string::npos)?0.0:(double)(model_.STVFBW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STVFBLW=%.12g\n",(_cbwrap.find(",STVFBLW,")!=std::string::npos)?0.0:(double)(model_.STVFBLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"TOXO=%.12g\n",(_cbwrap.find(",TOXO,")!=std::string::npos)?0.0:(double)(model_.TOXO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"EPSROXO=%.12g\n",(_cbwrap.find(",EPSROXO,")!=std::string::npos)?0.0:(double)(model_.EPSROXO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NSUBO=%.12g\n",(_cbwrap.find(",NSUBO,")!=std::string::npos)?0.0:(double)(model_.NSUBO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NSUBW=%.12g\n",(_cbwrap.find(",NSUBW,")!=std::string::npos)?0.0:(double)(model_.NSUBW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WSEG=%.12g\n",(_cbwrap.find(",WSEG,")!=std::string::npos)?0.0:(double)(model_.WSEG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NPCK=%.12g\n",(_cbwrap.find(",NPCK,")!=std::string::npos)?0.0:(double)(model_.NPCK)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NPCKW=%.12g\n",(_cbwrap.find(",NPCKW,")!=std::string::npos)?0.0:(double)(model_.NPCKW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WSEGP=%.12g\n",(_cbwrap.find(",WSEGP,")!=std::string::npos)?0.0:(double)(model_.WSEGP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LPCK=%.12g\n",(_cbwrap.find(",LPCK,")!=std::string::npos)?0.0:(double)(model_.LPCK)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LPCKW=%.12g\n",(_cbwrap.find(",LPCKW,")!=std::string::npos)?0.0:(double)(model_.LPCKW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FOL1=%.12g\n",(_cbwrap.find(",FOL1,")!=std::string::npos)?0.0:(double)(model_.FOL1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FOL2=%.12g\n",(_cbwrap.find(",FOL2,")!=std::string::npos)?0.0:(double)(model_.FOL2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FACNEFFACO=%.12g\n",(_cbwrap.find(",FACNEFFACO,")!=std::string::npos)?0.0:(double)(model_.FACNEFFACO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FACNEFFACL=%.12g\n",(_cbwrap.find(",FACNEFFACL,")!=std::string::npos)?0.0:(double)(model_.FACNEFFACL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FACNEFFACW=%.12g\n",(_cbwrap.find(",FACNEFFACW,")!=std::string::npos)?0.0:(double)(model_.FACNEFFACW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FACNEFFACLW=%.12g\n",(_cbwrap.find(",FACNEFFACLW,")!=std::string::npos)?0.0:(double)(model_.FACNEFFACLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GFACNUDO=%.12g\n",(_cbwrap.find(",GFACNUDO,")!=std::string::npos)?0.0:(double)(model_.GFACNUDO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GFACNUDL=%.12g\n",(_cbwrap.find(",GFACNUDL,")!=std::string::npos)?0.0:(double)(model_.GFACNUDL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GFACNUDLEXP=%.12g\n",(_cbwrap.find(",GFACNUDLEXP,")!=std::string::npos)?0.0:(double)(model_.GFACNUDLEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GFACNUDW=%.12g\n",(_cbwrap.find(",GFACNUDW,")!=std::string::npos)?0.0:(double)(model_.GFACNUDW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GFACNUDLW=%.12g\n",(_cbwrap.find(",GFACNUDLW,")!=std::string::npos)?0.0:(double)(model_.GFACNUDLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VSBNUDO=%.12g\n",(_cbwrap.find(",VSBNUDO,")!=std::string::npos)?0.0:(double)(model_.VSBNUDO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DVSBNUDO=%.12g\n",(_cbwrap.find(",DVSBNUDO,")!=std::string::npos)?0.0:(double)(model_.DVSBNUDO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VNSUBO=%.12g\n",(_cbwrap.find(",VNSUBO,")!=std::string::npos)?0.0:(double)(model_.VNSUBO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NSLPO=%.12g\n",(_cbwrap.find(",NSLPO,")!=std::string::npos)?0.0:(double)(model_.NSLPO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DNSUBO=%.12g\n",(_cbwrap.find(",DNSUBO,")!=std::string::npos)?0.0:(double)(model_.DNSUBO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIBO=%.12g\n",(_cbwrap.find(",DPHIBO,")!=std::string::npos)?0.0:(double)(model_.DPHIBO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIBL=%.12g\n",(_cbwrap.find(",DPHIBL,")!=std::string::npos)?0.0:(double)(model_.DPHIBL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIBLEXP=%.12g\n",(_cbwrap.find(",DPHIBLEXP,")!=std::string::npos)?0.0:(double)(model_.DPHIBLEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIBW=%.12g\n",(_cbwrap.find(",DPHIBW,")!=std::string::npos)?0.0:(double)(model_.DPHIBW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIBLW=%.12g\n",(_cbwrap.find(",DPHIBLW,")!=std::string::npos)?0.0:(double)(model_.DPHIBLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DELVTACO=%.12g\n",(_cbwrap.find(",DELVTACO,")!=std::string::npos)?0.0:(double)(model_.DELVTACO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DELVTACL=%.12g\n",(_cbwrap.find(",DELVTACL,")!=std::string::npos)?0.0:(double)(model_.DELVTACL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DELVTACLEXP=%.12g\n",(_cbwrap.find(",DELVTACLEXP,")!=std::string::npos)?0.0:(double)(model_.DELVTACLEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DELVTACW=%.12g\n",(_cbwrap.find(",DELVTACW,")!=std::string::npos)?0.0:(double)(model_.DELVTACW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DELVTACLW=%.12g\n",(_cbwrap.find(",DELVTACLW,")!=std::string::npos)?0.0:(double)(model_.DELVTACLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NPO=%.12g\n",(_cbwrap.find(",NPO,")!=std::string::npos)?0.0:(double)(model_.NPO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NPL=%.12g\n",(_cbwrap.find(",NPL,")!=std::string::npos)?0.0:(double)(model_.NPL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTO=%.12g\n",(_cbwrap.find(",CTO,")!=std::string::npos)?0.0:(double)(model_.CTO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTL=%.12g\n",(_cbwrap.find(",CTL,")!=std::string::npos)?0.0:(double)(model_.CTL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTLEXP=%.12g\n",(_cbwrap.find(",CTLEXP,")!=std::string::npos)?0.0:(double)(model_.CTLEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTW=%.12g\n",(_cbwrap.find(",CTW,")!=std::string::npos)?0.0:(double)(model_.CTW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTLW=%.12g\n",(_cbwrap.find(",CTLW,")!=std::string::npos)?0.0:(double)(model_.CTLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"TOXOVO=%.12g\n",(_cbwrap.find(",TOXOVO,")!=std::string::npos)?0.0:(double)(model_.TOXOVO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"TOXOVDO=%.12g\n",(_cbwrap.find(",TOXOVDO,")!=std::string::npos)?0.0:(double)(model_.TOXOVDO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LOV=%.12g\n",(_cbwrap.find(",LOV,")!=std::string::npos)?0.0:(double)(model_.LOV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LOVD=%.12g\n",(_cbwrap.find(",LOVD,")!=std::string::npos)?0.0:(double)(model_.LOVD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NOVO=%.12g\n",(_cbwrap.find(",NOVO,")!=std::string::npos)?0.0:(double)(model_.NOVO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NOVDO=%.12g\n",(_cbwrap.find(",NOVDO,")!=std::string::npos)?0.0:(double)(model_.NOVDO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFL=%.12g\n",(_cbwrap.find(",CFL,")!=std::string::npos)?0.0:(double)(model_.CFL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFLEXP=%.12g\n",(_cbwrap.find(",CFLEXP,")!=std::string::npos)?0.0:(double)(model_.CFLEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFW=%.12g\n",(_cbwrap.find(",CFW,")!=std::string::npos)?0.0:(double)(model_.CFW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFDO=%.12g\n",(_cbwrap.find(",CFDO,")!=std::string::npos)?0.0:(double)(model_.CFDO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFBO=%.12g\n",(_cbwrap.find(",CFBO,")!=std::string::npos)?0.0:(double)(model_.CFBO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEL=%.12g\n",(_cbwrap.find(",PSCEL,")!=std::string::npos)?0.0:(double)(model_.PSCEL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCELEXP=%.12g\n",(_cbwrap.find(",PSCELEXP,")!=std::string::npos)?0.0:(double)(model_.PSCELEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEW=%.12g\n",(_cbwrap.find(",PSCEW,")!=std::string::npos)?0.0:(double)(model_.PSCEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEBO=%.12g\n",(_cbwrap.find(",PSCEBO,")!=std::string::npos)?0.0:(double)(model_.PSCEBO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEDO=%.12g\n",(_cbwrap.find(",PSCEDO,")!=std::string::npos)?0.0:(double)(model_.PSCEDO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"UO=%.12g\n",(_cbwrap.find(",UO,")!=std::string::npos)?0.0:(double)(model_.UO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FBET1=%.12g\n",(_cbwrap.find(",FBET1,")!=std::string::npos)?0.0:(double)(model_.FBET1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FBET1W=%.12g\n",(_cbwrap.find(",FBET1W,")!=std::string::npos)?0.0:(double)(model_.FBET1W)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LP1=%.12g\n",(_cbwrap.find(",LP1,")!=std::string::npos)?0.0:(double)(model_.LP1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LP1W=%.12g\n",(_cbwrap.find(",LP1W,")!=std::string::npos)?0.0:(double)(model_.LP1W)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FBET2=%.12g\n",(_cbwrap.find(",FBET2,")!=std::string::npos)?0.0:(double)(model_.FBET2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LP2=%.12g\n",(_cbwrap.find(",LP2,")!=std::string::npos)?0.0:(double)(model_.LP2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"BETW1=%.12g\n",(_cbwrap.find(",BETW1,")!=std::string::npos)?0.0:(double)(model_.BETW1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"BETW2=%.12g\n",(_cbwrap.find(",BETW2,")!=std::string::npos)?0.0:(double)(model_.BETW2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WBET=%.12g\n",(_cbwrap.find(",WBET,")!=std::string::npos)?0.0:(double)(model_.WBET)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBETO=%.12g\n",(_cbwrap.find(",STBETO,")!=std::string::npos)?0.0:(double)(model_.STBETO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBETL=%.12g\n",(_cbwrap.find(",STBETL,")!=std::string::npos)?0.0:(double)(model_.STBETL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBETW=%.12g\n",(_cbwrap.find(",STBETW,")!=std::string::npos)?0.0:(double)(model_.STBETW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBETLW=%.12g\n",(_cbwrap.find(",STBETLW,")!=std::string::npos)?0.0:(double)(model_.STBETLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"MUEO=%.12g\n",(_cbwrap.find(",MUEO,")!=std::string::npos)?0.0:(double)(model_.MUEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"MUEW=%.12g\n",(_cbwrap.find(",MUEW,")!=std::string::npos)?0.0:(double)(model_.MUEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STMUEO=%.12g\n",(_cbwrap.find(",STMUEO,")!=std::string::npos)?0.0:(double)(model_.STMUEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THEMUO=%.12g\n",(_cbwrap.find(",THEMUO,")!=std::string::npos)?0.0:(double)(model_.THEMUO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STTHEMUO=%.12g\n",(_cbwrap.find(",STTHEMUO,")!=std::string::npos)?0.0:(double)(model_.STTHEMUO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CSO=%.12g\n",(_cbwrap.find(",CSO,")!=std::string::npos)?0.0:(double)(model_.CSO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CSL=%.12g\n",(_cbwrap.find(",CSL,")!=std::string::npos)?0.0:(double)(model_.CSL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CSLEXP=%.12g\n",(_cbwrap.find(",CSLEXP,")!=std::string::npos)?0.0:(double)(model_.CSLEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CSW=%.12g\n",(_cbwrap.find(",CSW,")!=std::string::npos)?0.0:(double)(model_.CSW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CSLW=%.12g\n",(_cbwrap.find(",CSLW,")!=std::string::npos)?0.0:(double)(model_.CSLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STCSO=%.12g\n",(_cbwrap.find(",STCSO,")!=std::string::npos)?0.0:(double)(model_.STCSO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"XCORO=%.12g\n",(_cbwrap.find(",XCORO,")!=std::string::npos)?0.0:(double)(model_.XCORO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"XCORL=%.12g\n",(_cbwrap.find(",XCORL,")!=std::string::npos)?0.0:(double)(model_.XCORL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"XCORW=%.12g\n",(_cbwrap.find(",XCORW,")!=std::string::npos)?0.0:(double)(model_.XCORW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"XCORLW=%.12g\n",(_cbwrap.find(",XCORLW,")!=std::string::npos)?0.0:(double)(model_.XCORLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STXCORO=%.12g\n",(_cbwrap.find(",STXCORO,")!=std::string::npos)?0.0:(double)(model_.STXCORO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FETAO=%.12g\n",(_cbwrap.find(",FETAO,")!=std::string::npos)?0.0:(double)(model_.FETAO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RSW1=%.12g\n",(_cbwrap.find(",RSW1,")!=std::string::npos)?0.0:(double)(model_.RSW1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RSW2=%.12g\n",(_cbwrap.find(",RSW2,")!=std::string::npos)?0.0:(double)(model_.RSW2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STRSO=%.12g\n",(_cbwrap.find(",STRSO,")!=std::string::npos)?0.0:(double)(model_.STRSO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RSBO=%.12g\n",(_cbwrap.find(",RSBO,")!=std::string::npos)?0.0:(double)(model_.RSBO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RSGO=%.12g\n",(_cbwrap.find(",RSGO,")!=std::string::npos)?0.0:(double)(model_.RSGO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THESATO=%.12g\n",(_cbwrap.find(",THESATO,")!=std::string::npos)?0.0:(double)(model_.THESATO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THESATL=%.12g\n",(_cbwrap.find(",THESATL,")!=std::string::npos)?0.0:(double)(model_.THESATL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THESATLEXP=%.12g\n",(_cbwrap.find(",THESATLEXP,")!=std::string::npos)?0.0:(double)(model_.THESATLEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THESATW=%.12g\n",(_cbwrap.find(",THESATW,")!=std::string::npos)?0.0:(double)(model_.THESATW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THESATLW=%.12g\n",(_cbwrap.find(",THESATLW,")!=std::string::npos)?0.0:(double)(model_.THESATLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STTHESATO=%.12g\n",(_cbwrap.find(",STTHESATO,")!=std::string::npos)?0.0:(double)(model_.STTHESATO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STTHESATL=%.12g\n",(_cbwrap.find(",STTHESATL,")!=std::string::npos)?0.0:(double)(model_.STTHESATL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STTHESATW=%.12g\n",(_cbwrap.find(",STTHESATW,")!=std::string::npos)?0.0:(double)(model_.STTHESATW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STTHESATLW=%.12g\n",(_cbwrap.find(",STTHESATLW,")!=std::string::npos)?0.0:(double)(model_.STTHESATLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THESATBO=%.12g\n",(_cbwrap.find(",THESATBO,")!=std::string::npos)?0.0:(double)(model_.THESATBO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"THESATGO=%.12g\n",(_cbwrap.find(",THESATGO,")!=std::string::npos)?0.0:(double)(model_.THESATGO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"AXO=%.12g\n",(_cbwrap.find(",AXO,")!=std::string::npos)?0.0:(double)(model_.AXO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"AXL=%.12g\n",(_cbwrap.find(",AXL,")!=std::string::npos)?0.0:(double)(model_.AXL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALPL=%.12g\n",(_cbwrap.find(",ALPL,")!=std::string::npos)?0.0:(double)(model_.ALPL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALPLEXP=%.12g\n",(_cbwrap.find(",ALPLEXP,")!=std::string::npos)?0.0:(double)(model_.ALPLEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALPW=%.12g\n",(_cbwrap.find(",ALPW,")!=std::string::npos)?0.0:(double)(model_.ALPW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALP1L1=%.12g\n",(_cbwrap.find(",ALP1L1,")!=std::string::npos)?0.0:(double)(model_.ALP1L1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALP1LEXP=%.12g\n",(_cbwrap.find(",ALP1LEXP,")!=std::string::npos)?0.0:(double)(model_.ALP1LEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALP1L2=%.12g\n",(_cbwrap.find(",ALP1L2,")!=std::string::npos)?0.0:(double)(model_.ALP1L2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALP1W=%.12g\n",(_cbwrap.find(",ALP1W,")!=std::string::npos)?0.0:(double)(model_.ALP1W)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALP2L1=%.12g\n",(_cbwrap.find(",ALP2L1,")!=std::string::npos)?0.0:(double)(model_.ALP2L1)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALP2LEXP=%.12g\n",(_cbwrap.find(",ALP2LEXP,")!=std::string::npos)?0.0:(double)(model_.ALP2LEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALP2L2=%.12g\n",(_cbwrap.find(",ALP2L2,")!=std::string::npos)?0.0:(double)(model_.ALP2L2)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALP2W=%.12g\n",(_cbwrap.find(",ALP2W,")!=std::string::npos)?0.0:(double)(model_.ALP2W)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VPO=%.12g\n",(_cbwrap.find(",VPO,")!=std::string::npos)?0.0:(double)(model_.VPO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A1O=%.12g\n",(_cbwrap.find(",A1O,")!=std::string::npos)?0.0:(double)(model_.A1O)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A1L=%.12g\n",(_cbwrap.find(",A1L,")!=std::string::npos)?0.0:(double)(model_.A1L)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A1W=%.12g\n",(_cbwrap.find(",A1W,")!=std::string::npos)?0.0:(double)(model_.A1W)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A2O=%.12g\n",(_cbwrap.find(",A2O,")!=std::string::npos)?0.0:(double)(model_.A2O)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STA2O=%.12g\n",(_cbwrap.find(",STA2O,")!=std::string::npos)?0.0:(double)(model_.STA2O)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A3O=%.12g\n",(_cbwrap.find(",A3O,")!=std::string::npos)?0.0:(double)(model_.A3O)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A3L=%.12g\n",(_cbwrap.find(",A3L,")!=std::string::npos)?0.0:(double)(model_.A3L)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A3W=%.12g\n",(_cbwrap.find(",A3W,")!=std::string::npos)?0.0:(double)(model_.A3W)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A4O=%.12g\n",(_cbwrap.find(",A4O,")!=std::string::npos)?0.0:(double)(model_.A4O)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A4L=%.12g\n",(_cbwrap.find(",A4L,")!=std::string::npos)?0.0:(double)(model_.A4L)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"A4W=%.12g\n",(_cbwrap.find(",A4W,")!=std::string::npos)?0.0:(double)(model_.A4W)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GCOO=%.12g\n",(_cbwrap.find(",GCOO,")!=std::string::npos)?0.0:(double)(model_.GCOO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IGINVLW=%.12g\n",(_cbwrap.find(",IGINVLW,")!=std::string::npos)?0.0:(double)(model_.IGINVLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IGOVW=%.12g\n",(_cbwrap.find(",IGOVW,")!=std::string::npos)?0.0:(double)(model_.IGOVW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IGOVDW=%.12g\n",(_cbwrap.find(",IGOVDW,")!=std::string::npos)?0.0:(double)(model_.IGOVDW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STIGO=%.12g\n",(_cbwrap.find(",STIGO,")!=std::string::npos)?0.0:(double)(model_.STIGO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GC2O=%.12g\n",(_cbwrap.find(",GC2O,")!=std::string::npos)?0.0:(double)(model_.GC2O)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"GC3O=%.12g\n",(_cbwrap.find(",GC3O,")!=std::string::npos)?0.0:(double)(model_.GC3O)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CHIBO=%.12g\n",(_cbwrap.find(",CHIBO,")!=std::string::npos)?0.0:(double)(model_.CHIBO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"AGIDLW=%.12g\n",(_cbwrap.find(",AGIDLW,")!=std::string::npos)?0.0:(double)(model_.AGIDLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"AGIDLDW=%.12g\n",(_cbwrap.find(",AGIDLDW,")!=std::string::npos)?0.0:(double)(model_.AGIDLDW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"BGIDLO=%.12g\n",(_cbwrap.find(",BGIDLO,")!=std::string::npos)?0.0:(double)(model_.BGIDLO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"BGIDLDO=%.12g\n",(_cbwrap.find(",BGIDLDO,")!=std::string::npos)?0.0:(double)(model_.BGIDLDO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBGIDLO=%.12g\n",(_cbwrap.find(",STBGIDLO,")!=std::string::npos)?0.0:(double)(model_.STBGIDLO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBGIDLDO=%.12g\n",(_cbwrap.find(",STBGIDLDO,")!=std::string::npos)?0.0:(double)(model_.STBGIDLDO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CGIDLO=%.12g\n",(_cbwrap.find(",CGIDLO,")!=std::string::npos)?0.0:(double)(model_.CGIDLO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CGIDLDO=%.12g\n",(_cbwrap.find(",CGIDLDO,")!=std::string::npos)?0.0:(double)(model_.CGIDLDO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CGBOVL=%.12g\n",(_cbwrap.find(",CGBOVL,")!=std::string::npos)?0.0:(double)(model_.CGBOVL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFRW=%.12g\n",(_cbwrap.find(",CFRW,")!=std::string::npos)?0.0:(double)(model_.CFRW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFRDW=%.12g\n",(_cbwrap.find(",CFRDW,")!=std::string::npos)?0.0:(double)(model_.CFRDW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FNTO=%.12g\n",(_cbwrap.find(",FNTO,")!=std::string::npos)?0.0:(double)(model_.FNTO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FNTEXCL=%.12g\n",(_cbwrap.find(",FNTEXCL,")!=std::string::npos)?0.0:(double)(model_.FNTEXCL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFALW=%.12g\n",(_cbwrap.find(",NFALW,")!=std::string::npos)?0.0:(double)(model_.NFALW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFBLW=%.12g\n",(_cbwrap.find(",NFBLW,")!=std::string::npos)?0.0:(double)(model_.NFBLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFCLW=%.12g\n",(_cbwrap.find(",NFCLW,")!=std::string::npos)?0.0:(double)(model_.NFCLW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"EFO=%.12g\n",(_cbwrap.find(",EFO,")!=std::string::npos)?0.0:(double)(model_.EFO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LINTNOI=%.12g\n",(_cbwrap.find(",LINTNOI,")!=std::string::npos)?0.0:(double)(model_.LINTNOI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"ALPNOI=%.12g\n",(_cbwrap.find(",ALPNOI,")!=std::string::npos)?0.0:(double)(model_.ALPNOI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WEDGE=%.12g\n",(_cbwrap.find(",WEDGE,")!=std::string::npos)?0.0:(double)(model_.WEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WEDGEW=%.12g\n",(_cbwrap.find(",WEDGEW,")!=std::string::npos)?0.0:(double)(model_.WEDGEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VFBEDGEO=%.12g\n",(_cbwrap.find(",VFBEDGEO,")!=std::string::npos)?0.0:(double)(model_.VFBEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STVFBEDGEO=%.12g\n",(_cbwrap.find(",STVFBEDGEO,")!=std::string::npos)?0.0:(double)(model_.STVFBEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STVFBEDGEL=%.12g\n",(_cbwrap.find(",STVFBEDGEL,")!=std::string::npos)?0.0:(double)(model_.STVFBEDGEL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STVFBEDGEW=%.12g\n",(_cbwrap.find(",STVFBEDGEW,")!=std::string::npos)?0.0:(double)(model_.STVFBEDGEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STVFBEDGELW=%.12g\n",(_cbwrap.find(",STVFBEDGELW,")!=std::string::npos)?0.0:(double)(model_.STVFBEDGELW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIBEDGEO=%.12g\n",(_cbwrap.find(",DPHIBEDGEO,")!=std::string::npos)?0.0:(double)(model_.DPHIBEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIBEDGEL=%.12g\n",(_cbwrap.find(",DPHIBEDGEL,")!=std::string::npos)?0.0:(double)(model_.DPHIBEDGEL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIBEDGELEXP=%.12g\n",(_cbwrap.find(",DPHIBEDGELEXP,")!=std::string::npos)?0.0:(double)(model_.DPHIBEDGELEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIBEDGEW=%.12g\n",(_cbwrap.find(",DPHIBEDGEW,")!=std::string::npos)?0.0:(double)(model_.DPHIBEDGEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DPHIBEDGELW=%.12g\n",(_cbwrap.find(",DPHIBEDGELW,")!=std::string::npos)?0.0:(double)(model_.DPHIBEDGELW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NSUBEDGEO=%.12g\n",(_cbwrap.find(",NSUBEDGEO,")!=std::string::npos)?0.0:(double)(model_.NSUBEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NSUBEDGEL=%.12g\n",(_cbwrap.find(",NSUBEDGEL,")!=std::string::npos)?0.0:(double)(model_.NSUBEDGEL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NSUBEDGEW=%.12g\n",(_cbwrap.find(",NSUBEDGEW,")!=std::string::npos)?0.0:(double)(model_.NSUBEDGEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NSUBEDGELW=%.12g\n",(_cbwrap.find(",NSUBEDGELW,")!=std::string::npos)?0.0:(double)(model_.NSUBEDGELW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTEDGEO=%.12g\n",(_cbwrap.find(",CTEDGEO,")!=std::string::npos)?0.0:(double)(model_.CTEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTEDGEL=%.12g\n",(_cbwrap.find(",CTEDGEL,")!=std::string::npos)?0.0:(double)(model_.CTEDGEL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTEDGELEXP=%.12g\n",(_cbwrap.find(",CTEDGELEXP,")!=std::string::npos)?0.0:(double)(model_.CTEDGELEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FBETEDGE=%.12g\n",(_cbwrap.find(",FBETEDGE,")!=std::string::npos)?0.0:(double)(model_.FBETEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LPEDGE=%.12g\n",(_cbwrap.find(",LPEDGE,")!=std::string::npos)?0.0:(double)(model_.LPEDGE)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"BETEDGEW=%.12g\n",(_cbwrap.find(",BETEDGEW,")!=std::string::npos)?0.0:(double)(model_.BETEDGEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBETEDGEO=%.12g\n",(_cbwrap.find(",STBETEDGEO,")!=std::string::npos)?0.0:(double)(model_.STBETEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBETEDGEL=%.12g\n",(_cbwrap.find(",STBETEDGEL,")!=std::string::npos)?0.0:(double)(model_.STBETEDGEL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBETEDGEW=%.12g\n",(_cbwrap.find(",STBETEDGEW,")!=std::string::npos)?0.0:(double)(model_.STBETEDGEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STBETEDGELW=%.12g\n",(_cbwrap.find(",STBETEDGELW,")!=std::string::npos)?0.0:(double)(model_.STBETEDGELW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEEDGEL=%.12g\n",(_cbwrap.find(",PSCEEDGEL,")!=std::string::npos)?0.0:(double)(model_.PSCEEDGEL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEEDGELEXP=%.12g\n",(_cbwrap.find(",PSCEEDGELEXP,")!=std::string::npos)?0.0:(double)(model_.PSCEEDGELEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEEDGEW=%.12g\n",(_cbwrap.find(",PSCEEDGEW,")!=std::string::npos)?0.0:(double)(model_.PSCEEDGEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEBEDGEO=%.12g\n",(_cbwrap.find(",PSCEBEDGEO,")!=std::string::npos)?0.0:(double)(model_.PSCEBEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSCEDEDGEO=%.12g\n",(_cbwrap.find(",PSCEDEDGEO,")!=std::string::npos)?0.0:(double)(model_.PSCEDEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFEDGEL=%.12g\n",(_cbwrap.find(",CFEDGEL,")!=std::string::npos)?0.0:(double)(model_.CFEDGEL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFEDGELEXP=%.12g\n",(_cbwrap.find(",CFEDGELEXP,")!=std::string::npos)?0.0:(double)(model_.CFEDGELEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFEDGEW=%.12g\n",(_cbwrap.find(",CFEDGEW,")!=std::string::npos)?0.0:(double)(model_.CFEDGEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFDEDGEO=%.12g\n",(_cbwrap.find(",CFDEDGEO,")!=std::string::npos)?0.0:(double)(model_.CFDEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CFBEDGEO=%.12g\n",(_cbwrap.find(",CFBEDGEO,")!=std::string::npos)?0.0:(double)(model_.CFBEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FNTEDGEO=%.12g\n",(_cbwrap.find(",FNTEDGEO,")!=std::string::npos)?0.0:(double)(model_.FNTEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFAEDGELW=%.12g\n",(_cbwrap.find(",NFAEDGELW,")!=std::string::npos)?0.0:(double)(model_.NFAEDGELW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFBEDGELW=%.12g\n",(_cbwrap.find(",NFBEDGELW,")!=std::string::npos)?0.0:(double)(model_.NFBEDGELW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"NFCEDGELW=%.12g\n",(_cbwrap.find(",NFCEDGELW,")!=std::string::npos)?0.0:(double)(model_.NFCEDGELW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"EFEDGEO=%.12g\n",(_cbwrap.find(",EFEDGEO,")!=std::string::npos)?0.0:(double)(model_.EFEDGEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"KVTHOWEO=%.12g\n",(_cbwrap.find(",KVTHOWEO,")!=std::string::npos)?0.0:(double)(model_.KVTHOWEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"KVTHOWEL=%.12g\n",(_cbwrap.find(",KVTHOWEL,")!=std::string::npos)?0.0:(double)(model_.KVTHOWEL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"KVTHOWEW=%.12g\n",(_cbwrap.find(",KVTHOWEW,")!=std::string::npos)?0.0:(double)(model_.KVTHOWEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"KVTHOWELW=%.12g\n",(_cbwrap.find(",KVTHOWELW,")!=std::string::npos)?0.0:(double)(model_.KVTHOWELW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"KUOWEO=%.12g\n",(_cbwrap.find(",KUOWEO,")!=std::string::npos)?0.0:(double)(model_.KUOWEO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"KUOWEL=%.12g\n",(_cbwrap.find(",KUOWEL,")!=std::string::npos)?0.0:(double)(model_.KUOWEL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"KUOWEW=%.12g\n",(_cbwrap.find(",KUOWEW,")!=std::string::npos)?0.0:(double)(model_.KUOWEW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"KUOWELW=%.12g\n",(_cbwrap.find(",KUOWELW,")!=std::string::npos)?0.0:(double)(model_.KUOWELW)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RGO=%.12g\n",(_cbwrap.find(",RGO,")!=std::string::npos)?0.0:(double)(model_.RGO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RINT=%.12g\n",(_cbwrap.find(",RINT,")!=std::string::npos)?0.0:(double)(model_.RINT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RVPOLY=%.12g\n",(_cbwrap.find(",RVPOLY,")!=std::string::npos)?0.0:(double)(model_.RVPOLY)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RSHG=%.12g\n",(_cbwrap.find(",RSHG,")!=std::string::npos)?0.0:(double)(model_.RSHG)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DLSIL=%.12g\n",(_cbwrap.find(",DLSIL,")!=std::string::npos)?0.0:(double)(model_.DLSIL)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RSH=%.12g\n",(_cbwrap.find(",RSH,")!=std::string::npos)?0.0:(double)(model_.RSH)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RSHD=%.12g\n",(_cbwrap.find(",RSHD,")!=std::string::npos)?0.0:(double)(model_.RSHD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RBULKO=%.12g\n",(_cbwrap.find(",RBULKO,")!=std::string::npos)?0.0:(double)(model_.RBULKO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RWELLO=%.12g\n",(_cbwrap.find(",RWELLO,")!=std::string::npos)?0.0:(double)(model_.RWELLO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RJUNSO=%.12g\n",(_cbwrap.find(",RJUNSO,")!=std::string::npos)?0.0:(double)(model_.RJUNSO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"RJUNDO=%.12g\n",(_cbwrap.find(",RJUNDO,")!=std::string::npos)?0.0:(double)(model_.RJUNDO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SAREF=%.12g\n",(_cbwrap.find(",SAREF,")!=std::string::npos)?0.0:(double)(model_.SAREF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SBREF=%.12g\n",(_cbwrap.find(",SBREF,")!=std::string::npos)?0.0:(double)(model_.SBREF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WLOD=%.12g\n",(_cbwrap.find(",WLOD,")!=std::string::npos)?0.0:(double)(model_.WLOD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"KUO=%.12g\n",(_cbwrap.find(",KUO,")!=std::string::npos)?0.0:(double)(model_.KUO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"KVSAT=%.12g\n",(_cbwrap.find(",KVSAT,")!=std::string::npos)?0.0:(double)(model_.KVSAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"TKUO=%.12g\n",(_cbwrap.find(",TKUO,")!=std::string::npos)?0.0:(double)(model_.TKUO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LKUO=%.12g\n",(_cbwrap.find(",LKUO,")!=std::string::npos)?0.0:(double)(model_.LKUO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WKUO=%.12g\n",(_cbwrap.find(",WKUO,")!=std::string::npos)?0.0:(double)(model_.WKUO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PKUO=%.12g\n",(_cbwrap.find(",PKUO,")!=std::string::npos)?0.0:(double)(model_.PKUO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LLODKUO=%.12g\n",(_cbwrap.find(",LLODKUO,")!=std::string::npos)?0.0:(double)(model_.LLODKUO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WLODKUO=%.12g\n",(_cbwrap.find(",WLODKUO,")!=std::string::npos)?0.0:(double)(model_.WLODKUO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"KVTHO=%.12g\n",(_cbwrap.find(",KVTHO,")!=std::string::npos)?0.0:(double)(model_.KVTHO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LKVTHO=%.12g\n",(_cbwrap.find(",LKVTHO,")!=std::string::npos)?0.0:(double)(model_.LKVTHO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WKVTHO=%.12g\n",(_cbwrap.find(",WKVTHO,")!=std::string::npos)?0.0:(double)(model_.WKVTHO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PKVTHO=%.12g\n",(_cbwrap.find(",PKVTHO,")!=std::string::npos)?0.0:(double)(model_.PKVTHO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LLODVTH=%.12g\n",(_cbwrap.find(",LLODVTH,")!=std::string::npos)?0.0:(double)(model_.LLODVTH)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WLODVTH=%.12g\n",(_cbwrap.find(",WLODVTH,")!=std::string::npos)?0.0:(double)(model_.WLODVTH)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STETAO=%.12g\n",(_cbwrap.find(",STETAO,")!=std::string::npos)?0.0:(double)(model_.STETAO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"LODETAO=%.12g\n",(_cbwrap.find(",LODETAO,")!=std::string::npos)?0.0:(double)(model_.LODETAO)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SCREF=%.12g\n",(_cbwrap.find(",SCREF,")!=std::string::npos)?0.0:(double)(model_.SCREF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WEB=%.12g\n",(_cbwrap.find(",WEB,")!=std::string::npos)?0.0:(double)(model_.WEB)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"WEC=%.12g\n",(_cbwrap.find(",WEC,")!=std::string::npos)?0.0:(double)(model_.WEC)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IMAX=%.12g\n",(_cbwrap.find(",IMAX,")!=std::string::npos)?0.0:(double)(model_.IMAX)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"TRJ=%.12g\n",(_cbwrap.find(",TRJ,")!=std::string::npos)?0.0:(double)(model_.TRJ)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FREV=%.12g\n",(_cbwrap.find(",FREV,")!=std::string::npos)?0.0:(double)(model_.FREV)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CJORBOT=%.12g\n",(_cbwrap.find(",CJORBOT,")!=std::string::npos)?0.0:(double)(model_.CJORBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CJORSTI=%.12g\n",(_cbwrap.find(",CJORSTI,")!=std::string::npos)?0.0:(double)(model_.CJORSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CJORGAT=%.12g\n",(_cbwrap.find(",CJORGAT,")!=std::string::npos)?0.0:(double)(model_.CJORGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBIRBOT=%.12g\n",(_cbwrap.find(",VBIRBOT,")!=std::string::npos)?0.0:(double)(model_.VBIRBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBIRSTI=%.12g\n",(_cbwrap.find(",VBIRSTI,")!=std::string::npos)?0.0:(double)(model_.VBIRSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBIRGAT=%.12g\n",(_cbwrap.find(",VBIRGAT,")!=std::string::npos)?0.0:(double)(model_.VBIRGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PBOT=%.12g\n",(_cbwrap.find(",PBOT,")!=std::string::npos)?0.0:(double)(model_.PBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSTI=%.12g\n",(_cbwrap.find(",PSTI,")!=std::string::npos)?0.0:(double)(model_.PSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PGAT=%.12g\n",(_cbwrap.find(",PGAT,")!=std::string::npos)?0.0:(double)(model_.PGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PHIGBOT=%.12g\n",(_cbwrap.find(",PHIGBOT,")!=std::string::npos)?0.0:(double)(model_.PHIGBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PHIGSTI=%.12g\n",(_cbwrap.find(",PHIGSTI,")!=std::string::npos)?0.0:(double)(model_.PHIGSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PHIGGAT=%.12g\n",(_cbwrap.find(",PHIGGAT,")!=std::string::npos)?0.0:(double)(model_.PHIGGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IDSATRBOT=%.12g\n",(_cbwrap.find(",IDSATRBOT,")!=std::string::npos)?0.0:(double)(model_.IDSATRBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IDSATRSTI=%.12g\n",(_cbwrap.find(",IDSATRSTI,")!=std::string::npos)?0.0:(double)(model_.IDSATRSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IDSATRGAT=%.12g\n",(_cbwrap.find(",IDSATRGAT,")!=std::string::npos)?0.0:(double)(model_.IDSATRGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CSRHBOT=%.12g\n",(_cbwrap.find(",CSRHBOT,")!=std::string::npos)?0.0:(double)(model_.CSRHBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CSRHSTI=%.12g\n",(_cbwrap.find(",CSRHSTI,")!=std::string::npos)?0.0:(double)(model_.CSRHSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CSRHGAT=%.12g\n",(_cbwrap.find(",CSRHGAT,")!=std::string::npos)?0.0:(double)(model_.CSRHGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"XJUNSTI=%.12g\n",(_cbwrap.find(",XJUNSTI,")!=std::string::npos)?0.0:(double)(model_.XJUNSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"XJUNGAT=%.12g\n",(_cbwrap.find(",XJUNGAT,")!=std::string::npos)?0.0:(double)(model_.XJUNGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTATBOT=%.12g\n",(_cbwrap.find(",CTATBOT,")!=std::string::npos)?0.0:(double)(model_.CTATBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTATSTI=%.12g\n",(_cbwrap.find(",CTATSTI,")!=std::string::npos)?0.0:(double)(model_.CTATSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTATGAT=%.12g\n",(_cbwrap.find(",CTATGAT,")!=std::string::npos)?0.0:(double)(model_.CTATGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"MEFFTATBOT=%.12g\n",(_cbwrap.find(",MEFFTATBOT,")!=std::string::npos)?0.0:(double)(model_.MEFFTATBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"MEFFTATSTI=%.12g\n",(_cbwrap.find(",MEFFTATSTI,")!=std::string::npos)?0.0:(double)(model_.MEFFTATSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"MEFFTATGAT=%.12g\n",(_cbwrap.find(",MEFFTATGAT,")!=std::string::npos)?0.0:(double)(model_.MEFFTATGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CBBTBOT=%.12g\n",(_cbwrap.find(",CBBTBOT,")!=std::string::npos)?0.0:(double)(model_.CBBTBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CBBTSTI=%.12g\n",(_cbwrap.find(",CBBTSTI,")!=std::string::npos)?0.0:(double)(model_.CBBTSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CBBTGAT=%.12g\n",(_cbwrap.find(",CBBTGAT,")!=std::string::npos)?0.0:(double)(model_.CBBTGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FBBTRBOT=%.12g\n",(_cbwrap.find(",FBBTRBOT,")!=std::string::npos)?0.0:(double)(model_.FBBTRBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FBBTRSTI=%.12g\n",(_cbwrap.find(",FBBTRSTI,")!=std::string::npos)?0.0:(double)(model_.FBBTRSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FBBTRGAT=%.12g\n",(_cbwrap.find(",FBBTRGAT,")!=std::string::npos)?0.0:(double)(model_.FBBTRGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STFBBTBOT=%.12g\n",(_cbwrap.find(",STFBBTBOT,")!=std::string::npos)?0.0:(double)(model_.STFBBTBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STFBBTSTI=%.12g\n",(_cbwrap.find(",STFBBTSTI,")!=std::string::npos)?0.0:(double)(model_.STFBBTSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STFBBTGAT=%.12g\n",(_cbwrap.find(",STFBBTGAT,")!=std::string::npos)?0.0:(double)(model_.STFBBTGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBRBOT=%.12g\n",(_cbwrap.find(",VBRBOT,")!=std::string::npos)?0.0:(double)(model_.VBRBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBRSTI=%.12g\n",(_cbwrap.find(",VBRSTI,")!=std::string::npos)?0.0:(double)(model_.VBRSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBRGAT=%.12g\n",(_cbwrap.find(",VBRGAT,")!=std::string::npos)?0.0:(double)(model_.VBRGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PBRBOT=%.12g\n",(_cbwrap.find(",PBRBOT,")!=std::string::npos)?0.0:(double)(model_.PBRBOT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PBRSTI=%.12g\n",(_cbwrap.find(",PBRSTI,")!=std::string::npos)?0.0:(double)(model_.PBRSTI)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PBRGAT=%.12g\n",(_cbwrap.find(",PBRGAT,")!=std::string::npos)?0.0:(double)(model_.PBRGAT)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CJORBOTD=%.12g\n",(_cbwrap.find(",CJORBOTD,")!=std::string::npos)?0.0:(double)(model_.CJORBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CJORSTID=%.12g\n",(_cbwrap.find(",CJORSTID,")!=std::string::npos)?0.0:(double)(model_.CJORSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CJORGATD=%.12g\n",(_cbwrap.find(",CJORGATD,")!=std::string::npos)?0.0:(double)(model_.CJORGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBIRBOTD=%.12g\n",(_cbwrap.find(",VBIRBOTD,")!=std::string::npos)?0.0:(double)(model_.VBIRBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBIRSTID=%.12g\n",(_cbwrap.find(",VBIRSTID,")!=std::string::npos)?0.0:(double)(model_.VBIRSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBIRGATD=%.12g\n",(_cbwrap.find(",VBIRGATD,")!=std::string::npos)?0.0:(double)(model_.VBIRGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PBOTD=%.12g\n",(_cbwrap.find(",PBOTD,")!=std::string::npos)?0.0:(double)(model_.PBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PSTID=%.12g\n",(_cbwrap.find(",PSTID,")!=std::string::npos)?0.0:(double)(model_.PSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PGATD=%.12g\n",(_cbwrap.find(",PGATD,")!=std::string::npos)?0.0:(double)(model_.PGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PHIGBOTD=%.12g\n",(_cbwrap.find(",PHIGBOTD,")!=std::string::npos)?0.0:(double)(model_.PHIGBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PHIGSTID=%.12g\n",(_cbwrap.find(",PHIGSTID,")!=std::string::npos)?0.0:(double)(model_.PHIGSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PHIGGATD=%.12g\n",(_cbwrap.find(",PHIGGATD,")!=std::string::npos)?0.0:(double)(model_.PHIGGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IDSATRBOTD=%.12g\n",(_cbwrap.find(",IDSATRBOTD,")!=std::string::npos)?0.0:(double)(model_.IDSATRBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IDSATRSTID=%.12g\n",(_cbwrap.find(",IDSATRSTID,")!=std::string::npos)?0.0:(double)(model_.IDSATRSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"IDSATRGATD=%.12g\n",(_cbwrap.find(",IDSATRGATD,")!=std::string::npos)?0.0:(double)(model_.IDSATRGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CSRHBOTD=%.12g\n",(_cbwrap.find(",CSRHBOTD,")!=std::string::npos)?0.0:(double)(model_.CSRHBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CSRHSTID=%.12g\n",(_cbwrap.find(",CSRHSTID,")!=std::string::npos)?0.0:(double)(model_.CSRHSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CSRHGATD=%.12g\n",(_cbwrap.find(",CSRHGATD,")!=std::string::npos)?0.0:(double)(model_.CSRHGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"XJUNSTID=%.12g\n",(_cbwrap.find(",XJUNSTID,")!=std::string::npos)?0.0:(double)(model_.XJUNSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"XJUNGATD=%.12g\n",(_cbwrap.find(",XJUNGATD,")!=std::string::npos)?0.0:(double)(model_.XJUNGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTATBOTD=%.12g\n",(_cbwrap.find(",CTATBOTD,")!=std::string::npos)?0.0:(double)(model_.CTATBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTATSTID=%.12g\n",(_cbwrap.find(",CTATSTID,")!=std::string::npos)?0.0:(double)(model_.CTATSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CTATGATD=%.12g\n",(_cbwrap.find(",CTATGATD,")!=std::string::npos)?0.0:(double)(model_.CTATGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"MEFFTATBOTD=%.12g\n",(_cbwrap.find(",MEFFTATBOTD,")!=std::string::npos)?0.0:(double)(model_.MEFFTATBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"MEFFTATSTID=%.12g\n",(_cbwrap.find(",MEFFTATSTID,")!=std::string::npos)?0.0:(double)(model_.MEFFTATSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"MEFFTATGATD=%.12g\n",(_cbwrap.find(",MEFFTATGATD,")!=std::string::npos)?0.0:(double)(model_.MEFFTATGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CBBTBOTD=%.12g\n",(_cbwrap.find(",CBBTBOTD,")!=std::string::npos)?0.0:(double)(model_.CBBTBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CBBTSTID=%.12g\n",(_cbwrap.find(",CBBTSTID,")!=std::string::npos)?0.0:(double)(model_.CBBTSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"CBBTGATD=%.12g\n",(_cbwrap.find(",CBBTGATD,")!=std::string::npos)?0.0:(double)(model_.CBBTGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FBBTRBOTD=%.12g\n",(_cbwrap.find(",FBBTRBOTD,")!=std::string::npos)?0.0:(double)(model_.FBBTRBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FBBTRSTID=%.12g\n",(_cbwrap.find(",FBBTRSTID,")!=std::string::npos)?0.0:(double)(model_.FBBTRSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FBBTRGATD=%.12g\n",(_cbwrap.find(",FBBTRGATD,")!=std::string::npos)?0.0:(double)(model_.FBBTRGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STFBBTBOTD=%.12g\n",(_cbwrap.find(",STFBBTBOTD,")!=std::string::npos)?0.0:(double)(model_.STFBBTBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STFBBTSTID=%.12g\n",(_cbwrap.find(",STFBBTSTID,")!=std::string::npos)?0.0:(double)(model_.STFBBTSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"STFBBTGATD=%.12g\n",(_cbwrap.find(",STFBBTGATD,")!=std::string::npos)?0.0:(double)(model_.STFBBTGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBRBOTD=%.12g\n",(_cbwrap.find(",VBRBOTD,")!=std::string::npos)?0.0:(double)(model_.VBRBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBRSTID=%.12g\n",(_cbwrap.find(",VBRSTID,")!=std::string::npos)?0.0:(double)(model_.VBRSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VBRGATD=%.12g\n",(_cbwrap.find(",VBRGATD,")!=std::string::npos)?0.0:(double)(model_.VBRGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PBRBOTD=%.12g\n",(_cbwrap.find(",PBRBOTD,")!=std::string::npos)?0.0:(double)(model_.PBRBOTD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PBRSTID=%.12g\n",(_cbwrap.find(",PBRSTID,")!=std::string::npos)?0.0:(double)(model_.PBRSTID)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"PBRGATD=%.12g\n",(_cbwrap.find(",PBRGATD,")!=std::string::npos)?0.0:(double)(model_.PBRGATD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"SWJUNEXP=%.12g\n",(_cbwrap.find(",SWJUNEXP,")!=std::string::npos)?0.0:(double)(model_.SWJUNEXP)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VJUNREF=%.12g\n",(_cbwrap.find(",VJUNREF,")!=std::string::npos)?0.0:(double)(model_.VJUNREF)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FJUNQ=%.12g\n",(_cbwrap.find(",FJUNQ,")!=std::string::npos)?0.0:(double)(model_.FJUNQ)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"VJUNREFD=%.12g\n",(_cbwrap.find(",VJUNREFD,")!=std::string::npos)?0.0:(double)(model_.VJUNREFD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"FJUNQD=%.12g\n",(_cbwrap.find(",FJUNQD,")!=std::string::npos)?0.0:(double)(model_.FJUNQD)); _p += _pb;
      snprintf(_pb,sizeof(_pb),"DTA=%.12g\n",(_cbwrap.find(",DTA,")!=std::string::npos)?0.0:(double)(DTA)); _p += _pb;
      std::string _gv;
      if (model_.given("LEVEL")) _gv += "LEVEL,";
      if (model_.given("TYPE")) _gv += "TYPE,";
      if (model_.given("TR")) _gv += "TR,";
      if (model_.given("SWGEO")) _gv += "SWGEO,";
      if (model_.given("SWIGATE")) _gv += "SWIGATE,";
      if (model_.given("SWIMPACT")) _gv += "SWIMPACT,";
      if (model_.given("SWGIDL")) _gv += "SWGIDL,";
      if (model_.given("SWJUNCAP")) _gv += "SWJUNCAP,";
      if (model_.given("SWJUNASYM")) _gv += "SWJUNASYM,";
      if (model_.given("SWNUD")) _gv += "SWNUD,";
      if (model_.given("SWEDGE")) _gv += "SWEDGE,";
      if (model_.given("SWDELVTAC")) _gv += "SWDELVTAC,";
      if (model_.given("SWIGN")) _gv += "SWIGN,";
      if (model_.given("QMC")) _gv += "QMC,";
      if (given("L")) _gv += "L,";
      if (given("W")) _gv += "W,";
      if (given("SA")) _gv += "SA,";
      if (given("SB")) _gv += "SB,";
      if (given("SD")) _gv += "SD,";
      if (given("SCA")) _gv += "SCA,";
      if (given("SCB")) _gv += "SCB,";
      if (given("SCC")) _gv += "SCC,";
      if (given("SC")) _gv += "SC,";
      if (given("NF")) _gv += "NF,";
      if (given("NGCON")) _gv += "NGCON,";
      if (given("XGW")) _gv += "XGW,";
      if (given("NRS")) _gv += "NRS,";
      if (given("NRD")) _gv += "NRD,";
      if (given("JW")) _gv += "JW,";
      if (given("DELVTO")) _gv += "DELVTO,";
      if (given("FACTUO")) _gv += "FACTUO,";
      if (given("DELVTOEDGE")) _gv += "DELVTOEDGE,";
      if (given("FACTUOEDGE")) _gv += "FACTUOEDGE,";
      if (given("ABSOURCE")) _gv += "ABSOURCE,";
      if (given("LSSOURCE")) _gv += "LSSOURCE,";
      if (given("LGSOURCE")) _gv += "LGSOURCE,";
      if (given("ABDRAIN")) _gv += "ABDRAIN,";
      if (given("LSDRAIN")) _gv += "LSDRAIN,";
      if (given("LGDRAIN")) _gv += "LGDRAIN,";
      if (given("AS")) _gv += "AS,";
      if (given("PS")) _gv += "PS,";
      if (given("AD")) _gv += "AD,";
      if (given("PD")) _gv += "PD,";
      if (given("MULT")) _gv += "MULT,";
      if (model_.given("VFB")) _gv += "VFB,";
      if (model_.given("STVFB")) _gv += "STVFB,";
      if (model_.given("TOX")) _gv += "TOX,";
      if (model_.given("EPSROX")) _gv += "EPSROX,";
      if (model_.given("NEFF")) _gv += "NEFF,";
      if (model_.given("FACNEFFAC")) _gv += "FACNEFFAC,";
      if (model_.given("GFACNUD")) _gv += "GFACNUD,";
      if (model_.given("VSBNUD")) _gv += "VSBNUD,";
      if (model_.given("DVSBNUD")) _gv += "DVSBNUD,";
      if (model_.given("VNSUB")) _gv += "VNSUB,";
      if (model_.given("NSLP")) _gv += "NSLP,";
      if (model_.given("DNSUB")) _gv += "DNSUB,";
      if (model_.given("DPHIB")) _gv += "DPHIB,";
      if (model_.given("DELVTAC")) _gv += "DELVTAC,";
      if (model_.given("NP")) _gv += "NP,";
      if (model_.given("CT")) _gv += "CT,";
      if (model_.given("TOXOV")) _gv += "TOXOV,";
      if (model_.given("TOXOVD")) _gv += "TOXOVD,";
      if (model_.given("NOV")) _gv += "NOV,";
      if (model_.given("NOVD")) _gv += "NOVD,";
      if (model_.given("CF")) _gv += "CF,";
      if (model_.given("CFD")) _gv += "CFD,";
      if (model_.given("CFB")) _gv += "CFB,";
      if (model_.given("PSCE")) _gv += "PSCE,";
      if (model_.given("PSCEB")) _gv += "PSCEB,";
      if (model_.given("PSCED")) _gv += "PSCED,";
      if (model_.given("BETN")) _gv += "BETN,";
      if (model_.given("STBET")) _gv += "STBET,";
      if (model_.given("MUE")) _gv += "MUE,";
      if (model_.given("STMUE")) _gv += "STMUE,";
      if (model_.given("THEMU")) _gv += "THEMU,";
      if (model_.given("STTHEMU")) _gv += "STTHEMU,";
      if (model_.given("CS")) _gv += "CS,";
      if (model_.given("STCS")) _gv += "STCS,";
      if (model_.given("XCOR")) _gv += "XCOR,";
      if (model_.given("STXCOR")) _gv += "STXCOR,";
      if (model_.given("FETA")) _gv += "FETA,";
      if (model_.given("RS")) _gv += "RS,";
      if (model_.given("STRS")) _gv += "STRS,";
      if (model_.given("RSB")) _gv += "RSB,";
      if (model_.given("RSG")) _gv += "RSG,";
      if (model_.given("THESAT")) _gv += "THESAT,";
      if (model_.given("STTHESAT")) _gv += "STTHESAT,";
      if (model_.given("THESATB")) _gv += "THESATB,";
      if (model_.given("THESATG")) _gv += "THESATG,";
      if (model_.given("AX")) _gv += "AX,";
      if (model_.given("ALP")) _gv += "ALP,";
      if (model_.given("ALP1")) _gv += "ALP1,";
      if (model_.given("ALP2")) _gv += "ALP2,";
      if (model_.given("VP")) _gv += "VP,";
      if (model_.given("A1")) _gv += "A1,";
      if (model_.given("A2")) _gv += "A2,";
      if (model_.given("STA2")) _gv += "STA2,";
      if (model_.given("A3")) _gv += "A3,";
      if (model_.given("A4")) _gv += "A4,";
      if (model_.given("GCO")) _gv += "GCO,";
      if (model_.given("IGINV")) _gv += "IGINV,";
      if (model_.given("IGOV")) _gv += "IGOV,";
      if (model_.given("IGOVD")) _gv += "IGOVD,";
      if (model_.given("STIG")) _gv += "STIG,";
      if (model_.given("GC2")) _gv += "GC2,";
      if (model_.given("GC3")) _gv += "GC3,";
      if (model_.given("CHIB")) _gv += "CHIB,";
      if (model_.given("AGIDL")) _gv += "AGIDL,";
      if (model_.given("AGIDLD")) _gv += "AGIDLD,";
      if (model_.given("BGIDL")) _gv += "BGIDL,";
      if (model_.given("BGIDLD")) _gv += "BGIDLD,";
      if (model_.given("STBGIDL")) _gv += "STBGIDL,";
      if (model_.given("STBGIDLD")) _gv += "STBGIDLD,";
      if (model_.given("CGIDL")) _gv += "CGIDL,";
      if (model_.given("CGIDLD")) _gv += "CGIDLD,";
      if (model_.given("COX")) _gv += "COX,";
      if (model_.given("CGOV")) _gv += "CGOV,";
      if (model_.given("CGOVD")) _gv += "CGOVD,";
      if (model_.given("CGBOV")) _gv += "CGBOV,";
      if (model_.given("CFR")) _gv += "CFR,";
      if (model_.given("CFRD")) _gv += "CFRD,";
      if (model_.given("FNT")) _gv += "FNT,";
      if (model_.given("FNTEXC")) _gv += "FNTEXC,";
      if (model_.given("NFA")) _gv += "NFA,";
      if (model_.given("NFB")) _gv += "NFB,";
      if (model_.given("NFC")) _gv += "NFC,";
      if (model_.given("EF")) _gv += "EF,";
      if (model_.given("VFBEDGE")) _gv += "VFBEDGE,";
      if (model_.given("STVFBEDGE")) _gv += "STVFBEDGE,";
      if (model_.given("DPHIBEDGE")) _gv += "DPHIBEDGE,";
      if (model_.given("NEFFEDGE")) _gv += "NEFFEDGE,";
      if (model_.given("CTEDGE")) _gv += "CTEDGE,";
      if (model_.given("BETNEDGE")) _gv += "BETNEDGE,";
      if (model_.given("STBETEDGE")) _gv += "STBETEDGE,";
      if (model_.given("PSCEEDGE")) _gv += "PSCEEDGE,";
      if (model_.given("PSCEBEDGE")) _gv += "PSCEBEDGE,";
      if (model_.given("PSCEDEDGE")) _gv += "PSCEDEDGE,";
      if (model_.given("CFEDGE")) _gv += "CFEDGE,";
      if (model_.given("CFDEDGE")) _gv += "CFDEDGE,";
      if (model_.given("CFBEDGE")) _gv += "CFBEDGE,";
      if (model_.given("FNTEDGE")) _gv += "FNTEDGE,";
      if (model_.given("NFAEDGE")) _gv += "NFAEDGE,";
      if (model_.given("NFBEDGE")) _gv += "NFBEDGE,";
      if (model_.given("NFCEDGE")) _gv += "NFCEDGE,";
      if (model_.given("EFEDGE")) _gv += "EFEDGE,";
      if (model_.given("RG")) _gv += "RG,";
      if (model_.given("RSE")) _gv += "RSE,";
      if (model_.given("RDE")) _gv += "RDE,";
      if (model_.given("RBULK")) _gv += "RBULK,";
      if (model_.given("RWELL")) _gv += "RWELL,";
      if (model_.given("RJUNS")) _gv += "RJUNS,";
      if (model_.given("RJUND")) _gv += "RJUND,";
      if (model_.given("POVFB")) _gv += "POVFB,";
      if (model_.given("PLVFB")) _gv += "PLVFB,";
      if (model_.given("PWVFB")) _gv += "PWVFB,";
      if (model_.given("PLWVFB")) _gv += "PLWVFB,";
      if (model_.given("POSTVFB")) _gv += "POSTVFB,";
      if (model_.given("PLSTVFB")) _gv += "PLSTVFB,";
      if (model_.given("PWSTVFB")) _gv += "PWSTVFB,";
      if (model_.given("PLWSTVFB")) _gv += "PLWSTVFB,";
      if (model_.given("POTOX")) _gv += "POTOX,";
      if (model_.given("POEPSROX")) _gv += "POEPSROX,";
      if (model_.given("PONEFF")) _gv += "PONEFF,";
      if (model_.given("PLNEFF")) _gv += "PLNEFF,";
      if (model_.given("PWNEFF")) _gv += "PWNEFF,";
      if (model_.given("PLWNEFF")) _gv += "PLWNEFF,";
      if (model_.given("POFACNEFFAC")) _gv += "POFACNEFFAC,";
      if (model_.given("PLFACNEFFAC")) _gv += "PLFACNEFFAC,";
      if (model_.given("PWFACNEFFAC")) _gv += "PWFACNEFFAC,";
      if (model_.given("PLWFACNEFFAC")) _gv += "PLWFACNEFFAC,";
      if (model_.given("POGFACNUD")) _gv += "POGFACNUD,";
      if (model_.given("PLGFACNUD")) _gv += "PLGFACNUD,";
      if (model_.given("PWGFACNUD")) _gv += "PWGFACNUD,";
      if (model_.given("PLWGFACNUD")) _gv += "PLWGFACNUD,";
      if (model_.given("POVSBNUD")) _gv += "POVSBNUD,";
      if (model_.given("PODVSBNUD")) _gv += "PODVSBNUD,";
      if (model_.given("POVNSUB")) _gv += "POVNSUB,";
      if (model_.given("PONSLP")) _gv += "PONSLP,";
      if (model_.given("PODNSUB")) _gv += "PODNSUB,";
      if (model_.given("PODPHIB")) _gv += "PODPHIB,";
      if (model_.given("PLDPHIB")) _gv += "PLDPHIB,";
      if (model_.given("PWDPHIB")) _gv += "PWDPHIB,";
      if (model_.given("PLWDPHIB")) _gv += "PLWDPHIB,";
      if (model_.given("PODELVTAC")) _gv += "PODELVTAC,";
      if (model_.given("PLDELVTAC")) _gv += "PLDELVTAC,";
      if (model_.given("PWDELVTAC")) _gv += "PWDELVTAC,";
      if (model_.given("PLWDELVTAC")) _gv += "PLWDELVTAC,";
      if (model_.given("PONP")) _gv += "PONP,";
      if (model_.given("PLNP")) _gv += "PLNP,";
      if (model_.given("PWNP")) _gv += "PWNP,";
      if (model_.given("PLWNP")) _gv += "PLWNP,";
      if (model_.given("POCT")) _gv += "POCT,";
      if (model_.given("PLCT")) _gv += "PLCT,";
      if (model_.given("PWCT")) _gv += "PWCT,";
      if (model_.given("PLWCT")) _gv += "PLWCT,";
      if (model_.given("POTOXOV")) _gv += "POTOXOV,";
      if (model_.given("POTOXOVD")) _gv += "POTOXOVD,";
      if (model_.given("PONOV")) _gv += "PONOV,";
      if (model_.given("PLNOV")) _gv += "PLNOV,";
      if (model_.given("PWNOV")) _gv += "PWNOV,";
      if (model_.given("PLWNOV")) _gv += "PLWNOV,";
      if (model_.given("PONOVD")) _gv += "PONOVD,";
      if (model_.given("PLNOVD")) _gv += "PLNOVD,";
      if (model_.given("PWNOVD")) _gv += "PWNOVD,";
      if (model_.given("PLWNOVD")) _gv += "PLWNOVD,";
      if (model_.given("POCF")) _gv += "POCF,";
      if (model_.given("PLCF")) _gv += "PLCF,";
      if (model_.given("PWCF")) _gv += "PWCF,";
      if (model_.given("PLWCF")) _gv += "PLWCF,";
      if (model_.given("POCFD")) _gv += "POCFD,";
      if (model_.given("POCFB")) _gv += "POCFB,";
      if (model_.given("POPSCE")) _gv += "POPSCE,";
      if (model_.given("PLPSCE")) _gv += "PLPSCE,";
      if (model_.given("PWPSCE")) _gv += "PWPSCE,";
      if (model_.given("PLWPSCE")) _gv += "PLWPSCE,";
      if (model_.given("POPSCEB")) _gv += "POPSCEB,";
      if (model_.given("POPSCED")) _gv += "POPSCED,";
      if (model_.given("POBETN")) _gv += "POBETN,";
      if (model_.given("PLBETN")) _gv += "PLBETN,";
      if (model_.given("PWBETN")) _gv += "PWBETN,";
      if (model_.given("PLWBETN")) _gv += "PLWBETN,";
      if (model_.given("POSTBET")) _gv += "POSTBET,";
      if (model_.given("PLSTBET")) _gv += "PLSTBET,";
      if (model_.given("PWSTBET")) _gv += "PWSTBET,";
      if (model_.given("PLWSTBET")) _gv += "PLWSTBET,";
      if (model_.given("POMUE")) _gv += "POMUE,";
      if (model_.given("PLMUE")) _gv += "PLMUE,";
      if (model_.given("PWMUE")) _gv += "PWMUE,";
      if (model_.given("PLWMUE")) _gv += "PLWMUE,";
      if (model_.given("POSTMUE")) _gv += "POSTMUE,";
      if (model_.given("POTHEMU")) _gv += "POTHEMU,";
      if (model_.given("POSTTHEMU")) _gv += "POSTTHEMU,";
      if (model_.given("POCS")) _gv += "POCS,";
      if (model_.given("PLCS")) _gv += "PLCS,";
      if (model_.given("PWCS")) _gv += "PWCS,";
      if (model_.given("PLWCS")) _gv += "PLWCS,";
      if (model_.given("POSTCS")) _gv += "POSTCS,";
      if (model_.given("POXCOR")) _gv += "POXCOR,";
      if (model_.given("PLXCOR")) _gv += "PLXCOR,";
      if (model_.given("PWXCOR")) _gv += "PWXCOR,";
      if (model_.given("PLWXCOR")) _gv += "PLWXCOR,";
      if (model_.given("POSTXCOR")) _gv += "POSTXCOR,";
      if (model_.given("POFETA")) _gv += "POFETA,";
      if (model_.given("PORS")) _gv += "PORS,";
      if (model_.given("PLRS")) _gv += "PLRS,";
      if (model_.given("PWRS")) _gv += "PWRS,";
      if (model_.given("PLWRS")) _gv += "PLWRS,";
      if (model_.given("POSTRS")) _gv += "POSTRS,";
      if (model_.given("PORSB")) _gv += "PORSB,";
      if (model_.given("PORSG")) _gv += "PORSG,";
      if (model_.given("POTHESAT")) _gv += "POTHESAT,";
      if (model_.given("PLTHESAT")) _gv += "PLTHESAT,";
      if (model_.given("PWTHESAT")) _gv += "PWTHESAT,";
      if (model_.given("PLWTHESAT")) _gv += "PLWTHESAT,";
      if (model_.given("POSTTHESAT")) _gv += "POSTTHESAT,";
      if (model_.given("PLSTTHESAT")) _gv += "PLSTTHESAT,";
      if (model_.given("PWSTTHESAT")) _gv += "PWSTTHESAT,";
      if (model_.given("PLWSTTHESAT")) _gv += "PLWSTTHESAT,";
      if (model_.given("POTHESATB")) _gv += "POTHESATB,";
      if (model_.given("PLTHESATB")) _gv += "PLTHESATB,";
      if (model_.given("PWTHESATB")) _gv += "PWTHESATB,";
      if (model_.given("PLWTHESATB")) _gv += "PLWTHESATB,";
      if (model_.given("POTHESATG")) _gv += "POTHESATG,";
      if (model_.given("PLTHESATG")) _gv += "PLTHESATG,";
      if (model_.given("PWTHESATG")) _gv += "PWTHESATG,";
      if (model_.given("PLWTHESATG")) _gv += "PLWTHESATG,";
      if (model_.given("POAX")) _gv += "POAX,";
      if (model_.given("PLAX")) _gv += "PLAX,";
      if (model_.given("PWAX")) _gv += "PWAX,";
      if (model_.given("PLWAX")) _gv += "PLWAX,";
      if (model_.given("POALP")) _gv += "POALP,";
      if (model_.given("PLALP")) _gv += "PLALP,";
      if (model_.given("PWALP")) _gv += "PWALP,";
      if (model_.given("PLWALP")) _gv += "PLWALP,";
      if (model_.given("POALP1")) _gv += "POALP1,";
      if (model_.given("PLALP1")) _gv += "PLALP1,";
      if (model_.given("PWALP1")) _gv += "PWALP1,";
      if (model_.given("PLWALP1")) _gv += "PLWALP1,";
      if (model_.given("POALP2")) _gv += "POALP2,";
      if (model_.given("PLALP2")) _gv += "PLALP2,";
      if (model_.given("PWALP2")) _gv += "PWALP2,";
      if (model_.given("PLWALP2")) _gv += "PLWALP2,";
      if (model_.given("POVP")) _gv += "POVP,";
      if (model_.given("POA1")) _gv += "POA1,";
      if (model_.given("PLA1")) _gv += "PLA1,";
      if (model_.given("PWA1")) _gv += "PWA1,";
      if (model_.given("PLWA1")) _gv += "PLWA1,";
      if (model_.given("POA2")) _gv += "POA2,";
      if (model_.given("POSTA2")) _gv += "POSTA2,";
      if (model_.given("POA3")) _gv += "POA3,";
      if (model_.given("PLA3")) _gv += "PLA3,";
      if (model_.given("PWA3")) _gv += "PWA3,";
      if (model_.given("PLWA3")) _gv += "PLWA3,";
      if (model_.given("POA4")) _gv += "POA4,";
      if (model_.given("PLA4")) _gv += "PLA4,";
      if (model_.given("PWA4")) _gv += "PWA4,";
      if (model_.given("PLWA4")) _gv += "PLWA4,";
      if (model_.given("POGCO")) _gv += "POGCO,";
      if (model_.given("POIGINV")) _gv += "POIGINV,";
      if (model_.given("PLIGINV")) _gv += "PLIGINV,";
      if (model_.given("PWIGINV")) _gv += "PWIGINV,";
      if (model_.given("PLWIGINV")) _gv += "PLWIGINV,";
      if (model_.given("POIGOV")) _gv += "POIGOV,";
      if (model_.given("PLIGOV")) _gv += "PLIGOV,";
      if (model_.given("PWIGOV")) _gv += "PWIGOV,";
      if (model_.given("PLWIGOV")) _gv += "PLWIGOV,";
      if (model_.given("POIGOVD")) _gv += "POIGOVD,";
      if (model_.given("PLIGOVD")) _gv += "PLIGOVD,";
      if (model_.given("PWIGOVD")) _gv += "PWIGOVD,";
      if (model_.given("PLWIGOVD")) _gv += "PLWIGOVD,";
      if (model_.given("POSTIG")) _gv += "POSTIG,";
      if (model_.given("POGC2")) _gv += "POGC2,";
      if (model_.given("POGC3")) _gv += "POGC3,";
      if (model_.given("POCHIB")) _gv += "POCHIB,";
      if (model_.given("POAGIDL")) _gv += "POAGIDL,";
      if (model_.given("PLAGIDL")) _gv += "PLAGIDL,";
      if (model_.given("PWAGIDL")) _gv += "PWAGIDL,";
      if (model_.given("PLWAGIDL")) _gv += "PLWAGIDL,";
      if (model_.given("POAGIDLD")) _gv += "POAGIDLD,";
      if (model_.given("PLAGIDLD")) _gv += "PLAGIDLD,";
      if (model_.given("PWAGIDLD")) _gv += "PWAGIDLD,";
      if (model_.given("PLWAGIDLD")) _gv += "PLWAGIDLD,";
      if (model_.given("POBGIDL")) _gv += "POBGIDL,";
      if (model_.given("POBGIDLD")) _gv += "POBGIDLD,";
      if (model_.given("POSTBGIDL")) _gv += "POSTBGIDL,";
      if (model_.given("POSTBGIDLD")) _gv += "POSTBGIDLD,";
      if (model_.given("POCGIDL")) _gv += "POCGIDL,";
      if (model_.given("POCGIDLD")) _gv += "POCGIDLD,";
      if (model_.given("POCOX")) _gv += "POCOX,";
      if (model_.given("PLCOX")) _gv += "PLCOX,";
      if (model_.given("PWCOX")) _gv += "PWCOX,";
      if (model_.given("PLWCOX")) _gv += "PLWCOX,";
      if (model_.given("POCGOV")) _gv += "POCGOV,";
      if (model_.given("PLCGOV")) _gv += "PLCGOV,";
      if (model_.given("PWCGOV")) _gv += "PWCGOV,";
      if (model_.given("PLWCGOV")) _gv += "PLWCGOV,";
      if (model_.given("POCGOVD")) _gv += "POCGOVD,";
      if (model_.given("PLCGOVD")) _gv += "PLCGOVD,";
      if (model_.given("PWCGOVD")) _gv += "PWCGOVD,";
      if (model_.given("PLWCGOVD")) _gv += "PLWCGOVD,";
      if (model_.given("POCGBOV")) _gv += "POCGBOV,";
      if (model_.given("PLCGBOV")) _gv += "PLCGBOV,";
      if (model_.given("PWCGBOV")) _gv += "PWCGBOV,";
      if (model_.given("PLWCGBOV")) _gv += "PLWCGBOV,";
      if (model_.given("POCFR")) _gv += "POCFR,";
      if (model_.given("PLCFR")) _gv += "PLCFR,";
      if (model_.given("PWCFR")) _gv += "PWCFR,";
      if (model_.given("PLWCFR")) _gv += "PLWCFR,";
      if (model_.given("POCFRD")) _gv += "POCFRD,";
      if (model_.given("PLCFRD")) _gv += "PLCFRD,";
      if (model_.given("PWCFRD")) _gv += "PWCFRD,";
      if (model_.given("PLWCFRD")) _gv += "PLWCFRD,";
      if (model_.given("POFNT")) _gv += "POFNT,";
      if (model_.given("POFNTEXC")) _gv += "POFNTEXC,";
      if (model_.given("PLFNTEXC")) _gv += "PLFNTEXC,";
      if (model_.given("PWFNTEXC")) _gv += "PWFNTEXC,";
      if (model_.given("PLWFNTEXC")) _gv += "PLWFNTEXC,";
      if (model_.given("PONFA")) _gv += "PONFA,";
      if (model_.given("PLNFA")) _gv += "PLNFA,";
      if (model_.given("PWNFA")) _gv += "PWNFA,";
      if (model_.given("PLWNFA")) _gv += "PLWNFA,";
      if (model_.given("PONFB")) _gv += "PONFB,";
      if (model_.given("PLNFB")) _gv += "PLNFB,";
      if (model_.given("PWNFB")) _gv += "PWNFB,";
      if (model_.given("PLWNFB")) _gv += "PLWNFB,";
      if (model_.given("PONFC")) _gv += "PONFC,";
      if (model_.given("PLNFC")) _gv += "PLNFC,";
      if (model_.given("PWNFC")) _gv += "PWNFC,";
      if (model_.given("PLWNFC")) _gv += "PLWNFC,";
      if (model_.given("POEF")) _gv += "POEF,";
      if (model_.given("POVFBEDGE")) _gv += "POVFBEDGE,";
      if (model_.given("POSTVFBEDGE")) _gv += "POSTVFBEDGE,";
      if (model_.given("PLSTVFBEDGE")) _gv += "PLSTVFBEDGE,";
      if (model_.given("PWSTVFBEDGE")) _gv += "PWSTVFBEDGE,";
      if (model_.given("PLWSTVFBEDGE")) _gv += "PLWSTVFBEDGE,";
      if (model_.given("PODPHIBEDGE")) _gv += "PODPHIBEDGE,";
      if (model_.given("PLDPHIBEDGE")) _gv += "PLDPHIBEDGE,";
      if (model_.given("PWDPHIBEDGE")) _gv += "PWDPHIBEDGE,";
      if (model_.given("PLWDPHIBEDGE")) _gv += "PLWDPHIBEDGE,";
      if (model_.given("PONEFFEDGE")) _gv += "PONEFFEDGE,";
      if (model_.given("PLNEFFEDGE")) _gv += "PLNEFFEDGE,";
      if (model_.given("PWNEFFEDGE")) _gv += "PWNEFFEDGE,";
      if (model_.given("PLWNEFFEDGE")) _gv += "PLWNEFFEDGE,";
      if (model_.given("POCTEDGE")) _gv += "POCTEDGE,";
      if (model_.given("PLCTEDGE")) _gv += "PLCTEDGE,";
      if (model_.given("PWCTEDGE")) _gv += "PWCTEDGE,";
      if (model_.given("PLWCTEDGE")) _gv += "PLWCTEDGE,";
      if (model_.given("POBETNEDGE")) _gv += "POBETNEDGE,";
      if (model_.given("PLBETNEDGE")) _gv += "PLBETNEDGE,";
      if (model_.given("PWBETNEDGE")) _gv += "PWBETNEDGE,";
      if (model_.given("PLWBETNEDGE")) _gv += "PLWBETNEDGE,";
      if (model_.given("POSTBETEDGE")) _gv += "POSTBETEDGE,";
      if (model_.given("PLSTBETEDGE")) _gv += "PLSTBETEDGE,";
      if (model_.given("PWSTBETEDGE")) _gv += "PWSTBETEDGE,";
      if (model_.given("PLWSTBETEDGE")) _gv += "PLWSTBETEDGE,";
      if (model_.given("POPSCEEDGE")) _gv += "POPSCEEDGE,";
      if (model_.given("PLPSCEEDGE")) _gv += "PLPSCEEDGE,";
      if (model_.given("PWPSCEEDGE")) _gv += "PWPSCEEDGE,";
      if (model_.given("PLWPSCEEDGE")) _gv += "PLWPSCEEDGE,";
      if (model_.given("POPSCEBEDGE")) _gv += "POPSCEBEDGE,";
      if (model_.given("POPSCEDEDGE")) _gv += "POPSCEDEDGE,";
      if (model_.given("POCFEDGE")) _gv += "POCFEDGE,";
      if (model_.given("PLCFEDGE")) _gv += "PLCFEDGE,";
      if (model_.given("PWCFEDGE")) _gv += "PWCFEDGE,";
      if (model_.given("PLWCFEDGE")) _gv += "PLWCFEDGE,";
      if (model_.given("POCFDEDGE")) _gv += "POCFDEDGE,";
      if (model_.given("POCFBEDGE")) _gv += "POCFBEDGE,";
      if (model_.given("POFNTEDGE")) _gv += "POFNTEDGE,";
      if (model_.given("PONFAEDGE")) _gv += "PONFAEDGE,";
      if (model_.given("PLNFAEDGE")) _gv += "PLNFAEDGE,";
      if (model_.given("PWNFAEDGE")) _gv += "PWNFAEDGE,";
      if (model_.given("PLWNFAEDGE")) _gv += "PLWNFAEDGE,";
      if (model_.given("PONFBEDGE")) _gv += "PONFBEDGE,";
      if (model_.given("PLNFBEDGE")) _gv += "PLNFBEDGE,";
      if (model_.given("PWNFBEDGE")) _gv += "PWNFBEDGE,";
      if (model_.given("PLWNFBEDGE")) _gv += "PLWNFBEDGE,";
      if (model_.given("PONFCEDGE")) _gv += "PONFCEDGE,";
      if (model_.given("PLNFCEDGE")) _gv += "PLNFCEDGE,";
      if (model_.given("PWNFCEDGE")) _gv += "PWNFCEDGE,";
      if (model_.given("PLWNFCEDGE")) _gv += "PLWNFCEDGE,";
      if (model_.given("POEFEDGE")) _gv += "POEFEDGE,";
      if (model_.given("POKVTHOWE")) _gv += "POKVTHOWE,";
      if (model_.given("PLKVTHOWE")) _gv += "PLKVTHOWE,";
      if (model_.given("PWKVTHOWE")) _gv += "PWKVTHOWE,";
      if (model_.given("PLWKVTHOWE")) _gv += "PLWKVTHOWE,";
      if (model_.given("POKUOWE")) _gv += "POKUOWE,";
      if (model_.given("PLKUOWE")) _gv += "PLKUOWE,";
      if (model_.given("PWKUOWE")) _gv += "PWKUOWE,";
      if (model_.given("PLWKUOWE")) _gv += "PLWKUOWE,";
      if (model_.given("LMIN")) _gv += "LMIN,";
      if (model_.given("LMAX")) _gv += "LMAX,";
      if (model_.given("WMIN")) _gv += "WMIN,";
      if (model_.given("WMAX")) _gv += "WMAX,";
      if (model_.given("LVARO")) _gv += "LVARO,";
      if (model_.given("LVARL")) _gv += "LVARL,";
      if (model_.given("LVARW")) _gv += "LVARW,";
      if (model_.given("LAP")) _gv += "LAP,";
      if (model_.given("WVARO")) _gv += "WVARO,";
      if (model_.given("WVARL")) _gv += "WVARL,";
      if (model_.given("WVARW")) _gv += "WVARW,";
      if (model_.given("WOT")) _gv += "WOT,";
      if (model_.given("DLQ")) _gv += "DLQ,";
      if (model_.given("DWQ")) _gv += "DWQ,";
      if (model_.given("VFBO")) _gv += "VFBO,";
      if (model_.given("VFBL")) _gv += "VFBL,";
      if (model_.given("VFBW")) _gv += "VFBW,";
      if (model_.given("VFBLW")) _gv += "VFBLW,";
      if (model_.given("STVFBO")) _gv += "STVFBO,";
      if (model_.given("STVFBL")) _gv += "STVFBL,";
      if (model_.given("STVFBW")) _gv += "STVFBW,";
      if (model_.given("STVFBLW")) _gv += "STVFBLW,";
      if (model_.given("TOXO")) _gv += "TOXO,";
      if (model_.given("EPSROXO")) _gv += "EPSROXO,";
      if (model_.given("NSUBO")) _gv += "NSUBO,";
      if (model_.given("NSUBW")) _gv += "NSUBW,";
      if (model_.given("WSEG")) _gv += "WSEG,";
      if (model_.given("NPCK")) _gv += "NPCK,";
      if (model_.given("NPCKW")) _gv += "NPCKW,";
      if (model_.given("WSEGP")) _gv += "WSEGP,";
      if (model_.given("LPCK")) _gv += "LPCK,";
      if (model_.given("LPCKW")) _gv += "LPCKW,";
      if (model_.given("FOL1")) _gv += "FOL1,";
      if (model_.given("FOL2")) _gv += "FOL2,";
      if (model_.given("FACNEFFACO")) _gv += "FACNEFFACO,";
      if (model_.given("FACNEFFACL")) _gv += "FACNEFFACL,";
      if (model_.given("FACNEFFACW")) _gv += "FACNEFFACW,";
      if (model_.given("FACNEFFACLW")) _gv += "FACNEFFACLW,";
      if (model_.given("GFACNUDO")) _gv += "GFACNUDO,";
      if (model_.given("GFACNUDL")) _gv += "GFACNUDL,";
      if (model_.given("GFACNUDLEXP")) _gv += "GFACNUDLEXP,";
      if (model_.given("GFACNUDW")) _gv += "GFACNUDW,";
      if (model_.given("GFACNUDLW")) _gv += "GFACNUDLW,";
      if (model_.given("VSBNUDO")) _gv += "VSBNUDO,";
      if (model_.given("DVSBNUDO")) _gv += "DVSBNUDO,";
      if (model_.given("VNSUBO")) _gv += "VNSUBO,";
      if (model_.given("NSLPO")) _gv += "NSLPO,";
      if (model_.given("DNSUBO")) _gv += "DNSUBO,";
      if (model_.given("DPHIBO")) _gv += "DPHIBO,";
      if (model_.given("DPHIBL")) _gv += "DPHIBL,";
      if (model_.given("DPHIBLEXP")) _gv += "DPHIBLEXP,";
      if (model_.given("DPHIBW")) _gv += "DPHIBW,";
      if (model_.given("DPHIBLW")) _gv += "DPHIBLW,";
      if (model_.given("DELVTACO")) _gv += "DELVTACO,";
      if (model_.given("DELVTACL")) _gv += "DELVTACL,";
      if (model_.given("DELVTACLEXP")) _gv += "DELVTACLEXP,";
      if (model_.given("DELVTACW")) _gv += "DELVTACW,";
      if (model_.given("DELVTACLW")) _gv += "DELVTACLW,";
      if (model_.given("NPO")) _gv += "NPO,";
      if (model_.given("NPL")) _gv += "NPL,";
      if (model_.given("CTO")) _gv += "CTO,";
      if (model_.given("CTL")) _gv += "CTL,";
      if (model_.given("CTLEXP")) _gv += "CTLEXP,";
      if (model_.given("CTW")) _gv += "CTW,";
      if (model_.given("CTLW")) _gv += "CTLW,";
      if (model_.given("TOXOVO")) _gv += "TOXOVO,";
      if (model_.given("TOXOVDO")) _gv += "TOXOVDO,";
      if (model_.given("LOV")) _gv += "LOV,";
      if (model_.given("LOVD")) _gv += "LOVD,";
      if (model_.given("NOVO")) _gv += "NOVO,";
      if (model_.given("NOVDO")) _gv += "NOVDO,";
      if (model_.given("CFL")) _gv += "CFL,";
      if (model_.given("CFLEXP")) _gv += "CFLEXP,";
      if (model_.given("CFW")) _gv += "CFW,";
      if (model_.given("CFDO")) _gv += "CFDO,";
      if (model_.given("CFBO")) _gv += "CFBO,";
      if (model_.given("PSCEL")) _gv += "PSCEL,";
      if (model_.given("PSCELEXP")) _gv += "PSCELEXP,";
      if (model_.given("PSCEW")) _gv += "PSCEW,";
      if (model_.given("PSCEBO")) _gv += "PSCEBO,";
      if (model_.given("PSCEDO")) _gv += "PSCEDO,";
      if (model_.given("UO")) _gv += "UO,";
      if (model_.given("FBET1")) _gv += "FBET1,";
      if (model_.given("FBET1W")) _gv += "FBET1W,";
      if (model_.given("LP1")) _gv += "LP1,";
      if (model_.given("LP1W")) _gv += "LP1W,";
      if (model_.given("FBET2")) _gv += "FBET2,";
      if (model_.given("LP2")) _gv += "LP2,";
      if (model_.given("BETW1")) _gv += "BETW1,";
      if (model_.given("BETW2")) _gv += "BETW2,";
      if (model_.given("WBET")) _gv += "WBET,";
      if (model_.given("STBETO")) _gv += "STBETO,";
      if (model_.given("STBETL")) _gv += "STBETL,";
      if (model_.given("STBETW")) _gv += "STBETW,";
      if (model_.given("STBETLW")) _gv += "STBETLW,";
      if (model_.given("MUEO")) _gv += "MUEO,";
      if (model_.given("MUEW")) _gv += "MUEW,";
      if (model_.given("STMUEO")) _gv += "STMUEO,";
      if (model_.given("THEMUO")) _gv += "THEMUO,";
      if (model_.given("STTHEMUO")) _gv += "STTHEMUO,";
      if (model_.given("CSO")) _gv += "CSO,";
      if (model_.given("CSL")) _gv += "CSL,";
      if (model_.given("CSLEXP")) _gv += "CSLEXP,";
      if (model_.given("CSW")) _gv += "CSW,";
      if (model_.given("CSLW")) _gv += "CSLW,";
      if (model_.given("STCSO")) _gv += "STCSO,";
      if (model_.given("XCORO")) _gv += "XCORO,";
      if (model_.given("XCORL")) _gv += "XCORL,";
      if (model_.given("XCORW")) _gv += "XCORW,";
      if (model_.given("XCORLW")) _gv += "XCORLW,";
      if (model_.given("STXCORO")) _gv += "STXCORO,";
      if (model_.given("FETAO")) _gv += "FETAO,";
      if (model_.given("RSW1")) _gv += "RSW1,";
      if (model_.given("RSW2")) _gv += "RSW2,";
      if (model_.given("STRSO")) _gv += "STRSO,";
      if (model_.given("RSBO")) _gv += "RSBO,";
      if (model_.given("RSGO")) _gv += "RSGO,";
      if (model_.given("THESATO")) _gv += "THESATO,";
      if (model_.given("THESATL")) _gv += "THESATL,";
      if (model_.given("THESATLEXP")) _gv += "THESATLEXP,";
      if (model_.given("THESATW")) _gv += "THESATW,";
      if (model_.given("THESATLW")) _gv += "THESATLW,";
      if (model_.given("STTHESATO")) _gv += "STTHESATO,";
      if (model_.given("STTHESATL")) _gv += "STTHESATL,";
      if (model_.given("STTHESATW")) _gv += "STTHESATW,";
      if (model_.given("STTHESATLW")) _gv += "STTHESATLW,";
      if (model_.given("THESATBO")) _gv += "THESATBO,";
      if (model_.given("THESATGO")) _gv += "THESATGO,";
      if (model_.given("AXO")) _gv += "AXO,";
      if (model_.given("AXL")) _gv += "AXL,";
      if (model_.given("ALPL")) _gv += "ALPL,";
      if (model_.given("ALPLEXP")) _gv += "ALPLEXP,";
      if (model_.given("ALPW")) _gv += "ALPW,";
      if (model_.given("ALP1L1")) _gv += "ALP1L1,";
      if (model_.given("ALP1LEXP")) _gv += "ALP1LEXP,";
      if (model_.given("ALP1L2")) _gv += "ALP1L2,";
      if (model_.given("ALP1W")) _gv += "ALP1W,";
      if (model_.given("ALP2L1")) _gv += "ALP2L1,";
      if (model_.given("ALP2LEXP")) _gv += "ALP2LEXP,";
      if (model_.given("ALP2L2")) _gv += "ALP2L2,";
      if (model_.given("ALP2W")) _gv += "ALP2W,";
      if (model_.given("VPO")) _gv += "VPO,";
      if (model_.given("A1O")) _gv += "A1O,";
      if (model_.given("A1L")) _gv += "A1L,";
      if (model_.given("A1W")) _gv += "A1W,";
      if (model_.given("A2O")) _gv += "A2O,";
      if (model_.given("STA2O")) _gv += "STA2O,";
      if (model_.given("A3O")) _gv += "A3O,";
      if (model_.given("A3L")) _gv += "A3L,";
      if (model_.given("A3W")) _gv += "A3W,";
      if (model_.given("A4O")) _gv += "A4O,";
      if (model_.given("A4L")) _gv += "A4L,";
      if (model_.given("A4W")) _gv += "A4W,";
      if (model_.given("GCOO")) _gv += "GCOO,";
      if (model_.given("IGINVLW")) _gv += "IGINVLW,";
      if (model_.given("IGOVW")) _gv += "IGOVW,";
      if (model_.given("IGOVDW")) _gv += "IGOVDW,";
      if (model_.given("STIGO")) _gv += "STIGO,";
      if (model_.given("GC2O")) _gv += "GC2O,";
      if (model_.given("GC3O")) _gv += "GC3O,";
      if (model_.given("CHIBO")) _gv += "CHIBO,";
      if (model_.given("AGIDLW")) _gv += "AGIDLW,";
      if (model_.given("AGIDLDW")) _gv += "AGIDLDW,";
      if (model_.given("BGIDLO")) _gv += "BGIDLO,";
      if (model_.given("BGIDLDO")) _gv += "BGIDLDO,";
      if (model_.given("STBGIDLO")) _gv += "STBGIDLO,";
      if (model_.given("STBGIDLDO")) _gv += "STBGIDLDO,";
      if (model_.given("CGIDLO")) _gv += "CGIDLO,";
      if (model_.given("CGIDLDO")) _gv += "CGIDLDO,";
      if (model_.given("CGBOVL")) _gv += "CGBOVL,";
      if (model_.given("CFRW")) _gv += "CFRW,";
      if (model_.given("CFRDW")) _gv += "CFRDW,";
      if (model_.given("FNTO")) _gv += "FNTO,";
      if (model_.given("FNTEXCL")) _gv += "FNTEXCL,";
      if (model_.given("NFALW")) _gv += "NFALW,";
      if (model_.given("NFBLW")) _gv += "NFBLW,";
      if (model_.given("NFCLW")) _gv += "NFCLW,";
      if (model_.given("EFO")) _gv += "EFO,";
      if (model_.given("LINTNOI")) _gv += "LINTNOI,";
      if (model_.given("ALPNOI")) _gv += "ALPNOI,";
      if (model_.given("WEDGE")) _gv += "WEDGE,";
      if (model_.given("WEDGEW")) _gv += "WEDGEW,";
      if (model_.given("VFBEDGEO")) _gv += "VFBEDGEO,";
      if (model_.given("STVFBEDGEO")) _gv += "STVFBEDGEO,";
      if (model_.given("STVFBEDGEL")) _gv += "STVFBEDGEL,";
      if (model_.given("STVFBEDGEW")) _gv += "STVFBEDGEW,";
      if (model_.given("STVFBEDGELW")) _gv += "STVFBEDGELW,";
      if (model_.given("DPHIBEDGEO")) _gv += "DPHIBEDGEO,";
      if (model_.given("DPHIBEDGEL")) _gv += "DPHIBEDGEL,";
      if (model_.given("DPHIBEDGELEXP")) _gv += "DPHIBEDGELEXP,";
      if (model_.given("DPHIBEDGEW")) _gv += "DPHIBEDGEW,";
      if (model_.given("DPHIBEDGELW")) _gv += "DPHIBEDGELW,";
      if (model_.given("NSUBEDGEO")) _gv += "NSUBEDGEO,";
      if (model_.given("NSUBEDGEL")) _gv += "NSUBEDGEL,";
      if (model_.given("NSUBEDGEW")) _gv += "NSUBEDGEW,";
      if (model_.given("NSUBEDGELW")) _gv += "NSUBEDGELW,";
      if (model_.given("CTEDGEO")) _gv += "CTEDGEO,";
      if (model_.given("CTEDGEL")) _gv += "CTEDGEL,";
      if (model_.given("CTEDGELEXP")) _gv += "CTEDGELEXP,";
      if (model_.given("FBETEDGE")) _gv += "FBETEDGE,";
      if (model_.given("LPEDGE")) _gv += "LPEDGE,";
      if (model_.given("BETEDGEW")) _gv += "BETEDGEW,";
      if (model_.given("STBETEDGEO")) _gv += "STBETEDGEO,";
      if (model_.given("STBETEDGEL")) _gv += "STBETEDGEL,";
      if (model_.given("STBETEDGEW")) _gv += "STBETEDGEW,";
      if (model_.given("STBETEDGELW")) _gv += "STBETEDGELW,";
      if (model_.given("PSCEEDGEL")) _gv += "PSCEEDGEL,";
      if (model_.given("PSCEEDGELEXP")) _gv += "PSCEEDGELEXP,";
      if (model_.given("PSCEEDGEW")) _gv += "PSCEEDGEW,";
      if (model_.given("PSCEBEDGEO")) _gv += "PSCEBEDGEO,";
      if (model_.given("PSCEDEDGEO")) _gv += "PSCEDEDGEO,";
      if (model_.given("CFEDGEL")) _gv += "CFEDGEL,";
      if (model_.given("CFEDGELEXP")) _gv += "CFEDGELEXP,";
      if (model_.given("CFEDGEW")) _gv += "CFEDGEW,";
      if (model_.given("CFDEDGEO")) _gv += "CFDEDGEO,";
      if (model_.given("CFBEDGEO")) _gv += "CFBEDGEO,";
      if (model_.given("FNTEDGEO")) _gv += "FNTEDGEO,";
      if (model_.given("NFAEDGELW")) _gv += "NFAEDGELW,";
      if (model_.given("NFBEDGELW")) _gv += "NFBEDGELW,";
      if (model_.given("NFCEDGELW")) _gv += "NFCEDGELW,";
      if (model_.given("EFEDGEO")) _gv += "EFEDGEO,";
      if (model_.given("KVTHOWEO")) _gv += "KVTHOWEO,";
      if (model_.given("KVTHOWEL")) _gv += "KVTHOWEL,";
      if (model_.given("KVTHOWEW")) _gv += "KVTHOWEW,";
      if (model_.given("KVTHOWELW")) _gv += "KVTHOWELW,";
      if (model_.given("KUOWEO")) _gv += "KUOWEO,";
      if (model_.given("KUOWEL")) _gv += "KUOWEL,";
      if (model_.given("KUOWEW")) _gv += "KUOWEW,";
      if (model_.given("KUOWELW")) _gv += "KUOWELW,";
      if (model_.given("RGO")) _gv += "RGO,";
      if (model_.given("RINT")) _gv += "RINT,";
      if (model_.given("RVPOLY")) _gv += "RVPOLY,";
      if (model_.given("RSHG")) _gv += "RSHG,";
      if (model_.given("DLSIL")) _gv += "DLSIL,";
      if (model_.given("RSH")) _gv += "RSH,";
      if (model_.given("RSHD")) _gv += "RSHD,";
      if (model_.given("RBULKO")) _gv += "RBULKO,";
      if (model_.given("RWELLO")) _gv += "RWELLO,";
      if (model_.given("RJUNSO")) _gv += "RJUNSO,";
      if (model_.given("RJUNDO")) _gv += "RJUNDO,";
      if (model_.given("SAREF")) _gv += "SAREF,";
      if (model_.given("SBREF")) _gv += "SBREF,";
      if (model_.given("WLOD")) _gv += "WLOD,";
      if (model_.given("KUO")) _gv += "KUO,";
      if (model_.given("KVSAT")) _gv += "KVSAT,";
      if (model_.given("TKUO")) _gv += "TKUO,";
      if (model_.given("LKUO")) _gv += "LKUO,";
      if (model_.given("WKUO")) _gv += "WKUO,";
      if (model_.given("PKUO")) _gv += "PKUO,";
      if (model_.given("LLODKUO")) _gv += "LLODKUO,";
      if (model_.given("WLODKUO")) _gv += "WLODKUO,";
      if (model_.given("KVTHO")) _gv += "KVTHO,";
      if (model_.given("LKVTHO")) _gv += "LKVTHO,";
      if (model_.given("WKVTHO")) _gv += "WKVTHO,";
      if (model_.given("PKVTHO")) _gv += "PKVTHO,";
      if (model_.given("LLODVTH")) _gv += "LLODVTH,";
      if (model_.given("WLODVTH")) _gv += "WLODVTH,";
      if (model_.given("STETAO")) _gv += "STETAO,";
      if (model_.given("LODETAO")) _gv += "LODETAO,";
      if (model_.given("SCREF")) _gv += "SCREF,";
      if (model_.given("WEB")) _gv += "WEB,";
      if (model_.given("WEC")) _gv += "WEC,";
      if (model_.given("IMAX")) _gv += "IMAX,";
      if (model_.given("TRJ")) _gv += "TRJ,";
      if (model_.given("FREV")) _gv += "FREV,";
      if (model_.given("CJORBOT")) _gv += "CJORBOT,";
      if (model_.given("CJORSTI")) _gv += "CJORSTI,";
      if (model_.given("CJORGAT")) _gv += "CJORGAT,";
      if (model_.given("VBIRBOT")) _gv += "VBIRBOT,";
      if (model_.given("VBIRSTI")) _gv += "VBIRSTI,";
      if (model_.given("VBIRGAT")) _gv += "VBIRGAT,";
      if (model_.given("PBOT")) _gv += "PBOT,";
      if (model_.given("PSTI")) _gv += "PSTI,";
      if (model_.given("PGAT")) _gv += "PGAT,";
      if (model_.given("PHIGBOT")) _gv += "PHIGBOT,";
      if (model_.given("PHIGSTI")) _gv += "PHIGSTI,";
      if (model_.given("PHIGGAT")) _gv += "PHIGGAT,";
      if (model_.given("IDSATRBOT")) _gv += "IDSATRBOT,";
      if (model_.given("IDSATRSTI")) _gv += "IDSATRSTI,";
      if (model_.given("IDSATRGAT")) _gv += "IDSATRGAT,";
      if (model_.given("CSRHBOT")) _gv += "CSRHBOT,";
      if (model_.given("CSRHSTI")) _gv += "CSRHSTI,";
      if (model_.given("CSRHGAT")) _gv += "CSRHGAT,";
      if (model_.given("XJUNSTI")) _gv += "XJUNSTI,";
      if (model_.given("XJUNGAT")) _gv += "XJUNGAT,";
      if (model_.given("CTATBOT")) _gv += "CTATBOT,";
      if (model_.given("CTATSTI")) _gv += "CTATSTI,";
      if (model_.given("CTATGAT")) _gv += "CTATGAT,";
      if (model_.given("MEFFTATBOT")) _gv += "MEFFTATBOT,";
      if (model_.given("MEFFTATSTI")) _gv += "MEFFTATSTI,";
      if (model_.given("MEFFTATGAT")) _gv += "MEFFTATGAT,";
      if (model_.given("CBBTBOT")) _gv += "CBBTBOT,";
      if (model_.given("CBBTSTI")) _gv += "CBBTSTI,";
      if (model_.given("CBBTGAT")) _gv += "CBBTGAT,";
      if (model_.given("FBBTRBOT")) _gv += "FBBTRBOT,";
      if (model_.given("FBBTRSTI")) _gv += "FBBTRSTI,";
      if (model_.given("FBBTRGAT")) _gv += "FBBTRGAT,";
      if (model_.given("STFBBTBOT")) _gv += "STFBBTBOT,";
      if (model_.given("STFBBTSTI")) _gv += "STFBBTSTI,";
      if (model_.given("STFBBTGAT")) _gv += "STFBBTGAT,";
      if (model_.given("VBRBOT")) _gv += "VBRBOT,";
      if (model_.given("VBRSTI")) _gv += "VBRSTI,";
      if (model_.given("VBRGAT")) _gv += "VBRGAT,";
      if (model_.given("PBRBOT")) _gv += "PBRBOT,";
      if (model_.given("PBRSTI")) _gv += "PBRSTI,";
      if (model_.given("PBRGAT")) _gv += "PBRGAT,";
      if (model_.given("CJORBOTD")) _gv += "CJORBOTD,";
      if (model_.given("CJORSTID")) _gv += "CJORSTID,";
      if (model_.given("CJORGATD")) _gv += "CJORGATD,";
      if (model_.given("VBIRBOTD")) _gv += "VBIRBOTD,";
      if (model_.given("VBIRSTID")) _gv += "VBIRSTID,";
      if (model_.given("VBIRGATD")) _gv += "VBIRGATD,";
      if (model_.given("PBOTD")) _gv += "PBOTD,";
      if (model_.given("PSTID")) _gv += "PSTID,";
      if (model_.given("PGATD")) _gv += "PGATD,";
      if (model_.given("PHIGBOTD")) _gv += "PHIGBOTD,";
      if (model_.given("PHIGSTID")) _gv += "PHIGSTID,";
      if (model_.given("PHIGGATD")) _gv += "PHIGGATD,";
      if (model_.given("IDSATRBOTD")) _gv += "IDSATRBOTD,";
      if (model_.given("IDSATRSTID")) _gv += "IDSATRSTID,";
      if (model_.given("IDSATRGATD")) _gv += "IDSATRGATD,";
      if (model_.given("CSRHBOTD")) _gv += "CSRHBOTD,";
      if (model_.given("CSRHSTID")) _gv += "CSRHSTID,";
      if (model_.given("CSRHGATD")) _gv += "CSRHGATD,";
      if (model_.given("XJUNSTID")) _gv += "XJUNSTID,";
      if (model_.given("XJUNGATD")) _gv += "XJUNGATD,";
      if (model_.given("CTATBOTD")) _gv += "CTATBOTD,";
      if (model_.given("CTATSTID")) _gv += "CTATSTID,";
      if (model_.given("CTATGATD")) _gv += "CTATGATD,";
      if (model_.given("MEFFTATBOTD")) _gv += "MEFFTATBOTD,";
      if (model_.given("MEFFTATSTID")) _gv += "MEFFTATSTID,";
      if (model_.given("MEFFTATGATD")) _gv += "MEFFTATGATD,";
      if (model_.given("CBBTBOTD")) _gv += "CBBTBOTD,";
      if (model_.given("CBBTSTID")) _gv += "CBBTSTID,";
      if (model_.given("CBBTGATD")) _gv += "CBBTGATD,";
      if (model_.given("FBBTRBOTD")) _gv += "FBBTRBOTD,";
      if (model_.given("FBBTRSTID")) _gv += "FBBTRSTID,";
      if (model_.given("FBBTRGATD")) _gv += "FBBTRGATD,";
      if (model_.given("STFBBTBOTD")) _gv += "STFBBTBOTD,";
      if (model_.given("STFBBTSTID")) _gv += "STFBBTSTID,";
      if (model_.given("STFBBTGATD")) _gv += "STFBBTGATD,";
      if (model_.given("VBRBOTD")) _gv += "VBRBOTD,";
      if (model_.given("VBRSTID")) _gv += "VBRSTID,";
      if (model_.given("VBRGATD")) _gv += "VBRGATD,";
      if (model_.given("PBRBOTD")) _gv += "PBRBOTD,";
      if (model_.given("PBRSTID")) _gv += "PBRSTID,";
      if (model_.given("PBRGATD")) _gv += "PBRGATD,";
      if (model_.given("SWJUNEXP")) _gv += "SWJUNEXP,";
      if (model_.given("VJUNREF")) _gv += "VJUNREF,";
      if (model_.given("FJUNQ")) _gv += "FJUNQ,";
      if (model_.given("VJUNREFD")) _gv += "VJUNREFD,";
      if (model_.given("FJUNQD")) _gv += "FJUNQD,";
      if (given("DTA")) _gv += "DTA,";
      _p += "__GIVEN__=" + _gv + "\n";
      const char* _cbp = getenv("PYMS_CALLBACK_PARAMS");
      if (_cbp && _cbp[0]) _p += std::string("__CALLBACK__=") + _cbp + "\n";
      std::string _vc; { std::ifstream _vf(_va, std::ios::binary); std::ostringstream _vs; _vs << _vf.rdbuf(); _vc = _vs.str(); }
      std::size_t _key = std::hash<std::string>{}(std::string(_va) + "|" + _p + "|" + _vc);
      const char *_cd = getenv("PYMS_VAE_CACHE");
      std::string _cache = _cd ? _cd : "/tmp/pyms_vae_cache";
      { std::string _mk = "mkdir -p '" + _cache + "'"; if(system(_mk.c_str())){} }
      char _sob[1024]; snprintf(_sob,sizeof(_sob),"%s/vae_%s_%zx.so",_cache.c_str(),"PSP103VA",_key);
      std::string _sopath = _sob; struct stat _st;
      if (stat(_sopath.c_str(), &_st) != 0) {
        std::string _bld; const char *_pd = getenv("PYMS_DIR");
        if (_pd) { std::string t = std::string(_pd)+"/vae/build_vae_so.py"; if(stat(t.c_str(),&_st)==0) _bld=t; }
        if (_bld.empty()) { const char* cds[]={"/usr/local/share/xyce/PyMS/vae/build_vae_so.py","/usr/local/src/xyce/utils/PyMS/vae/build_vae_so.py"}; for(auto cc:cds){ if(stat(cc,&_st)==0){_bld=cc;break;} } }
        std::string _pf = _sopath + ".params"; FILE* _f=fopen(_pf.c_str(),"w"); if(_f){ fwrite(_p.data(),1,_p.size(),_f); fclose(_f); }
        if (!_bld.empty()) { std::string _cmd = "python3 '" + _bld + "' '" + std::string(_va) + "' '" + _sopath + "' '" + _pf + "' 1>&2"; if(system(_cmd.c_str())){} }
      }
      vae_dl_ = dlopen(_sopath.c_str(), RTLD_NOW);
      if (vae_dl_) { vae_eval_ = (VaeEvalFn)dlsym(vae_dl_, "vae_eval");
                     vae_jac_ = (VaeEvalFn)dlsym(vae_dl_, "vae_jacobian"); }
    }
  }
  if (vae_dl_) {
    VaeSetCbFn _setcb = (VaeSetCbFn)dlsym(vae_dl_, "vae_set_param_cb");
    if (_setcb) _setcb(&pyms_param_cb);
  }
  return true;
}

void Instance::registerLIDs(const std::vector<int> &intLIDVec,
                            const std::vector<int> &extLIDVec) {
  DeviceInstance::registerLIDs(intLIDVec, extLIDVec);
  const int n_ext_supplied = (int)extLIDVec.size();
  li_D = (0 < n_ext_supplied) ? extLIDVec[0] : -1;
  li_G = (1 < n_ext_supplied) ? extLIDVec[1] : -1;
  li_S = (2 < n_ext_supplied) ? extLIDVec[2] : -1;
  li_B = (3 < n_ext_supplied) ? extLIDVec[3] : -1;
  li_NOI = intLIDVec[0];
}

void Instance::registerStateLIDs(const std::vector<int> &v) {}
void Instance::registerStoreLIDs(const std::vector<int> &v) {}
std::map<int,std::string> &Instance::getIntNameMap() {
  static std::map<int,std::string> m;
  m[0] = "NOI";
  return m;
}
std::map<int,std::string> &Instance::getStoreNameMap() {
  static std::map<int,std::string> m; return m;
}
const std::vector<std::string> &Instance::getDepSolnVars() {
  static std::vector<std::string> v; return v;
}

void Instance::loadNodeSymbols(Util::SymbolTable &symbol_table) const {
  addInternalNode(symbol_table, li_NOI, getName(), "NOI");
}

const std::vector<std::vector<int>> &Instance::jacobianStamp() const {
  return jacStamp_;
}

void Instance::registerJacLIDs(const std::vector<std::vector<int>> &j) {
  jacLIDs_ = j;
}

bool Instance::updateIntermediateVars() {
  Linear::Vector *solVec = extData.nextSolVectorPtr;
  memset(F_, 0, sizeof(F_));
  memset(Q_, 0, sizeof(Q_));
  memset(dFdx_, 0, sizeof(dFdx_));
  memset(dQdx_, 0, sizeof(dQdx_));

  if (vae_eval_ && vae_jac_) {
    VaeState state = {};
    g_pyms_cur = this;  // callback params resolve to THIS instance
    state.V[0] = (*solVec)[li_D];
    state.V[1] = (*solVec)[li_G];
    state.V[2] = (*solVec)[li_S];
    state.V[3] = (*solVec)[li_B];
    state.V[4] = (*solVec)[li_NOI];
    state.Vt = 8.617087e-5 * 300.15;

    // Call VAE .so — supports both node-indexed and branch-indexed output
    int so_n_branches = 27;
    int so_n_nodes = 5;
    // Try to query .so for its output size
    typedef int (*IntFn)();
    IntFn nb_fn = vae_dl_ ? (IntFn)dlsym(vae_dl_, "vae_n_branches") : 0;
    IntFn nn_fn = vae_dl_ ? (IntFn)dlsym(vae_dl_, "vae_n_nodes") : 0;
    if (nb_fn) so_n_branches = nb_fn();
    if (nn_fn) so_n_nodes = nn_fn();
    bool node_indexed = (so_n_branches == so_n_nodes);

    double Fb[27]={}, Qb[27]={};
    vae_eval_(&state, Fb, Qb);

    // Sanitize NaN/Inf
    for (int i = 0; i < 27; i++) {
      if (std::isnan(Fb[i]) || std::isinf(Fb[i])) Fb[i] = 0.0;
      if (std::isnan(Qb[i]) || std::isinf(Qb[i])) Qb[i] = 0.0;
    }

    if (node_indexed) {
      // Node-indexed: F[i] = KCL contribution for node i
      for (int i = 0; i < 5; i++) {
        F_[i] += Fb[i];
        Q_[i] += Qb[i];
      }
      // Node-indexed Jacobian: dF[i]/dV[j]
      double dFn[25]={}, dQn[25]={};
      vae_jac_(&state, dFn, dQn);
      for (int i = 0; i < 5; i++)
        for (int j = 0; j < 5; j++) {
          dFdx_[i][j] += dFn[i*5+j];
          dQdx_[i][j] += dQn[i*5+j];
        }
    } else {
      // Branch-indexed: map branches to KCL node contributions.
      // The wrapper walks every contribution in the .va source,
      // but the GiNaC .so walks the same AST with parameter-
      // resolved condition culling — so its branch ordering is a
      // (possibly proper) subset of ours. Use a label-keyed remap
      // built on first call: wrapper branch wi -> GiNaC branch gi
      // (or -1 if the GiNaC walk dropped this branch as dead code).
      static const char* wrapper_branch_labels[] = {
        "I(DI,BP)",
        "I(DI,SI)",
        "I(GP,SI)",
        "I(GP,DI)",
        "I(SI,BP)",
        "I(SI,DI)",
        "I(GP,BP)",
        "I(BS,SI)",
        "I(BD,DI)",
        "I(G,GP)",
        "V(G,GP)",
        "I(S,SI)",
        "V(S,SI)",
        "I(D,DI)",
        "V(D,DI)",
        "I(BP,BI)",
        "V(BP,BI)",
        "I(BS,BI)",
        "V(BS,BI)",
        "I(BD,BI)",
        "V(BD,BI)",
        "I(B,BI)",
        "V(B,BI)",
        "I(BP,SI)",
        "I(NOII)",
        "I(NOIR)",
        "I(NOIC)",
      };
      static int branch_remap[27];
      static bool branch_remap_built = false;
      if (!branch_remap_built) {
        for (int i = 0; i < 27; i++) branch_remap[i] = -1;
        typedef const char* (*LabelFn)(int);
        LabelFn lbl_fn = (LabelFn)dlsym(vae_dl_, "vae_branch_label");
        if (lbl_fn) {
          for (int gi = 0; gi < so_n_branches; gi++) {
            const char *lbl = lbl_fn(gi);
            for (int wi = 0; wi < 27; wi++) {
              if (lbl && std::string(lbl) == wrapper_branch_labels[wi]) {
                branch_remap[wi] = gi;
                break;
              }
            }
          }
        } else {
          // No label export — assume index-aligned (legacy .so).
          for (int wi = 0; wi < 27; wi++) branch_remap[wi] = wi;
        }
        branch_remap_built = true;
      }
      double dFb[135]={}, dQb[135]={};
      vae_jac_(&state, dFb, dQb);
      { int gi = branch_remap[0]; if (gi >= 0) {
        F_[0] += Fb[gi];
        Q_[0] += Qb[gi];
        F_[3] -= Fb[gi];
        Q_[3] -= Qb[gi];
        dFdx_[0][0] += dFb[gi*5+0];
        dQdx_[0][0] += dQb[gi*5+0];
        dFdx_[3][0] -= dFb[gi*5+0];
        dQdx_[3][0] -= dQb[gi*5+0];
        dFdx_[0][1] += dFb[gi*5+1];
        dQdx_[0][1] += dQb[gi*5+1];
        dFdx_[3][1] -= dFb[gi*5+1];
        dQdx_[3][1] -= dQb[gi*5+1];
        dFdx_[0][2] += dFb[gi*5+2];
        dQdx_[0][2] += dQb[gi*5+2];
        dFdx_[3][2] -= dFb[gi*5+2];
        dQdx_[3][2] -= dQb[gi*5+2];
        dFdx_[0][3] += dFb[gi*5+3];
        dQdx_[0][3] += dQb[gi*5+3];
        dFdx_[3][3] -= dFb[gi*5+3];
        dQdx_[3][3] -= dQb[gi*5+3];
        dFdx_[0][4] += dFb[gi*5+4];
        dQdx_[0][4] += dQb[gi*5+4];
        dFdx_[3][4] -= dFb[gi*5+4];
        dQdx_[3][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[1]; if (gi >= 0) {
        F_[0] += Fb[gi];
        Q_[0] += Qb[gi];
        F_[2] -= Fb[gi];
        Q_[2] -= Qb[gi];
        dFdx_[0][0] += dFb[gi*5+0];
        dQdx_[0][0] += dQb[gi*5+0];
        dFdx_[2][0] -= dFb[gi*5+0];
        dQdx_[2][0] -= dQb[gi*5+0];
        dFdx_[0][1] += dFb[gi*5+1];
        dQdx_[0][1] += dQb[gi*5+1];
        dFdx_[2][1] -= dFb[gi*5+1];
        dQdx_[2][1] -= dQb[gi*5+1];
        dFdx_[0][2] += dFb[gi*5+2];
        dQdx_[0][2] += dQb[gi*5+2];
        dFdx_[2][2] -= dFb[gi*5+2];
        dQdx_[2][2] -= dQb[gi*5+2];
        dFdx_[0][3] += dFb[gi*5+3];
        dQdx_[0][3] += dQb[gi*5+3];
        dFdx_[2][3] -= dFb[gi*5+3];
        dQdx_[2][3] -= dQb[gi*5+3];
        dFdx_[0][4] += dFb[gi*5+4];
        dQdx_[0][4] += dQb[gi*5+4];
        dFdx_[2][4] -= dFb[gi*5+4];
        dQdx_[2][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[2]; if (gi >= 0) {
        F_[1] += Fb[gi];
        Q_[1] += Qb[gi];
        F_[2] -= Fb[gi];
        Q_[2] -= Qb[gi];
        dFdx_[1][0] += dFb[gi*5+0];
        dQdx_[1][0] += dQb[gi*5+0];
        dFdx_[2][0] -= dFb[gi*5+0];
        dQdx_[2][0] -= dQb[gi*5+0];
        dFdx_[1][1] += dFb[gi*5+1];
        dQdx_[1][1] += dQb[gi*5+1];
        dFdx_[2][1] -= dFb[gi*5+1];
        dQdx_[2][1] -= dQb[gi*5+1];
        dFdx_[1][2] += dFb[gi*5+2];
        dQdx_[1][2] += dQb[gi*5+2];
        dFdx_[2][2] -= dFb[gi*5+2];
        dQdx_[2][2] -= dQb[gi*5+2];
        dFdx_[1][3] += dFb[gi*5+3];
        dQdx_[1][3] += dQb[gi*5+3];
        dFdx_[2][3] -= dFb[gi*5+3];
        dQdx_[2][3] -= dQb[gi*5+3];
        dFdx_[1][4] += dFb[gi*5+4];
        dQdx_[1][4] += dQb[gi*5+4];
        dFdx_[2][4] -= dFb[gi*5+4];
        dQdx_[2][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[3]; if (gi >= 0) {
        F_[1] += Fb[gi];
        Q_[1] += Qb[gi];
        F_[0] -= Fb[gi];
        Q_[0] -= Qb[gi];
        dFdx_[1][0] += dFb[gi*5+0];
        dQdx_[1][0] += dQb[gi*5+0];
        dFdx_[0][0] -= dFb[gi*5+0];
        dQdx_[0][0] -= dQb[gi*5+0];
        dFdx_[1][1] += dFb[gi*5+1];
        dQdx_[1][1] += dQb[gi*5+1];
        dFdx_[0][1] -= dFb[gi*5+1];
        dQdx_[0][1] -= dQb[gi*5+1];
        dFdx_[1][2] += dFb[gi*5+2];
        dQdx_[1][2] += dQb[gi*5+2];
        dFdx_[0][2] -= dFb[gi*5+2];
        dQdx_[0][2] -= dQb[gi*5+2];
        dFdx_[1][3] += dFb[gi*5+3];
        dQdx_[1][3] += dQb[gi*5+3];
        dFdx_[0][3] -= dFb[gi*5+3];
        dQdx_[0][3] -= dQb[gi*5+3];
        dFdx_[1][4] += dFb[gi*5+4];
        dQdx_[1][4] += dQb[gi*5+4];
        dFdx_[0][4] -= dFb[gi*5+4];
        dQdx_[0][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[4]; if (gi >= 0) {
        F_[2] += Fb[gi];
        Q_[2] += Qb[gi];
        F_[3] -= Fb[gi];
        Q_[3] -= Qb[gi];
        dFdx_[2][0] += dFb[gi*5+0];
        dQdx_[2][0] += dQb[gi*5+0];
        dFdx_[3][0] -= dFb[gi*5+0];
        dQdx_[3][0] -= dQb[gi*5+0];
        dFdx_[2][1] += dFb[gi*5+1];
        dQdx_[2][1] += dQb[gi*5+1];
        dFdx_[3][1] -= dFb[gi*5+1];
        dQdx_[3][1] -= dQb[gi*5+1];
        dFdx_[2][2] += dFb[gi*5+2];
        dQdx_[2][2] += dQb[gi*5+2];
        dFdx_[3][2] -= dFb[gi*5+2];
        dQdx_[3][2] -= dQb[gi*5+2];
        dFdx_[2][3] += dFb[gi*5+3];
        dQdx_[2][3] += dQb[gi*5+3];
        dFdx_[3][3] -= dFb[gi*5+3];
        dQdx_[3][3] -= dQb[gi*5+3];
        dFdx_[2][4] += dFb[gi*5+4];
        dQdx_[2][4] += dQb[gi*5+4];
        dFdx_[3][4] -= dFb[gi*5+4];
        dQdx_[3][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[5]; if (gi >= 0) {
        F_[2] += Fb[gi];
        Q_[2] += Qb[gi];
        F_[0] -= Fb[gi];
        Q_[0] -= Qb[gi];
        dFdx_[2][0] += dFb[gi*5+0];
        dQdx_[2][0] += dQb[gi*5+0];
        dFdx_[0][0] -= dFb[gi*5+0];
        dQdx_[0][0] -= dQb[gi*5+0];
        dFdx_[2][1] += dFb[gi*5+1];
        dQdx_[2][1] += dQb[gi*5+1];
        dFdx_[0][1] -= dFb[gi*5+1];
        dQdx_[0][1] -= dQb[gi*5+1];
        dFdx_[2][2] += dFb[gi*5+2];
        dQdx_[2][2] += dQb[gi*5+2];
        dFdx_[0][2] -= dFb[gi*5+2];
        dQdx_[0][2] -= dQb[gi*5+2];
        dFdx_[2][3] += dFb[gi*5+3];
        dQdx_[2][3] += dQb[gi*5+3];
        dFdx_[0][3] -= dFb[gi*5+3];
        dQdx_[0][3] -= dQb[gi*5+3];
        dFdx_[2][4] += dFb[gi*5+4];
        dQdx_[2][4] += dQb[gi*5+4];
        dFdx_[0][4] -= dFb[gi*5+4];
        dQdx_[0][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[6]; if (gi >= 0) {
        F_[1] += Fb[gi];
        Q_[1] += Qb[gi];
        F_[3] -= Fb[gi];
        Q_[3] -= Qb[gi];
        dFdx_[1][0] += dFb[gi*5+0];
        dQdx_[1][0] += dQb[gi*5+0];
        dFdx_[3][0] -= dFb[gi*5+0];
        dQdx_[3][0] -= dQb[gi*5+0];
        dFdx_[1][1] += dFb[gi*5+1];
        dQdx_[1][1] += dQb[gi*5+1];
        dFdx_[3][1] -= dFb[gi*5+1];
        dQdx_[3][1] -= dQb[gi*5+1];
        dFdx_[1][2] += dFb[gi*5+2];
        dQdx_[1][2] += dQb[gi*5+2];
        dFdx_[3][2] -= dFb[gi*5+2];
        dQdx_[3][2] -= dQb[gi*5+2];
        dFdx_[1][3] += dFb[gi*5+3];
        dQdx_[1][3] += dQb[gi*5+3];
        dFdx_[3][3] -= dFb[gi*5+3];
        dQdx_[3][3] -= dQb[gi*5+3];
        dFdx_[1][4] += dFb[gi*5+4];
        dQdx_[1][4] += dQb[gi*5+4];
        dFdx_[3][4] -= dFb[gi*5+4];
        dQdx_[3][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[7]; if (gi >= 0) {
        F_[3] += Fb[gi];
        Q_[3] += Qb[gi];
        F_[2] -= Fb[gi];
        Q_[2] -= Qb[gi];
        dFdx_[3][0] += dFb[gi*5+0];
        dQdx_[3][0] += dQb[gi*5+0];
        dFdx_[2][0] -= dFb[gi*5+0];
        dQdx_[2][0] -= dQb[gi*5+0];
        dFdx_[3][1] += dFb[gi*5+1];
        dQdx_[3][1] += dQb[gi*5+1];
        dFdx_[2][1] -= dFb[gi*5+1];
        dQdx_[2][1] -= dQb[gi*5+1];
        dFdx_[3][2] += dFb[gi*5+2];
        dQdx_[3][2] += dQb[gi*5+2];
        dFdx_[2][2] -= dFb[gi*5+2];
        dQdx_[2][2] -= dQb[gi*5+2];
        dFdx_[3][3] += dFb[gi*5+3];
        dQdx_[3][3] += dQb[gi*5+3];
        dFdx_[2][3] -= dFb[gi*5+3];
        dQdx_[2][3] -= dQb[gi*5+3];
        dFdx_[3][4] += dFb[gi*5+4];
        dQdx_[3][4] += dQb[gi*5+4];
        dFdx_[2][4] -= dFb[gi*5+4];
        dQdx_[2][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[8]; if (gi >= 0) {
        F_[3] += Fb[gi];
        Q_[3] += Qb[gi];
        F_[0] -= Fb[gi];
        Q_[0] -= Qb[gi];
        dFdx_[3][0] += dFb[gi*5+0];
        dQdx_[3][0] += dQb[gi*5+0];
        dFdx_[0][0] -= dFb[gi*5+0];
        dQdx_[0][0] -= dQb[gi*5+0];
        dFdx_[3][1] += dFb[gi*5+1];
        dQdx_[3][1] += dQb[gi*5+1];
        dFdx_[0][1] -= dFb[gi*5+1];
        dQdx_[0][1] -= dQb[gi*5+1];
        dFdx_[3][2] += dFb[gi*5+2];
        dQdx_[3][2] += dQb[gi*5+2];
        dFdx_[0][2] -= dFb[gi*5+2];
        dQdx_[0][2] -= dQb[gi*5+2];
        dFdx_[3][3] += dFb[gi*5+3];
        dQdx_[3][3] += dQb[gi*5+3];
        dFdx_[0][3] -= dFb[gi*5+3];
        dQdx_[0][3] -= dQb[gi*5+3];
        dFdx_[3][4] += dFb[gi*5+4];
        dQdx_[3][4] += dQb[gi*5+4];
        dFdx_[0][4] -= dFb[gi*5+4];
        dQdx_[0][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[9]; if (gi >= 0) {
        F_[1] += Fb[gi];
        Q_[1] += Qb[gi];
        F_[1] -= Fb[gi];
        Q_[1] -= Qb[gi];
        dFdx_[1][0] += dFb[gi*5+0];
        dQdx_[1][0] += dQb[gi*5+0];
        dFdx_[1][0] -= dFb[gi*5+0];
        dQdx_[1][0] -= dQb[gi*5+0];
        dFdx_[1][1] += dFb[gi*5+1];
        dQdx_[1][1] += dQb[gi*5+1];
        dFdx_[1][1] -= dFb[gi*5+1];
        dQdx_[1][1] -= dQb[gi*5+1];
        dFdx_[1][2] += dFb[gi*5+2];
        dQdx_[1][2] += dQb[gi*5+2];
        dFdx_[1][2] -= dFb[gi*5+2];
        dQdx_[1][2] -= dQb[gi*5+2];
        dFdx_[1][3] += dFb[gi*5+3];
        dQdx_[1][3] += dQb[gi*5+3];
        dFdx_[1][3] -= dFb[gi*5+3];
        dQdx_[1][3] -= dQb[gi*5+3];
        dFdx_[1][4] += dFb[gi*5+4];
        dQdx_[1][4] += dQb[gi*5+4];
        dFdx_[1][4] -= dFb[gi*5+4];
        dQdx_[1][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[10]; if (gi >= 0) {
        F_[1] += Fb[gi];
        Q_[1] += Qb[gi];
        F_[1] -= Fb[gi];
        Q_[1] -= Qb[gi];
        dFdx_[1][0] += dFb[gi*5+0];
        dQdx_[1][0] += dQb[gi*5+0];
        dFdx_[1][0] -= dFb[gi*5+0];
        dQdx_[1][0] -= dQb[gi*5+0];
        dFdx_[1][1] += dFb[gi*5+1];
        dQdx_[1][1] += dQb[gi*5+1];
        dFdx_[1][1] -= dFb[gi*5+1];
        dQdx_[1][1] -= dQb[gi*5+1];
        dFdx_[1][2] += dFb[gi*5+2];
        dQdx_[1][2] += dQb[gi*5+2];
        dFdx_[1][2] -= dFb[gi*5+2];
        dQdx_[1][2] -= dQb[gi*5+2];
        dFdx_[1][3] += dFb[gi*5+3];
        dQdx_[1][3] += dQb[gi*5+3];
        dFdx_[1][3] -= dFb[gi*5+3];
        dQdx_[1][3] -= dQb[gi*5+3];
        dFdx_[1][4] += dFb[gi*5+4];
        dQdx_[1][4] += dQb[gi*5+4];
        dFdx_[1][4] -= dFb[gi*5+4];
        dQdx_[1][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[11]; if (gi >= 0) {
        F_[2] += Fb[gi];
        Q_[2] += Qb[gi];
        F_[2] -= Fb[gi];
        Q_[2] -= Qb[gi];
        dFdx_[2][0] += dFb[gi*5+0];
        dQdx_[2][0] += dQb[gi*5+0];
        dFdx_[2][0] -= dFb[gi*5+0];
        dQdx_[2][0] -= dQb[gi*5+0];
        dFdx_[2][1] += dFb[gi*5+1];
        dQdx_[2][1] += dQb[gi*5+1];
        dFdx_[2][1] -= dFb[gi*5+1];
        dQdx_[2][1] -= dQb[gi*5+1];
        dFdx_[2][2] += dFb[gi*5+2];
        dQdx_[2][2] += dQb[gi*5+2];
        dFdx_[2][2] -= dFb[gi*5+2];
        dQdx_[2][2] -= dQb[gi*5+2];
        dFdx_[2][3] += dFb[gi*5+3];
        dQdx_[2][3] += dQb[gi*5+3];
        dFdx_[2][3] -= dFb[gi*5+3];
        dQdx_[2][3] -= dQb[gi*5+3];
        dFdx_[2][4] += dFb[gi*5+4];
        dQdx_[2][4] += dQb[gi*5+4];
        dFdx_[2][4] -= dFb[gi*5+4];
        dQdx_[2][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[12]; if (gi >= 0) {
        F_[2] += Fb[gi];
        Q_[2] += Qb[gi];
        F_[2] -= Fb[gi];
        Q_[2] -= Qb[gi];
        dFdx_[2][0] += dFb[gi*5+0];
        dQdx_[2][0] += dQb[gi*5+0];
        dFdx_[2][0] -= dFb[gi*5+0];
        dQdx_[2][0] -= dQb[gi*5+0];
        dFdx_[2][1] += dFb[gi*5+1];
        dQdx_[2][1] += dQb[gi*5+1];
        dFdx_[2][1] -= dFb[gi*5+1];
        dQdx_[2][1] -= dQb[gi*5+1];
        dFdx_[2][2] += dFb[gi*5+2];
        dQdx_[2][2] += dQb[gi*5+2];
        dFdx_[2][2] -= dFb[gi*5+2];
        dQdx_[2][2] -= dQb[gi*5+2];
        dFdx_[2][3] += dFb[gi*5+3];
        dQdx_[2][3] += dQb[gi*5+3];
        dFdx_[2][3] -= dFb[gi*5+3];
        dQdx_[2][3] -= dQb[gi*5+3];
        dFdx_[2][4] += dFb[gi*5+4];
        dQdx_[2][4] += dQb[gi*5+4];
        dFdx_[2][4] -= dFb[gi*5+4];
        dQdx_[2][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[13]; if (gi >= 0) {
        F_[0] += Fb[gi];
        Q_[0] += Qb[gi];
        F_[0] -= Fb[gi];
        Q_[0] -= Qb[gi];
        dFdx_[0][0] += dFb[gi*5+0];
        dQdx_[0][0] += dQb[gi*5+0];
        dFdx_[0][0] -= dFb[gi*5+0];
        dQdx_[0][0] -= dQb[gi*5+0];
        dFdx_[0][1] += dFb[gi*5+1];
        dQdx_[0][1] += dQb[gi*5+1];
        dFdx_[0][1] -= dFb[gi*5+1];
        dQdx_[0][1] -= dQb[gi*5+1];
        dFdx_[0][2] += dFb[gi*5+2];
        dQdx_[0][2] += dQb[gi*5+2];
        dFdx_[0][2] -= dFb[gi*5+2];
        dQdx_[0][2] -= dQb[gi*5+2];
        dFdx_[0][3] += dFb[gi*5+3];
        dQdx_[0][3] += dQb[gi*5+3];
        dFdx_[0][3] -= dFb[gi*5+3];
        dQdx_[0][3] -= dQb[gi*5+3];
        dFdx_[0][4] += dFb[gi*5+4];
        dQdx_[0][4] += dQb[gi*5+4];
        dFdx_[0][4] -= dFb[gi*5+4];
        dQdx_[0][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[14]; if (gi >= 0) {
        F_[0] += Fb[gi];
        Q_[0] += Qb[gi];
        F_[0] -= Fb[gi];
        Q_[0] -= Qb[gi];
        dFdx_[0][0] += dFb[gi*5+0];
        dQdx_[0][0] += dQb[gi*5+0];
        dFdx_[0][0] -= dFb[gi*5+0];
        dQdx_[0][0] -= dQb[gi*5+0];
        dFdx_[0][1] += dFb[gi*5+1];
        dQdx_[0][1] += dQb[gi*5+1];
        dFdx_[0][1] -= dFb[gi*5+1];
        dQdx_[0][1] -= dQb[gi*5+1];
        dFdx_[0][2] += dFb[gi*5+2];
        dQdx_[0][2] += dQb[gi*5+2];
        dFdx_[0][2] -= dFb[gi*5+2];
        dQdx_[0][2] -= dQb[gi*5+2];
        dFdx_[0][3] += dFb[gi*5+3];
        dQdx_[0][3] += dQb[gi*5+3];
        dFdx_[0][3] -= dFb[gi*5+3];
        dQdx_[0][3] -= dQb[gi*5+3];
        dFdx_[0][4] += dFb[gi*5+4];
        dQdx_[0][4] += dQb[gi*5+4];
        dFdx_[0][4] -= dFb[gi*5+4];
        dQdx_[0][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[15]; if (gi >= 0) {
        F_[3] += Fb[gi];
        Q_[3] += Qb[gi];
        F_[3] -= Fb[gi];
        Q_[3] -= Qb[gi];
        dFdx_[3][0] += dFb[gi*5+0];
        dQdx_[3][0] += dQb[gi*5+0];
        dFdx_[3][0] -= dFb[gi*5+0];
        dQdx_[3][0] -= dQb[gi*5+0];
        dFdx_[3][1] += dFb[gi*5+1];
        dQdx_[3][1] += dQb[gi*5+1];
        dFdx_[3][1] -= dFb[gi*5+1];
        dQdx_[3][1] -= dQb[gi*5+1];
        dFdx_[3][2] += dFb[gi*5+2];
        dQdx_[3][2] += dQb[gi*5+2];
        dFdx_[3][2] -= dFb[gi*5+2];
        dQdx_[3][2] -= dQb[gi*5+2];
        dFdx_[3][3] += dFb[gi*5+3];
        dQdx_[3][3] += dQb[gi*5+3];
        dFdx_[3][3] -= dFb[gi*5+3];
        dQdx_[3][3] -= dQb[gi*5+3];
        dFdx_[3][4] += dFb[gi*5+4];
        dQdx_[3][4] += dQb[gi*5+4];
        dFdx_[3][4] -= dFb[gi*5+4];
        dQdx_[3][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[16]; if (gi >= 0) {
        F_[3] += Fb[gi];
        Q_[3] += Qb[gi];
        F_[3] -= Fb[gi];
        Q_[3] -= Qb[gi];
        dFdx_[3][0] += dFb[gi*5+0];
        dQdx_[3][0] += dQb[gi*5+0];
        dFdx_[3][0] -= dFb[gi*5+0];
        dQdx_[3][0] -= dQb[gi*5+0];
        dFdx_[3][1] += dFb[gi*5+1];
        dQdx_[3][1] += dQb[gi*5+1];
        dFdx_[3][1] -= dFb[gi*5+1];
        dQdx_[3][1] -= dQb[gi*5+1];
        dFdx_[3][2] += dFb[gi*5+2];
        dQdx_[3][2] += dQb[gi*5+2];
        dFdx_[3][2] -= dFb[gi*5+2];
        dQdx_[3][2] -= dQb[gi*5+2];
        dFdx_[3][3] += dFb[gi*5+3];
        dQdx_[3][3] += dQb[gi*5+3];
        dFdx_[3][3] -= dFb[gi*5+3];
        dQdx_[3][3] -= dQb[gi*5+3];
        dFdx_[3][4] += dFb[gi*5+4];
        dQdx_[3][4] += dQb[gi*5+4];
        dFdx_[3][4] -= dFb[gi*5+4];
        dQdx_[3][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[17]; if (gi >= 0) {
        F_[3] += Fb[gi];
        Q_[3] += Qb[gi];
        F_[3] -= Fb[gi];
        Q_[3] -= Qb[gi];
        dFdx_[3][0] += dFb[gi*5+0];
        dQdx_[3][0] += dQb[gi*5+0];
        dFdx_[3][0] -= dFb[gi*5+0];
        dQdx_[3][0] -= dQb[gi*5+0];
        dFdx_[3][1] += dFb[gi*5+1];
        dQdx_[3][1] += dQb[gi*5+1];
        dFdx_[3][1] -= dFb[gi*5+1];
        dQdx_[3][1] -= dQb[gi*5+1];
        dFdx_[3][2] += dFb[gi*5+2];
        dQdx_[3][2] += dQb[gi*5+2];
        dFdx_[3][2] -= dFb[gi*5+2];
        dQdx_[3][2] -= dQb[gi*5+2];
        dFdx_[3][3] += dFb[gi*5+3];
        dQdx_[3][3] += dQb[gi*5+3];
        dFdx_[3][3] -= dFb[gi*5+3];
        dQdx_[3][3] -= dQb[gi*5+3];
        dFdx_[3][4] += dFb[gi*5+4];
        dQdx_[3][4] += dQb[gi*5+4];
        dFdx_[3][4] -= dFb[gi*5+4];
        dQdx_[3][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[18]; if (gi >= 0) {
        F_[3] += Fb[gi];
        Q_[3] += Qb[gi];
        F_[3] -= Fb[gi];
        Q_[3] -= Qb[gi];
        dFdx_[3][0] += dFb[gi*5+0];
        dQdx_[3][0] += dQb[gi*5+0];
        dFdx_[3][0] -= dFb[gi*5+0];
        dQdx_[3][0] -= dQb[gi*5+0];
        dFdx_[3][1] += dFb[gi*5+1];
        dQdx_[3][1] += dQb[gi*5+1];
        dFdx_[3][1] -= dFb[gi*5+1];
        dQdx_[3][1] -= dQb[gi*5+1];
        dFdx_[3][2] += dFb[gi*5+2];
        dQdx_[3][2] += dQb[gi*5+2];
        dFdx_[3][2] -= dFb[gi*5+2];
        dQdx_[3][2] -= dQb[gi*5+2];
        dFdx_[3][3] += dFb[gi*5+3];
        dQdx_[3][3] += dQb[gi*5+3];
        dFdx_[3][3] -= dFb[gi*5+3];
        dQdx_[3][3] -= dQb[gi*5+3];
        dFdx_[3][4] += dFb[gi*5+4];
        dQdx_[3][4] += dQb[gi*5+4];
        dFdx_[3][4] -= dFb[gi*5+4];
        dQdx_[3][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[19]; if (gi >= 0) {
        F_[3] += Fb[gi];
        Q_[3] += Qb[gi];
        F_[3] -= Fb[gi];
        Q_[3] -= Qb[gi];
        dFdx_[3][0] += dFb[gi*5+0];
        dQdx_[3][0] += dQb[gi*5+0];
        dFdx_[3][0] -= dFb[gi*5+0];
        dQdx_[3][0] -= dQb[gi*5+0];
        dFdx_[3][1] += dFb[gi*5+1];
        dQdx_[3][1] += dQb[gi*5+1];
        dFdx_[3][1] -= dFb[gi*5+1];
        dQdx_[3][1] -= dQb[gi*5+1];
        dFdx_[3][2] += dFb[gi*5+2];
        dQdx_[3][2] += dQb[gi*5+2];
        dFdx_[3][2] -= dFb[gi*5+2];
        dQdx_[3][2] -= dQb[gi*5+2];
        dFdx_[3][3] += dFb[gi*5+3];
        dQdx_[3][3] += dQb[gi*5+3];
        dFdx_[3][3] -= dFb[gi*5+3];
        dQdx_[3][3] -= dQb[gi*5+3];
        dFdx_[3][4] += dFb[gi*5+4];
        dQdx_[3][4] += dQb[gi*5+4];
        dFdx_[3][4] -= dFb[gi*5+4];
        dQdx_[3][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[20]; if (gi >= 0) {
        F_[3] += Fb[gi];
        Q_[3] += Qb[gi];
        F_[3] -= Fb[gi];
        Q_[3] -= Qb[gi];
        dFdx_[3][0] += dFb[gi*5+0];
        dQdx_[3][0] += dQb[gi*5+0];
        dFdx_[3][0] -= dFb[gi*5+0];
        dQdx_[3][0] -= dQb[gi*5+0];
        dFdx_[3][1] += dFb[gi*5+1];
        dQdx_[3][1] += dQb[gi*5+1];
        dFdx_[3][1] -= dFb[gi*5+1];
        dQdx_[3][1] -= dQb[gi*5+1];
        dFdx_[3][2] += dFb[gi*5+2];
        dQdx_[3][2] += dQb[gi*5+2];
        dFdx_[3][2] -= dFb[gi*5+2];
        dQdx_[3][2] -= dQb[gi*5+2];
        dFdx_[3][3] += dFb[gi*5+3];
        dQdx_[3][3] += dQb[gi*5+3];
        dFdx_[3][3] -= dFb[gi*5+3];
        dQdx_[3][3] -= dQb[gi*5+3];
        dFdx_[3][4] += dFb[gi*5+4];
        dQdx_[3][4] += dQb[gi*5+4];
        dFdx_[3][4] -= dFb[gi*5+4];
        dQdx_[3][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[21]; if (gi >= 0) {
        F_[3] += Fb[gi];
        Q_[3] += Qb[gi];
        F_[3] -= Fb[gi];
        Q_[3] -= Qb[gi];
        dFdx_[3][0] += dFb[gi*5+0];
        dQdx_[3][0] += dQb[gi*5+0];
        dFdx_[3][0] -= dFb[gi*5+0];
        dQdx_[3][0] -= dQb[gi*5+0];
        dFdx_[3][1] += dFb[gi*5+1];
        dQdx_[3][1] += dQb[gi*5+1];
        dFdx_[3][1] -= dFb[gi*5+1];
        dQdx_[3][1] -= dQb[gi*5+1];
        dFdx_[3][2] += dFb[gi*5+2];
        dQdx_[3][2] += dQb[gi*5+2];
        dFdx_[3][2] -= dFb[gi*5+2];
        dQdx_[3][2] -= dQb[gi*5+2];
        dFdx_[3][3] += dFb[gi*5+3];
        dQdx_[3][3] += dQb[gi*5+3];
        dFdx_[3][3] -= dFb[gi*5+3];
        dQdx_[3][3] -= dQb[gi*5+3];
        dFdx_[3][4] += dFb[gi*5+4];
        dQdx_[3][4] += dQb[gi*5+4];
        dFdx_[3][4] -= dFb[gi*5+4];
        dQdx_[3][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[22]; if (gi >= 0) {
        F_[3] += Fb[gi];
        Q_[3] += Qb[gi];
        F_[3] -= Fb[gi];
        Q_[3] -= Qb[gi];
        dFdx_[3][0] += dFb[gi*5+0];
        dQdx_[3][0] += dQb[gi*5+0];
        dFdx_[3][0] -= dFb[gi*5+0];
        dQdx_[3][0] -= dQb[gi*5+0];
        dFdx_[3][1] += dFb[gi*5+1];
        dQdx_[3][1] += dQb[gi*5+1];
        dFdx_[3][1] -= dFb[gi*5+1];
        dQdx_[3][1] -= dQb[gi*5+1];
        dFdx_[3][2] += dFb[gi*5+2];
        dQdx_[3][2] += dQb[gi*5+2];
        dFdx_[3][2] -= dFb[gi*5+2];
        dQdx_[3][2] -= dQb[gi*5+2];
        dFdx_[3][3] += dFb[gi*5+3];
        dQdx_[3][3] += dQb[gi*5+3];
        dFdx_[3][3] -= dFb[gi*5+3];
        dQdx_[3][3] -= dQb[gi*5+3];
        dFdx_[3][4] += dFb[gi*5+4];
        dQdx_[3][4] += dQb[gi*5+4];
        dFdx_[3][4] -= dFb[gi*5+4];
        dQdx_[3][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[23]; if (gi >= 0) {
        F_[3] += Fb[gi];
        Q_[3] += Qb[gi];
        F_[2] -= Fb[gi];
        Q_[2] -= Qb[gi];
        dFdx_[3][0] += dFb[gi*5+0];
        dQdx_[3][0] += dQb[gi*5+0];
        dFdx_[2][0] -= dFb[gi*5+0];
        dQdx_[2][0] -= dQb[gi*5+0];
        dFdx_[3][1] += dFb[gi*5+1];
        dQdx_[3][1] += dQb[gi*5+1];
        dFdx_[2][1] -= dFb[gi*5+1];
        dQdx_[2][1] -= dQb[gi*5+1];
        dFdx_[3][2] += dFb[gi*5+2];
        dQdx_[3][2] += dQb[gi*5+2];
        dFdx_[2][2] -= dFb[gi*5+2];
        dQdx_[2][2] -= dQb[gi*5+2];
        dFdx_[3][3] += dFb[gi*5+3];
        dQdx_[3][3] += dQb[gi*5+3];
        dFdx_[2][3] -= dFb[gi*5+3];
        dQdx_[2][3] -= dQb[gi*5+3];
        dFdx_[3][4] += dFb[gi*5+4];
        dQdx_[3][4] += dQb[gi*5+4];
        dFdx_[2][4] -= dFb[gi*5+4];
        dQdx_[2][4] -= dQb[gi*5+4];
      } }
      { int gi = branch_remap[24]; if (gi >= 0) {
        F_[4] += Fb[gi];
        Q_[4] += Qb[gi];
        dFdx_[4][0] += dFb[gi*5+0];
        dQdx_[4][0] += dQb[gi*5+0];
        dFdx_[4][1] += dFb[gi*5+1];
        dQdx_[4][1] += dQb[gi*5+1];
        dFdx_[4][2] += dFb[gi*5+2];
        dQdx_[4][2] += dQb[gi*5+2];
        dFdx_[4][3] += dFb[gi*5+3];
        dQdx_[4][3] += dQb[gi*5+3];
        dFdx_[4][4] += dFb[gi*5+4];
        dQdx_[4][4] += dQb[gi*5+4];
      } }
      { int gi = branch_remap[25]; if (gi >= 0) {
        F_[4] += Fb[gi];
        Q_[4] += Qb[gi];
        dFdx_[4][0] += dFb[gi*5+0];
        dQdx_[4][0] += dQb[gi*5+0];
        dFdx_[4][1] += dFb[gi*5+1];
        dQdx_[4][1] += dQb[gi*5+1];
        dFdx_[4][2] += dFb[gi*5+2];
        dQdx_[4][2] += dQb[gi*5+2];
        dFdx_[4][3] += dFb[gi*5+3];
        dQdx_[4][3] += dQb[gi*5+3];
        dFdx_[4][4] += dFb[gi*5+4];
        dQdx_[4][4] += dQb[gi*5+4];
      } }
      { int gi = branch_remap[26]; if (gi >= 0) {
        F_[4] += Fb[gi];
        Q_[4] += Qb[gi];
        dFdx_[4][0] += dFb[gi*5+0];
        dQdx_[4][0] += dQb[gi*5+0];
        dFdx_[4][1] += dFb[gi*5+1];
        dQdx_[4][1] += dQb[gi*5+1];
        dFdx_[4][2] += dFb[gi*5+2];
        dQdx_[4][2] += dQb[gi*5+2];
        dFdx_[4][3] += dFb[gi*5+3];
        dQdx_[4][3] += dQb[gi*5+3];
        dFdx_[4][4] += dFb[gi*5+4];
        dQdx_[4][4] += dQb[gi*5+4];
      } }
    }
  }

  // Diagonal regularization (gmin) to keep the matrix non-singular
  const double gmin_ext = 1e-12;
  const double gmin_int = 1e-9;
  Linear::Vector *solVec2 = extData.nextSolVectorPtr;
  F_[0] += gmin_ext * (*solVec2)[li_D];
  dFdx_[0][0] += gmin_ext;
  F_[1] += gmin_ext * (*solVec2)[li_G];
  dFdx_[1][1] += gmin_ext;
  F_[2] += gmin_ext * (*solVec2)[li_S];
  dFdx_[2][2] += gmin_ext;
  F_[3] += gmin_ext * (*solVec2)[li_B];
  dFdx_[3][3] += gmin_ext;
  F_[4] += gmin_int * (*solVec2)[li_NOI];
  dFdx_[4][4] += gmin_int;

  return true;
}

bool Instance::updatePrimaryState() {
  return updateIntermediateVars();
}

bool Instance::loadDAEFVector() {
  Linear::Vector &fVec = *(extData.daeFVectorPtr);
  fVec[li_D] += F_[0];
  fVec[li_G] += F_[1];
  fVec[li_S] += F_[2];
  fVec[li_B] += F_[3];
  fVec[li_NOI] += F_[4];
  return true;
}

bool Instance::loadDAEQVector() {
  Linear::Vector &qVec = *(extData.daeQVectorPtr);
  qVec[li_D] += Q_[0];
  qVec[li_G] += Q_[1];
  qVec[li_S] += Q_[2];
  qVec[li_B] += Q_[3];
  qVec[li_NOI] += Q_[4];
  return true;
}

bool Instance::loadDAEdFdx() {
  Linear::Matrix &dFdx = *(extData.dFdxMatrixPtr);
  dFdx[li_D][jacLIDs_[0][0]] += dFdx_[0][0];
  dFdx[li_D][jacLIDs_[0][1]] += dFdx_[0][1];
  dFdx[li_D][jacLIDs_[0][2]] += dFdx_[0][2];
  dFdx[li_D][jacLIDs_[0][3]] += dFdx_[0][3];
  dFdx[li_D][jacLIDs_[0][4]] += dFdx_[0][4];
  dFdx[li_G][jacLIDs_[1][0]] += dFdx_[1][0];
  dFdx[li_G][jacLIDs_[1][1]] += dFdx_[1][1];
  dFdx[li_G][jacLIDs_[1][2]] += dFdx_[1][2];
  dFdx[li_G][jacLIDs_[1][3]] += dFdx_[1][3];
  dFdx[li_G][jacLIDs_[1][4]] += dFdx_[1][4];
  dFdx[li_S][jacLIDs_[2][0]] += dFdx_[2][0];
  dFdx[li_S][jacLIDs_[2][1]] += dFdx_[2][1];
  dFdx[li_S][jacLIDs_[2][2]] += dFdx_[2][2];
  dFdx[li_S][jacLIDs_[2][3]] += dFdx_[2][3];
  dFdx[li_S][jacLIDs_[2][4]] += dFdx_[2][4];
  dFdx[li_B][jacLIDs_[3][0]] += dFdx_[3][0];
  dFdx[li_B][jacLIDs_[3][1]] += dFdx_[3][1];
  dFdx[li_B][jacLIDs_[3][2]] += dFdx_[3][2];
  dFdx[li_B][jacLIDs_[3][3]] += dFdx_[3][3];
  dFdx[li_B][jacLIDs_[3][4]] += dFdx_[3][4];
  dFdx[li_NOI][jacLIDs_[4][0]] += dFdx_[4][0];
  dFdx[li_NOI][jacLIDs_[4][1]] += dFdx_[4][1];
  dFdx[li_NOI][jacLIDs_[4][2]] += dFdx_[4][2];
  dFdx[li_NOI][jacLIDs_[4][3]] += dFdx_[4][3];
  dFdx[li_NOI][jacLIDs_[4][4]] += dFdx_[4][4];
  return true;
}

bool Instance::loadDAEdQdx() {
  Linear::Matrix &dQdx = *(extData.dQdxMatrixPtr);
  dQdx[li_D][jacLIDs_[0][0]] += dQdx_[0][0];
  dQdx[li_D][jacLIDs_[0][1]] += dQdx_[0][1];
  dQdx[li_D][jacLIDs_[0][2]] += dQdx_[0][2];
  dQdx[li_D][jacLIDs_[0][3]] += dQdx_[0][3];
  dQdx[li_D][jacLIDs_[0][4]] += dQdx_[0][4];
  dQdx[li_G][jacLIDs_[1][0]] += dQdx_[1][0];
  dQdx[li_G][jacLIDs_[1][1]] += dQdx_[1][1];
  dQdx[li_G][jacLIDs_[1][2]] += dQdx_[1][2];
  dQdx[li_G][jacLIDs_[1][3]] += dQdx_[1][3];
  dQdx[li_G][jacLIDs_[1][4]] += dQdx_[1][4];
  dQdx[li_S][jacLIDs_[2][0]] += dQdx_[2][0];
  dQdx[li_S][jacLIDs_[2][1]] += dQdx_[2][1];
  dQdx[li_S][jacLIDs_[2][2]] += dQdx_[2][2];
  dQdx[li_S][jacLIDs_[2][3]] += dQdx_[2][3];
  dQdx[li_S][jacLIDs_[2][4]] += dQdx_[2][4];
  dQdx[li_B][jacLIDs_[3][0]] += dQdx_[3][0];
  dQdx[li_B][jacLIDs_[3][1]] += dQdx_[3][1];
  dQdx[li_B][jacLIDs_[3][2]] += dQdx_[3][2];
  dQdx[li_B][jacLIDs_[3][3]] += dQdx_[3][3];
  dQdx[li_B][jacLIDs_[3][4]] += dQdx_[3][4];
  dQdx[li_NOI][jacLIDs_[4][0]] += dQdx_[4][0];
  dQdx[li_NOI][jacLIDs_[4][1]] += dQdx_[4][1];
  dQdx[li_NOI][jacLIDs_[4][2]] += dQdx_[4][2];
  dQdx[li_NOI][jacLIDs_[4][3]] += dQdx_[4][3];
  dQdx[li_NOI][jacLIDs_[4][4]] += dQdx_[4][4];
  return true;
}

Model::Model(const Configuration &config, const ModelBlock &mb,
             const FactoryBlock &fb)
  : DeviceModel(mb, config.getModelParameters(), fb)
{
  LEVEL = 103.0;
  TYPE = 1.0;
  TR = 21.0;
  SWGEO = 1.0;
  SWIGATE = 0.0;
  SWIMPACT = 0.0;
  SWGIDL = 0.0;
  SWJUNCAP = 0.0;
  SWJUNASYM = 0.0;
  SWNUD = 0.0;
  SWEDGE = 0.0;
  SWDELVTAC = 0.0;
  SWIGN = 1.0;
  QMC = 1.0;
  VFB = -1.0;
  STVFB = 0.0005;
  TOX = 2e-09;
  EPSROX = 3.9;
  NEFF = 5e+23;
  FACNEFFAC = 1.0;
  GFACNUD = 1.0;
  VSBNUD = 0.0;
  DVSBNUD = 1.0;
  VNSUB = 0.0;
  NSLP = 0.05;
  DNSUB = 0.0;
  DPHIB = 0.0;
  DELVTAC = 0.0;
  NP = 1e+26;
  CT = 0.0;
  TOXOV = 2e-09;
  TOXOVD = 2e-09;
  NOV = 5e+25;
  NOVD = 5e+25;
  CF = 0.0;
  CFD = 0.0;
  CFB = 0.0;
  PSCE = 0.0;
  PSCEB = 0.0;
  PSCED = 0.0;
  BETN = 0.07;
  STBET = 1.0;
  MUE = 0.5;
  STMUE = 0.0;
  THEMU = 1.5;
  STTHEMU = 1.5;
  CS = 0.0;
  STCS = 0.0;
  XCOR = 0.0;
  STXCOR = 0.0;
  FETA = 1.0;
  RS = 30.0;
  STRS = 1.0;
  RSB = 0.0;
  RSG = 0.0;
  THESAT = 1.0;
  STTHESAT = 1.0;
  THESATB = 0.0;
  THESATG = 0.0;
  AX = 3.0;
  ALP = 0.01;
  ALP1 = 0.0;
  ALP2 = 0.0;
  VP = 0.05;
  A1 = 1.0;
  A2 = 10.0;
  STA2 = 0.0;
  A3 = 1.0;
  A4 = 0.0;
  GCO = 0.0;
  IGINV = 0.0;
  IGOV = 0.0;
  IGOVD = 0.0;
  STIG = 2.0;
  GC2 = 0.375;
  GC3 = 0.063;
  CHIB = 3.1;
  AGIDL = 0.0;
  AGIDLD = 0.0;
  BGIDL = 41.0;
  BGIDLD = 41.0;
  STBGIDL = 0.0;
  STBGIDLD = 0.0;
  CGIDL = 0.0;
  CGIDLD = 0.0;
  COX = 1e-14;
  CGOV = 1e-15;
  CGOVD = 1e-15;
  CGBOV = 0.0;
  CFR = 0.0;
  CFRD = 0.0;
  FNT = 1.0;
  FNTEXC = 0.0;
  NFA = 8e+22;
  NFB = 30000000.0;
  NFC = 0.0;
  EF = 1.0;
  VFBEDGE = -1.0;
  STVFBEDGE = 0.0005;
  DPHIBEDGE = 0.0;
  NEFFEDGE = 5e+23;
  CTEDGE = 0.0;
  BETNEDGE = 0.0005;
  STBETEDGE = 1.0;
  PSCEEDGE = 0.0;
  PSCEBEDGE = 0.0;
  PSCEDEDGE = 0.0;
  CFEDGE = 0.0;
  CFDEDGE = 0.0;
  CFBEDGE = 0.0;
  FNTEDGE = 1.0;
  NFAEDGE = 8e+22;
  NFBEDGE = 30000000.0;
  NFCEDGE = 0.0;
  EFEDGE = 1.0;
  RG = 0.0;
  RSE = 0.0;
  RDE = 0.0;
  RBULK = 0.0;
  RWELL = 0.0;
  RJUNS = 0.0;
  RJUND = 0.0;
  POVFB = -1.0;
  PLVFB = 0.0;
  PWVFB = 0.0;
  PLWVFB = 0.0;
  POSTVFB = 0.0005;
  PLSTVFB = 0.0;
  PWSTVFB = 0.0;
  PLWSTVFB = 0.0;
  POTOX = 2e-09;
  POEPSROX = 3.9;
  PONEFF = 5e+23;
  PLNEFF = 0.0;
  PWNEFF = 0.0;
  PLWNEFF = 0.0;
  POFACNEFFAC = 1.0;
  PLFACNEFFAC = 0.0;
  PWFACNEFFAC = 0.0;
  PLWFACNEFFAC = 0.0;
  POGFACNUD = 1.0;
  PLGFACNUD = 0.0;
  PWGFACNUD = 0.0;
  PLWGFACNUD = 0.0;
  POVSBNUD = 0.0;
  PODVSBNUD = 1.0;
  POVNSUB = 0.0;
  PONSLP = 0.05;
  PODNSUB = 0.0;
  PODPHIB = 0.0;
  PLDPHIB = 0.0;
  PWDPHIB = 0.0;
  PLWDPHIB = 0.0;
  PODELVTAC = 0.0;
  PLDELVTAC = 0.0;
  PWDELVTAC = 0.0;
  PLWDELVTAC = 0.0;
  PONP = 1e+26;
  PLNP = 0.0;
  PWNP = 0.0;
  PLWNP = 0.0;
  POCT = 0.0;
  PLCT = 0.0;
  PWCT = 0.0;
  PLWCT = 0.0;
  POTOXOV = 2e-09;
  POTOXOVD = 2e-09;
  PONOV = 5e+25;
  PLNOV = 0.0;
  PWNOV = 0.0;
  PLWNOV = 0.0;
  PONOVD = 5e+25;
  PLNOVD = 0.0;
  PWNOVD = 0.0;
  PLWNOVD = 0.0;
  POCF = 0.0;
  PLCF = 0.0;
  PWCF = 0.0;
  PLWCF = 0.0;
  POCFD = 0.0;
  POCFB = 0.0;
  POPSCE = 0.0;
  PLPSCE = 0.0;
  PWPSCE = 0.0;
  PLWPSCE = 0.0;
  POPSCEB = 0.0;
  POPSCED = 0.0;
  POBETN = 0.07;
  PLBETN = 0.0;
  PWBETN = 0.0;
  PLWBETN = 0.0;
  POSTBET = 1.0;
  PLSTBET = 0.0;
  PWSTBET = 0.0;
  PLWSTBET = 0.0;
  POMUE = 0.5;
  PLMUE = 0.0;
  PWMUE = 0.0;
  PLWMUE = 0.0;
  POSTMUE = 0.0;
  POTHEMU = 1.5;
  POSTTHEMU = 1.5;
  POCS = 0.0;
  PLCS = 0.0;
  PWCS = 0.0;
  PLWCS = 0.0;
  POSTCS = 0.0;
  POXCOR = 0.0;
  PLXCOR = 0.0;
  PWXCOR = 0.0;
  PLWXCOR = 0.0;
  POSTXCOR = 0.0;
  POFETA = 1.0;
  PORS = 30.0;
  PLRS = 0.0;
  PWRS = 0.0;
  PLWRS = 0.0;
  POSTRS = 1.0;
  PORSB = 0.0;
  PORSG = 0.0;
  POTHESAT = 1.0;
  PLTHESAT = 0.0;
  PWTHESAT = 0.0;
  PLWTHESAT = 0.0;
  POSTTHESAT = 1.0;
  PLSTTHESAT = 0.0;
  PWSTTHESAT = 0.0;
  PLWSTTHESAT = 0.0;
  POTHESATB = 0.0;
  PLTHESATB = 0.0;
  PWTHESATB = 0.0;
  PLWTHESATB = 0.0;
  POTHESATG = 0.0;
  PLTHESATG = 0.0;
  PWTHESATG = 0.0;
  PLWTHESATG = 0.0;
  POAX = 3.0;
  PLAX = 0.0;
  PWAX = 0.0;
  PLWAX = 0.0;
  POALP = 0.01;
  PLALP = 0.0;
  PWALP = 0.0;
  PLWALP = 0.0;
  POALP1 = 0.0;
  PLALP1 = 0.0;
  PWALP1 = 0.0;
  PLWALP1 = 0.0;
  POALP2 = 0.0;
  PLALP2 = 0.0;
  PWALP2 = 0.0;
  PLWALP2 = 0.0;
  POVP = 0.05;
  POA1 = 1.0;
  PLA1 = 0.0;
  PWA1 = 0.0;
  PLWA1 = 0.0;
  POA2 = 10.0;
  POSTA2 = 0.0;
  POA3 = 1.0;
  PLA3 = 0.0;
  PWA3 = 0.0;
  PLWA3 = 0.0;
  POA4 = 0.0;
  PLA4 = 0.0;
  PWA4 = 0.0;
  PLWA4 = 0.0;
  POGCO = 0.0;
  POIGINV = 0.0;
  PLIGINV = 0.0;
  PWIGINV = 0.0;
  PLWIGINV = 0.0;
  POIGOV = 0.0;
  PLIGOV = 0.0;
  PWIGOV = 0.0;
  PLWIGOV = 0.0;
  POIGOVD = 0.0;
  PLIGOVD = 0.0;
  PWIGOVD = 0.0;
  PLWIGOVD = 0.0;
  POSTIG = 2.0;
  POGC2 = 0.375;
  POGC3 = 0.063;
  POCHIB = 3.1;
  POAGIDL = 0.0;
  PLAGIDL = 0.0;
  PWAGIDL = 0.0;
  PLWAGIDL = 0.0;
  POAGIDLD = 0.0;
  PLAGIDLD = 0.0;
  PWAGIDLD = 0.0;
  PLWAGIDLD = 0.0;
  POBGIDL = 41.0;
  POBGIDLD = 41.0;
  POSTBGIDL = 0.0;
  POSTBGIDLD = 0.0;
  POCGIDL = 0.0;
  POCGIDLD = 0.0;
  POCOX = 1e-14;
  PLCOX = 0.0;
  PWCOX = 0.0;
  PLWCOX = 0.0;
  POCGOV = 1e-15;
  PLCGOV = 0.0;
  PWCGOV = 0.0;
  PLWCGOV = 0.0;
  POCGOVD = 1e-15;
  PLCGOVD = 0.0;
  PWCGOVD = 0.0;
  PLWCGOVD = 0.0;
  POCGBOV = 0.0;
  PLCGBOV = 0.0;
  PWCGBOV = 0.0;
  PLWCGBOV = 0.0;
  POCFR = 0.0;
  PLCFR = 0.0;
  PWCFR = 0.0;
  PLWCFR = 0.0;
  POCFRD = 0.0;
  PLCFRD = 0.0;
  PWCFRD = 0.0;
  PLWCFRD = 0.0;
  POFNT = 1.0;
  POFNTEXC = 0.0;
  PLFNTEXC = 0.0;
  PWFNTEXC = 0.0;
  PLWFNTEXC = 0.0;
  PONFA = 8e+22;
  PLNFA = 0.0;
  PWNFA = 0.0;
  PLWNFA = 0.0;
  PONFB = 30000000.0;
  PLNFB = 0.0;
  PWNFB = 0.0;
  PLWNFB = 0.0;
  PONFC = 0.0;
  PLNFC = 0.0;
  PWNFC = 0.0;
  PLWNFC = 0.0;
  POEF = 1.0;
  POVFBEDGE = -1.0;
  POSTVFBEDGE = 0.0;
  PLSTVFBEDGE = 0.0;
  PWSTVFBEDGE = 0.0;
  PLWSTVFBEDGE = 0.0;
  PODPHIBEDGE = 0.0;
  PLDPHIBEDGE = 0.0;
  PWDPHIBEDGE = 0.0;
  PLWDPHIBEDGE = 0.0;
  PONEFFEDGE = 5e+23;
  PLNEFFEDGE = 0.0;
  PWNEFFEDGE = 0.0;
  PLWNEFFEDGE = 0.0;
  POCTEDGE = 0.0;
  PLCTEDGE = 0.0;
  PWCTEDGE = 0.0;
  PLWCTEDGE = 0.0;
  POBETNEDGE = 0.0005;
  PLBETNEDGE = 0.0;
  PWBETNEDGE = 0.0;
  PLWBETNEDGE = 0.0;
  POSTBETEDGE = 1.0;
  PLSTBETEDGE = 0.0;
  PWSTBETEDGE = 0.0;
  PLWSTBETEDGE = 0.0;
  POPSCEEDGE = 0.0;
  PLPSCEEDGE = 0.0;
  PWPSCEEDGE = 0.0;
  PLWPSCEEDGE = 0.0;
  POPSCEBEDGE = 0.0;
  POPSCEDEDGE = 0.0;
  POCFEDGE = 0.0;
  PLCFEDGE = 0.0;
  PWCFEDGE = 0.0;
  PLWCFEDGE = 0.0;
  POCFDEDGE = 0.0;
  POCFBEDGE = 0.0;
  POFNTEDGE = 1.0;
  PONFAEDGE = 8e+22;
  PLNFAEDGE = 0.0;
  PWNFAEDGE = 0.0;
  PLWNFAEDGE = 0.0;
  PONFBEDGE = 30000000.0;
  PLNFBEDGE = 0.0;
  PWNFBEDGE = 0.0;
  PLWNFBEDGE = 0.0;
  PONFCEDGE = 0.0;
  PLNFCEDGE = 0.0;
  PWNFCEDGE = 0.0;
  PLWNFCEDGE = 0.0;
  POEFEDGE = 1.0;
  POKVTHOWE = 0.0;
  PLKVTHOWE = 0.0;
  PWKVTHOWE = 0.0;
  PLWKVTHOWE = 0.0;
  POKUOWE = 0.0;
  PLKUOWE = 0.0;
  PWKUOWE = 0.0;
  PLWKUOWE = 0.0;
  LMIN = 0.0;
  LMAX = 1.0;
  WMIN = 0.0;
  WMAX = 1.0;
  LVARO = 0.0;
  LVARL = 0.0;
  LVARW = 0.0;
  LAP = 0.0;
  WVARO = 0.0;
  WVARL = 0.0;
  WVARW = 0.0;
  WOT = 0.0;
  DLQ = 0.0;
  DWQ = 0.0;
  VFBO = -1.0;
  VFBL = 0.0;
  VFBW = 0.0;
  VFBLW = 0.0;
  STVFBO = 0.0005;
  STVFBL = 0.0;
  STVFBW = 0.0;
  STVFBLW = 0.0;
  TOXO = 2e-09;
  EPSROXO = 3.9;
  NSUBO = 3e+23;
  NSUBW = 0.0;
  WSEG = 1e-08;
  NPCK = 1e+24;
  NPCKW = 0.0;
  WSEGP = 1e-08;
  LPCK = 1e-08;
  LPCKW = 0.0;
  FOL1 = 0.0;
  FOL2 = 0.0;
  FACNEFFACO = 1.0;
  FACNEFFACL = 0.0;
  FACNEFFACW = 0.0;
  FACNEFFACLW = 0.0;
  GFACNUDO = 1.0;
  GFACNUDL = 0.0;
  GFACNUDLEXP = 1.0;
  GFACNUDW = 0.0;
  GFACNUDLW = 0.0;
  VSBNUDO = 0.0;
  DVSBNUDO = 1.0;
  VNSUBO = 0.0;
  NSLPO = 0.05;
  DNSUBO = 0.0;
  DPHIBO = 0.0;
  DPHIBL = 0.0;
  DPHIBLEXP = 1.0;
  DPHIBW = 0.0;
  DPHIBLW = 0.0;
  DELVTACO = 0.0;
  DELVTACL = 0.0;
  DELVTACLEXP = 1.0;
  DELVTACW = 0.0;
  DELVTACLW = 0.0;
  NPO = 1e+26;
  NPL = 0.0;
  CTO = 0.0;
  CTL = 0.0;
  CTLEXP = 1.0;
  CTW = 0.0;
  CTLW = 0.0;
  TOXOVO = 2e-09;
  TOXOVDO = 2e-09;
  LOV = 0.0;
  LOVD = 0.0;
  NOVO = 5e+25;
  NOVDO = 5e+25;
  CFL = 0.0;
  CFLEXP = 2.0;
  CFW = 0.0;
  CFDO = 0.0;
  CFBO = 0.0;
  PSCEL = 0.0;
  PSCELEXP = 2.0;
  PSCEW = 0.0;
  PSCEBO = 0.0;
  PSCEDO = 0.0;
  UO = 0.05;
  FBET1 = 0.0;
  FBET1W = 0.0;
  LP1 = 1e-08;
  LP1W = 0.0;
  FBET2 = 0.0;
  LP2 = 1e-08;
  BETW1 = 0.0;
  BETW2 = 0.0;
  WBET = 1e-09;
  STBETO = 1.0;
  STBETL = 0.0;
  STBETW = 0.0;
  STBETLW = 0.0;
  MUEO = 0.5;
  MUEW = 0.0;
  STMUEO = 0.0;
  THEMUO = 1.5;
  STTHEMUO = 1.5;
  CSO = 0.0;
  CSL = 0.0;
  CSLEXP = 1.0;
  CSW = 0.0;
  CSLW = 0.0;
  STCSO = 0.0;
  XCORO = 0.0;
  XCORL = 0.0;
  XCORW = 0.0;
  XCORLW = 0.0;
  STXCORO = 0.0;
  FETAO = 1.0;
  RSW1 = 50.0;
  RSW2 = 0.0;
  STRSO = 1.0;
  RSBO = 0.0;
  RSGO = 0.0;
  THESATO = 0.0;
  THESATL = 0.05;
  THESATLEXP = 1.0;
  THESATW = 0.0;
  THESATLW = 0.0;
  STTHESATO = 1.0;
  STTHESATL = 0.0;
  STTHESATW = 0.0;
  STTHESATLW = 0.0;
  THESATBO = 0.0;
  THESATGO = 0.0;
  AXO = 18.0;
  AXL = 0.4;
  ALPL = 0.0005;
  ALPLEXP = 1.0;
  ALPW = 0.0;
  ALP1L1 = 0.0;
  ALP1LEXP = 0.5;
  ALP1L2 = 0.0;
  ALP1W = 0.0;
  ALP2L1 = 0.0;
  ALP2LEXP = 0.5;
  ALP2L2 = 0.0;
  ALP2W = 0.0;
  VPO = 0.05;
  A1O = 1.0;
  A1L = 0.0;
  A1W = 0.0;
  A2O = 10.0;
  STA2O = 0.0;
  A3O = 1.0;
  A3L = 0.0;
  A3W = 0.0;
  A4O = 0.0;
  A4L = 0.0;
  A4W = 0.0;
  GCOO = 0.0;
  IGINVLW = 0.0;
  IGOVW = 0.0;
  IGOVDW = 0.0;
  STIGO = 2.0;
  GC2O = 0.375;
  GC3O = 0.063;
  CHIBO = 3.1;
  AGIDLW = 0.0;
  AGIDLDW = 0.0;
  BGIDLO = 41.0;
  BGIDLDO = 41.0;
  STBGIDLO = 0.0;
  STBGIDLDO = 0.0;
  CGIDLO = 0.0;
  CGIDLDO = 0.0;
  CGBOVL = 0.0;
  CFRW = 0.0;
  CFRDW = 0.0;
  FNTO = 1.0;
  FNTEXCL = 0.0;
  NFALW = 8e+22;
  NFBLW = 30000000.0;
  NFCLW = 0.0;
  EFO = 1.0;
  LINTNOI = 0.0;
  ALPNOI = 2.0;
  WEDGE = 1e-08;
  WEDGEW = 0.0;
  VFBEDGEO = -1.0;
  STVFBEDGEO = 0.0005;
  STVFBEDGEL = 0.0;
  STVFBEDGEW = 0.0;
  STVFBEDGELW = 0.0;
  DPHIBEDGEO = 0.0;
  DPHIBEDGEL = 0.0;
  DPHIBEDGELEXP = 1.0;
  DPHIBEDGEW = 0.0;
  DPHIBEDGELW = 0.0;
  NSUBEDGEO = 5e+23;
  NSUBEDGEL = 0.0;
  NSUBEDGEW = 0.0;
  NSUBEDGELW = 0.0;
  CTEDGEO = 0.0;
  CTEDGEL = 0.0;
  CTEDGELEXP = 1.0;
  FBETEDGE = 0.0;
  LPEDGE = 1e-08;
  BETEDGEW = 0.0;
  STBETEDGEO = 1.0;
  STBETEDGEL = 0.0;
  STBETEDGEW = 0.0;
  STBETEDGELW = 0.0;
  PSCEEDGEL = 0.0;
  PSCEEDGELEXP = 2.0;
  PSCEEDGEW = 0.0;
  PSCEBEDGEO = 0.0;
  PSCEDEDGEO = 0.0;
  CFEDGEL = 0.0;
  CFEDGELEXP = 2.0;
  CFEDGEW = 0.0;
  CFDEDGEO = 0.0;
  CFBEDGEO = 0.0;
  FNTEDGEO = 1.0;
  NFAEDGELW = 8e+22;
  NFBEDGELW = 30000000.0;
  NFCEDGELW = 0.0;
  EFEDGEO = 1.0;
  KVTHOWEO = 0.0;
  KVTHOWEL = 0.0;
  KVTHOWEW = 0.0;
  KVTHOWELW = 0.0;
  KUOWEO = 0.0;
  KUOWEL = 0.0;
  KUOWEW = 0.0;
  KUOWELW = 0.0;
  RGO = 0.0;
  RINT = 0.0;
  RVPOLY = 0.0;
  RSHG = 0.0;
  DLSIL = 0.0;
  RSH = 0.0;
  RSHD = 0.0;
  RBULKO = 0.0;
  RWELLO = 0.0;
  RJUNSO = 0.0;
  RJUNDO = 0.0;
  SAREF = 1e-06;
  SBREF = 1e-06;
  WLOD = 0.0;
  KUO = 0.0;
  KVSAT = 0.0;
  TKUO = 0.0;
  LKUO = 0.0;
  WKUO = 0.0;
  PKUO = 0.0;
  LLODKUO = 0.0;
  WLODKUO = 0.0;
  KVTHO = 0.0;
  LKVTHO = 0.0;
  WKVTHO = 0.0;
  PKVTHO = 0.0;
  LLODVTH = 0.0;
  WLODVTH = 0.0;
  STETAO = 0.0;
  LODETAO = 1.0;
  SCREF = 1e-06;
  WEB = 0.0;
  WEC = 0.0;
  IMAX = 1000.0;
  TRJ = 21.0;
  FREV = 1000.0;
  CJORBOT = 0.001;
  CJORSTI = 1e-09;
  CJORGAT = 1e-09;
  VBIRBOT = 1.0;
  VBIRSTI = 1.0;
  VBIRGAT = 1.0;
  PBOT = 0.5;
  PSTI = 0.5;
  PGAT = 0.5;
  PHIGBOT = 1.16;
  PHIGSTI = 1.16;
  PHIGGAT = 1.16;
  IDSATRBOT = 1e-12;
  IDSATRSTI = 1e-18;
  IDSATRGAT = 1e-18;
  CSRHBOT = 100.0;
  CSRHSTI = 0.0001;
  CSRHGAT = 0.0001;
  XJUNSTI = 1e-07;
  XJUNGAT = 1e-07;
  CTATBOT = 100.0;
  CTATSTI = 0.0001;
  CTATGAT = 0.0001;
  MEFFTATBOT = 0.25;
  MEFFTATSTI = 0.25;
  MEFFTATGAT = 0.25;
  CBBTBOT = 1e-12;
  CBBTSTI = 1e-18;
  CBBTGAT = 1e-18;
  FBBTRBOT = 1000000000.0;
  FBBTRSTI = 1000000000.0;
  FBBTRGAT = 1000000000.0;
  STFBBTBOT = -0.001;
  STFBBTSTI = -0.001;
  STFBBTGAT = -0.001;
  VBRBOT = 10.0;
  VBRSTI = 10.0;
  VBRGAT = 10.0;
  PBRBOT = 4.0;
  PBRSTI = 4.0;
  PBRGAT = 4.0;
  CJORBOTD = 0.001;
  CJORSTID = 1e-09;
  CJORGATD = 1e-09;
  VBIRBOTD = 1.0;
  VBIRSTID = 1.0;
  VBIRGATD = 1.0;
  PBOTD = 0.5;
  PSTID = 0.5;
  PGATD = 0.5;
  PHIGBOTD = 1.16;
  PHIGSTID = 1.16;
  PHIGGATD = 1.16;
  IDSATRBOTD = 1e-12;
  IDSATRSTID = 1e-18;
  IDSATRGATD = 1e-18;
  CSRHBOTD = 100.0;
  CSRHSTID = 0.0001;
  CSRHGATD = 0.0001;
  XJUNSTID = 1e-07;
  XJUNGATD = 1e-07;
  CTATBOTD = 100.0;
  CTATSTID = 0.0001;
  CTATGATD = 0.0001;
  MEFFTATBOTD = 0.25;
  MEFFTATSTID = 0.25;
  MEFFTATGATD = 0.25;
  CBBTBOTD = 1e-12;
  CBBTSTID = 1e-18;
  CBBTGATD = 1e-18;
  FBBTRBOTD = 1000000000.0;
  FBBTRSTID = 1000000000.0;
  FBBTRGATD = 1000000000.0;
  STFBBTBOTD = -0.001;
  STFBBTSTID = -0.001;
  STFBBTGATD = -0.001;
  VBRBOTD = 10.0;
  VBRSTID = 10.0;
  VBRGATD = 10.0;
  PBRBOTD = 4.0;
  PBRSTID = 4.0;
  PBRGATD = 4.0;
  SWJUNEXP = 0.0;
  VJUNREF = 2.5;
  FJUNQ = 0.03;
  VJUNREFD = 2.5;
  FJUNQD = 0.03;
  setModParams(mb.params);
  { std::string _mt = getType(); for(auto &ch:_mt) ch = tolower(ch);
    if (_mt.find("pmos") != std::string::npos || _mt == "p") TYPE = -1.0;
    else if (_mt.find("nmos") != std::string::npos || _mt == "n") TYPE = 1.0; }
  processParams();
}

Model::~Model() {}
bool Model::processParams() { return true; }
bool Model::processInstanceParams() { return true; }

void Model::forEachInstance(DeviceInstanceOp &op) const {
  for (auto *inst : instanceContainer) op(inst);
}
std::ostream &Model::printOutInstances(std::ostream &os) const {
  return os;
}

Device *Traits::factory(const Configuration &configuration,
                        const FactoryBlock &factory_block) {
  return new DeviceMaster<Traits>(configuration, factory_block,
    factory_block.solverState_, factory_block.deviceOptions_);
}

void registerDevice(const DeviceCountMap &deviceMap,
                    const std::set<int> &levelSet) {
  Config<Traits>::addConfiguration()
    .registerDevice("m", 103)
    .registerModelType("nmos", 103)
    .registerModelType("pmos", 103);
}

} } }  // namespace PYMS_PSP103VA

__attribute__((constructor)) static void pyms_register() {
  Xyce::Device::PYMS_PSP103VA::registerDevice(
    Xyce::Device::DeviceCountMap(), std::set<int>());
}
