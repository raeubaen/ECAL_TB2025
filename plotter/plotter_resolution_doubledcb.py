import os, json, uproot, argparse, sys, ROOT
import numpy as np
import array
import glob
from math import sqrt
import csv
import scipy.signal as signal_proc


def is_file_ok(fname, branch):
    f = ROOT.TFile.Open(fname)
    if not f or f.IsZombie():
        print(f"  ZOMBIE: {fname}")
        return False
    if f.TestBit(ROOT.TFile.kRecovered):
        print(f"  RECOVERED (potentially corrupt): {fname}")
        f.Close()
        return False
    t = f.Get("tree")
    if not t:
        print(f"  NO TREE: {fname}")
        f.Close()
        return False
    if t.GetBranch(branch) is None:
        print(f"  MISSING BRANCH '{branch}': {fname}")
        f.Close()
        return False
    if t.GetEntries() == 0:
        print(f"  EMPTY TREE: {fname}")
        f.Close()
        return False
    f.Close()
    return True



def cbFitDouble(h, name, Run, energy, gain_ratio, output_dir,
                 mean1_guess, sigma1_guess, mean2_guess, sigma2_guess,
                 xmin=-1, xmax=-1):

    x = ROOT.RooRealVar(f"x_{name}_{Run}", "5x5 crystal charge [ADC]",
                         h.GetXaxis().GetXmin(), h.GetXaxis().GetXmax())

    data = ROOT.RooDataHist(f"data_{name}_{Run}", "data", ROOT.RooArgList(x), h)

    # ---- Peak 1 (secondary, lower charge) ----
    mean1  = ROOT.RooRealVar(f"mean1_{name}", "DCB1 mean", mean1_guess,
                              mean1_guess - 500, mean1_guess + 500)
    sigma1 = ROOT.RooRealVar(f"sigma1_{name}", "DCB1 sigma", sigma1_guess, 0.0001, 2000)
    alphaL1 = ROOT.RooRealVar(f"alphaL1_{name}", "alphaL1", 1.5, 0.1, 5.0)
    nL1     = ROOT.RooRealVar(f"nL1_{name}",     "nL1",     3.0, 0.5, 20.0)
    alphaR1 = ROOT.RooRealVar(f"alphaR1_{name}", "alphaR1", 1.5, 0.1, 5.0)
    nR1     = ROOT.RooRealVar(f"nR1_{name}",     "nR1",     3.0, 0.5, 20.0)
    dcb1 = ROOT.RooCrystalBall(f"dcb1_{name}", "DCB1", x, mean1, sigma1, alphaL1, nL1, alphaR1, nR1)
    nsig1 = ROOT.RooRealVar(f"nsig1_{name}", "yield1", 0.2*h.Integral(), 0.0, h.Integral())

    # ---- Peak 2 (main, higher charge) ----
    mean2  = ROOT.RooRealVar(f"mean2_{name}", "DCB2 mean", mean2_guess,
                              mean2_guess - 500, mean2_guess + 500)
    sigma2 = ROOT.RooRealVar(f"sigma2_{name}", "DCB2 sigma", sigma2_guess, 0.0001, 2000)
    alphaL2 = ROOT.RooRealVar(f"alphaL2_{name}", "alphaL2", 1.5, 0.1, 5.0)
    nL2     = ROOT.RooRealVar(f"nL2_{name}",     "nL2",     3.0, 0.5, 20.0)
    alphaR2 = ROOT.RooRealVar(f"alphaR2_{name}", "alphaR2", 1.5, 0.1, 5.0)
    nR2     = ROOT.RooRealVar(f"nR2_{name}",     "nR2",     3.0, 0.5, 20.0)
    dcb2 = ROOT.RooCrystalBall(f"dcb2_{name}", "DCB2", x, mean2, sigma2, alphaL2, nL2, alphaR2, nR2)
    nsig2 = ROOT.RooRealVar(f"nsig2_{name}", "yield2", 0.8*h.Integral(), 0.0, h.Integral())

    model = ROOT.RooAddPdf(f"model_{name}_{Run}", "double DCB model",
                            ROOT.RooArgList(dcb1, dcb2), ROOT.RooArgList(nsig1, nsig2))

    fitArgs = [
        ROOT.RooFit.Extended(True),
        ROOT.RooFit.Save(),
        ROOT.RooFit.PrintLevel(-1)
    ]

    if xmin >= 0 and xmax >= 0:
        fitArgs.insert(0, ROOT.RooFit.Range("fitRange"))
        x.setRange("fitRange", xmin, xmax)

    result = model.fitTo(data, *fitArgs)

    canvas = ROOT.TCanvas()
    frame = x.frame()
    data.plotOn(frame)

    print("all good2")

    model.plotOn(frame, ROOT.RooFit.Range("fitRange"), ROOT.RooFit.NormRange("fitRange"),
                  ROOT.RooFit.LineColor(ROOT.kBlue))
    model.plotOn(frame, ROOT.RooFit.Components(f"dcb1_{name}"),
                  ROOT.RooFit.Range("fitRange"), ROOT.RooFit.NormRange("fitRange"),
                  ROOT.RooFit.LineStyle(ROOT.kDashed), ROOT.RooFit.LineColor(ROOT.kRed))
    model.plotOn(frame, ROOT.RooFit.Components(f"dcb2_{name}"),
                  ROOT.RooFit.Range("fitRange"), ROOT.RooFit.NormRange("fitRange"),
                  ROOT.RooFit.LineStyle(ROOT.kDashed), ROOT.RooFit.LineColor(ROOT.kGreen+2))

    ROOT.gStyle.SetOptTitle(1)
    frame.SetTitle(f"Run {Run} - double dcb fit of seed crystal charge")
    frame.Draw()

    print("all good3")

    npar = result.floatParsFinal().getSize()
    chi2_ndf = frame.chiSquare(npar)

    pt = ROOT.TPaveText(0.55, 0.55, 0.88, 0.88, "NDC")
    pt.SetFillColor(0)
    pt.SetTextFont(42)
    pt.SetBorderSize(0)
    pt.SetTextSize(0.04)
    pt.AddText(f"#mu_{{1}} = {mean1.getVal():.5g} #pm {mean1.getError():.1g}")
    pt.AddText(f"#sigma_{{1}} = {sigma1.getVal():.4g} #pm {sigma1.getError():.1g}")
    pt.AddText(f"#mu_{{2}} = {mean2.getVal():.5g} #pm {mean2.getError():.1g}")
    pt.AddText(f"#sigma_{{2}} = {sigma2.getVal():.4g} #pm {sigma2.getError():.1g}")
    pt.AddText(f"Resolution = {sigma2.getVal()/mean2.getVal():.5g}")
    pt.AddText(f"#chi^2/Ndf = {chi2_ndf:.3g}")
    pt.AddText(f"Energy = {energy} GeV")
    pt.AddText(f"Gain ratio = {gain_ratio}")
    pt.Draw()

    canvas.Update()
    output_path = os.path.join(output_dir, name)
    canvas.SaveAs(output_path + ".pdf")
    canvas.SaveAs(output_path + ".root")

    return {
        "mean1": (mean1.getVal(), mean1.getError()),
        "sigma1": (sigma1.getVal(), sigma1.getError()),
        "mean2": (mean2.getVal(), mean2.getError()),
        "sigma2": (sigma2.getVal(), sigma2.getError()),
        "chi_squared": chi2_ndf
    }



