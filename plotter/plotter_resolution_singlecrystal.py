import os, json, uproot, argparse, sys, ROOT
import numpy as np
import array
import glob
from math import sqrt
import csv


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

def cbFit(h, name, Run, energy, gain_ratio, output_dir, xmin=-1, xmax=-1):

    x = ROOT.RooRealVar(f"x_{name}_{Run}", "Seed crystal charge [ADC]", h.GetXaxis().GetXmin(), h.GetXaxis().GetXmax())

    data = ROOT.RooDataHist(f"data_{name}_{Run}", "data", ROOT.RooArgList(x), h)

    peak = h.GetBinCenter(h.GetMaximumBin())

    mean  = ROOT.RooRealVar(f"mean_{name}", "DCB mean", peak, peak-500, peak+500)

    sigma = ROOT.RooRealVar(f"sigma_{name}", "DCB sigma", h.GetRMS(), 0.0001, 1000)

    alphaL = ROOT.RooRealVar(f"alphaL_{name}", "alphaL", 1.5, 0.1, 5.0)
    nL     = ROOT.RooRealVar(f"nL_{name}",     "nL",     3.0, 0.5, 20.0)

    alphaR = ROOT.RooRealVar(f"alphaR_{name}", "alphaR", 1.5, 0.1, 5.0)
    nR     = ROOT.RooRealVar(f"nR_{name}",     "nR",     3.0, 0.5, 20.0)

    dcb = ROOT.RooCrystalBall(f"dcb_{name}", "Double Crystal Ball", x, mean, sigma, alphaL, nL, alphaR, nR)

    nsig = ROOT.RooRealVar(f"nsig_{name}", "signal yield", h.Integral(), 0.0, 10.0*h.Integral())
    model = ROOT.RooAddPdf(f"model_{name}_{Run}", "extended DCB model", ROOT.RooArgList(dcb), ROOT.RooArgList(nsig))

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
    model.plotOn(frame, ROOT.RooFit.Range("fitRange"), ROOT.RooFit.NormRange("fitRange"))

    ROOT.gStyle.SetOptTitle(1)
    frame.SetTitle(f"Run {Run} - dcb fit of seed crystal charge")
    frame.Draw()

    npar = result.floatParsFinal().getSize()
    chi2_ndf = frame.chiSquare(npar)

    pt = ROOT.TPaveText(0.60, 0.65, 0.88, 0.88, "NDC")
    pt.SetFillColor(0)
    pt.SetTextFont(42)
    pt.SetBorderSize(0)
    pt.SetTextSize(0.05)

    pt.AddText(f"#mu = {mean.getVal():.5g} #pm {mean.getError():.1g}")
    pt.AddText(f"#sigma = {sigma.getVal():.4g} #pm {sigma.getError():.1g}")
    pt.AddText(f"Resolution = {sigma.getVal()/mean.getVal():.5g}" )
    pt.AddText(f"#chi^2/Ndf = {chi2_ndf:.3g}" )
    pt.AddText(f"Energy = {energy} GeV" )
    pt.AddText(f"Gain ratio = {gain_ratio}" )

    pt.Draw()

    canvas.Update()

    filename = f"{name}"
    output_path = os.path.join(output_dir, filename)
    canvas.SaveAs(output_path + ".pdf")
    canvas.SaveAs(output_path + ".root")

    return {
        "mean": (mean.getVal(), mean.getError()),
        "sigma": (sigma.getVal(), sigma.getError()),
        "chi_squared": chi2_ndf
    }


def main(arguments):

    ROOT.gStyle.SetOptTitle(1)
    ROOT.gStyle.SetTitleAlign(23)
    ROOT.gStyle.SetTitleX(0.5)

    parser = argparse.ArgumentParser(description='')
    parser.add_argument("-i",  f"--input-dir", type=str, required=True, help="input directory containing ROOT file with unpacked tree")
    parser.add_argument("-z", f"--plot-output-dir", type=str, required=True, help="directory for output plots")
    parser.add_argument("-r", f"--run", type=str, required=True, help="run")
    parser.add_argument("-e", f"--energy", type=str, required=True, help="energy")
    parser.add_argument("-g", f"--gain-ratio", type=str, required=True, help="gain ratio")
    parser.add_argument("-f", f"--fit-output-dir", type=str, required=True, help="directory for fits")

    args = parser.parse_args(arguments)

    input_dir=args.input_dir
    plot_output_dir=args.plot_output_dir
    fit_output_dir=args.fit_output_dir
    run=args.run
    energy=args.energy
    gain_ratio=args.gain_ratio
    os.makedirs(plot_output_dir, exist_ok=True)
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

    h = ROOT.TH1F(f"Charge_3x3_En-{energy}_GainRatio-{gain_ratio}", "", 500, 0, 30000)

    Charge_sum_3x3_string = "Sum$(ecal_charge * (abs(ecal_iphi_within_5x5) < 2) * (abs(ecal_ieta_within_5x5) < 2))"
    chain.Draw(f"{Charge_sum_3x3_string}>>Charge_3x3_En-{energy}_GainRatio-{gain_ratio}", "", "goff")
#    chain.Draw(f"ecal_charge_seed>>Charge_singlecrystal_En-{energy}_GainRatio-{gain_ratio}", "", "goff")
    ROOT.gDebug = 1
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


    max_bin = h.GetMaximumBin()
    max_position = h.GetBinCenter(max_bin)
    max_value = h.GetBinContent(max_bin)
    bin1 = h.FindFirstBinAbove(max_value/2)
    bin2 = h.FindLastBinAbove(max_value/2)
    fwhm = h.GetBinCenter(bin2) - h.GetBinCenter(bin1)

    min = max_position - 2.5*fwhm
    max = max_position + 2*fwhm

    results = cbFit(h, h.GetName(), run, energy, gain_ratio, fit_output_dir, min, max)
    mu_val, emu_val = results["mean"]
    sig_val, esig_val = results["sigma"]
    chi2 = results["chi_squared"]

    resolution = sig_val/mu_val
    resolution_error = sqrt((esig_val/mu_val)**2+emu_val**2*(sig_val/mu_val**2)**2+(5e-4)**2)

#    print(f"Run {run} and energy {energy} GeV")
#    print("Mu:", mu_val, "eMu:", emu_val, "Sigma:", sig_val, "eSigma:", esig_val, "Res:", resolution, "eRes:", resolution_error)

    print(f"RESULT {resolution} {resolution_error} {chi2}")


if __name__ == "__main__":
    main(sys.argv[1:])