def main(arguments):

    ROOT.gStyle.SetOptTitle(1)
    ROOT.gStyle.SetTitleAlign(23)
    ROOT.gStyle.SetTitleX(0.5)

    parser = argparse.ArgumentParser(description='')
    parser.add_argument("-i",  f"--input-dir", type=str, required=True, help="input directory containing ROOT file with unpacked tree")
    parser.add_argument("-r", f"--run", type=str, required=True, help="run")
    parser.add_argument("-e", f"--energy", type=str, required=True, help="energy")
    parser.add_argument("-g", f"--gain-ratio", type=str, required=True, help="gain ratio")
    parser.add_argument("-f", f"--fit-output-dir", type=str, required=True, help="directory for fits")

    args = parser.parse_args(arguments)

    input_dir=args.input_dir
    fit_output_dir=args.fit_output_dir
    run=args.run
    energy=args.energy
    gain_ratio=args.gain_ratio
    os.makedirs(fit_output_dir, exist_ok=True)

    ROOT.gStyle.SetTitleSize(0.045, "XYZ")
    c = ROOT.TCanvas()
    c.SetGrid()


    chain = ROOT.TChain("tree")
    pattern = os.path.join(input_dir, f"run_{run}/{run}_*_reco.root")

    good_files = []
    bad_files = []
    for f in glob.glob(pattern):
        if is_file_ok(f, "ecal_charge"):
            chain.Add(f)
            good_files.append(f)
        else:
            bad_files.append(f)

    print(f"Added {len(good_files)} good files, skipped {len(bad_files)} bad files")
    if bad_files:
        print("Skipped files:")
        for f in bad_files:
            print(f"  {f}")

    if chain.GetEntries() == 0:
        print("ERROR: chain is empty, nothing to plot")
        return


    print(f"Run {run}: added {chain.GetNtrees()} files")

    h = ROOT.TH1F(f"Charge_singlecrystal_En-{energy}_GainRatio-{gain_ratio}_doubledcb", "", 500, 0, 30000)

#    Charge_sum_3x3_string = "Sum$(ecal_charge * (abs(ecal_iphi_within_5x5) < 2) * (abs(ecal_ieta_within_5x5) < 2))"

    print("all good000")
#    chain.Draw(f"{Charge_sum_3x3_string}>>Charge_3x3_En-{energy}_GainRatio-{gain_ratio}_doubledcb", "", "goff")
    chain.Draw(f"ecal_charge_seed>>Charge_singlecrystal_En-{energy}_GainRatio-{gain_ratio}_doubledcb", "", "goff")
    print("all good00")
#    ROOT.gDebug = 1
    h.Draw()


#    df_rdf = ROOT.RDataFrame(chain)
#
#    # Define the per-event sum using a C++ lambda via Define
#    df_rdf = df_rdf.Define(
#        "charge_3x3",
#        "double s = 0; "
#        "for (size_t i = 0; i < ecal_charge.size(); i++) { "
#        "  if (abs(ecal_iphi_within_5x5[i]) < 2 && abs(ecal_ieta_within_5x5[i]) < 2) "
#        "    s += ecal_charge[i]; "
#        "} "
#        "return s;"
#    )
#
#    h = df_rdf.Histo1D(
#        ROOT.RDF.TH1DModel(f"Charge_3x3_En-{energy}_GainRatio-{gain_ratio}", "", 500, 0, 30000),
#        "charge_3x3"
#    )
#
#    h = h.GetValue()


    print("all good0")

    nbins = h.GetNbinsX()
    counts = np.array([h.GetBinContent(i) for i in range(1, nbins+1)])
    centers = np.array([h.GetBinCenter(i) for i in range(1, nbins+1)])

    peaks, _ = signal_proc.find_peaks(counts, prominence=counts.max()*0.1, distance=10)
    peaks_sorted = sorted(peaks, key=lambda p: centers[p])

    if len(peaks_sorted) < 2:
        print("WARNING: found fewer than 2 peaks, falling back to single peak")
        mean1_guess = mean2_guess = centers[peaks_sorted[0]]
        sigma1_guess = sigma2_guess = h.GetRMS()
    else:
        mean1_guess = centers[peaks_sorted[0]]   # secondary (lower charge)
        mean2_guess = centers[peaks_sorted[-1]]  # main (higher charge)
        sigma1_guess = (mean2_guess - mean1_guess) * 0.1
        sigma2_guess = (mean2_guess - mean1_guess) * 0.1

    # fit range covers both peaks
    fit_min = mean1_guess - 3*sigma1_guess
    fit_max = mean2_guess + 3*sigma2_guess

    print("all good")
    results = cbFitDouble(h, h.GetName(), run, energy, gain_ratio, fit_output_dir,
                           mean1_guess, sigma1_guess, mean2_guess, sigma2_guess,
                           fit_min, fit_max)

    mu_val, emu_val = results["mean2"]
    sig_val, esig_val = results["sigma2"]
    chi2 = results["chi_squared"]
    charge_ratio = results["mean2"] / results["mean1"]

    resolution = sig_val/mu_val
    resolution_error = sqrt((esig_val/mu_val)**2 + emu_val**2*(sig_val/mu_val**2)**2 + (5e-4)**2)

    print(f"RESULT {resolution} {resolution_error} {chi2} {charge_ratio}")

if __name__ == "__main__":
    main(sys.argv[1:])



















