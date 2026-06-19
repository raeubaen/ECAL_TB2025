import os,json,uproot,argparse,sys,ROOT
import numpy as np
import array
import glob
from math import sqrt
import csv

def has_branch(fname, branch):
    f = ROOT.TFile.Open(fname)
    if not f or f.IsZombie():
        return False
    t = f.Get("tree")
    if not t:
        return False

    return t.GetBranchStatus(branch)

def make_fit_box(fit, x1, y1, x2, y2, color, label):

    p0    = fit.GetParameter(0)
    p1    = fit.GetParameter(1)
    p2    = fit.GetParameter(2)
    chi2  = fit.GetChisquare()
    ndf   = fit.GetNDF()
    p0e   = fit.GetParError(0)
    p1e   = fit.GetParError(1)
    p2e   = fit.GetParError(2)

    box = ROOT.TPaveText(x1, y1, x2, y2, "NDC")
    box.SetFillColor(0)
    box.SetBorderSize(1)
    box.SetTextColor(color)
    box.SetTextSize(0.025)
    box.AddText(label)
    box.AddText(f"N = {p0/100:.7f} #pm {p0e/100:.7f}")
    box.AddText(f"S = {p1/100:.7f} #pm {p1e/100:.7f}")
    box.AddText(f"C = {p2/100:.7f} #pm {p2e/100:.7f}")
    box.AddText(f"#chi^{{2}}/ndf = {chi2:.2f}/{ndf}")
    return box


def cbFit(h,name,Run,energy,output_dir,xmin=-1,xmax=-1):

    x = ROOT.RooRealVar(f"x_{name}_{Run}", "FitAmp [ADC]", h.GetXaxis().GetXmin(), h.GetXaxis().GetXmax())

    data = ROOT.RooDataHist(f"data_{name}_{Run}", "data", ROOT.RooArgList(x), h)

    peak = h.GetBinCenter(h.GetMaximumBin())

    mean  = ROOT.RooRealVar(f"mean_{name}", "DCB mean",peak,peak-500,peak+500)

    sigma = ROOT.RooRealVar(f"sigma_{name}", "DCB sigma",h.GetRMS(),0.0001,1000)

    alphaL = ROOT.RooRealVar(f"alphaL_{name}", "alphaL", 1.5, 0.1, 5.0)
    nL     = ROOT.RooRealVar(f"nL_{name}",     "nL",     3.0, 0.5, 20.0)

    alphaR = ROOT.RooRealVar(f"alphaR_{name}", "alphaR", 1.5, 0.1, 5.0)
    nR     = ROOT.RooRealVar(f"nR_{name}",     "nR",     3.0, 0.5, 20.0)

    dcb = ROOT.RooCrystalBall(f"dcb_{name}", "Double Crystal Ball",x,mean,sigma,alphaL, nL,alphaR, nR)

    nsig = ROOT.RooRealVar(f"nsig_{name}", "signal yield",h.Integral(),0.0,10.0*h.Integral())
    model = ROOT.RooAddPdf(f"model_{name}_{Run}", "extended DCB model",ROOT.RooArgList(dcb),ROOT.RooArgList(nsig))

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
    model.plotOn(frame, ROOT.RooFit.Range("fitRange"),ROOT.RooFit.NormRange("fitRange"))

    ROOT.gStyle.SetOptTitle(1)
    frame.SetTitle(f"Run {Run} - dcb fit of fitamp 3x3")
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
    pt.AddText(f"Resolution = {sigma.getVal()/mean.getVal():.2g}" )
    pt.AddText(f"#chi^2/Ndf = {chi2_ndf:.3g}" )
    pt.AddText(f"Energy = {energy:.3g} GeV" )

    pt.Draw()

    canvas.Update()

    filename = f"{name}_fit_dcb"
    output_path = os.path.join(output_dir, filename)
    canvas.SaveAs(output_path + ".pdf")
    canvas.SaveAs(output_path + ".root")

    return {
        "mean": (mean.getVal(), mean.getError()),
        "sigma": (sigma.getVal(), sigma.getError())
    }



def main(arguments):

    parser = argparse.ArgumentParser(description='')
    parser.add_argument("-i",  f"--input-dir", type=str, required=True, help="input directory containing ROOT file with unpacked tree")
    parser.add_argument("-ro", f"--plot-output-dir", type=str, required=True, help="directory for output plots")
    parser.add_argument("-f", f"--fit-output-dir", type=str, required=True, help="directory for fits")
    parser.add_argument("-j", f"--run-info-json", type=str, required=False, help="run and energy sample")

    args = parser.parse_args(arguments)

    json_dict = json.load(open(args.run_info_json, "r"))
    input_dir=args.input_dir
    plot_output_dir=args.plot_output_dir
    fit_output_dir=args.fit_output_dir
    os.makedirs(plot_output_dir, exist_ok=True)
    os.makedirs(fit_output_dir, exist_ok=True)

    dd = json_dict["global"]["run info"]

    Run, Ebins, Channels3x3, Channels5x5, do_fitamp, do_channel_matrix_3x3 = [dd[k] for k in ["run list", "run energies", "3x3 channels", "5x5 channels", "do fitamp", "do matrix 3x3"]]
    roofit_objects, rows_resolution = [],[]
    intercalib_dict = {}

    lin = ROOT.TGraphErrors(len(Ebins))
    res = ROOT.TGraphErrors(len(Ebins))
    rescal = ROOT.TGraphErrors(len(Ebins))

    ROOT.gStyle.SetTitleSize(0.045, "XYZ")

    with open("intercalibration_info_fixed.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ch = int(row["seed_channel"])
            ic = float(row["intercalibrationfactor"])
            intercalib_dict[ch] = ic

    for ie in range(len(Ebins)):

        c = ROOT.TCanvas()
        c.SetGrid()

        run = Run[ie]
        energy = Ebins[ie]

        chain = ROOT.TChain("tree")

        pattern = os.path.join(input_dir, f"run_{run}/{run}_*_reco.root") 

        for f in glob.glob(pattern): 
            if has_branch(f, "ecal_lsfit_amp"): 
                chain.Add(f)
            else:
                print("Skipping:", f) 

        print(f"Run {run}: added {chain.GetNtrees()} files")


        if do_fitamp:

            if do_channel_matrix_3x3:

              h = ROOT.TH1F(f"FitAmp_3x3_{run}_uncalibrated", "", 1000, 0, 15000)
#              FitAmp_sum_3x3_string = "+".join([f"ecal_lsfit_amp[{ch}]" for ch in Channels3x3])
              FitAmp_sum_5x5_string = "Sum$(ecal_lsfit_amp * (abs(ecal_iphi_within_5x5) < 3) * (abs(ecal_ieta_within_5x5) < 3))"

              print("allgood1")
              FitAmp_sum_3x3_string_withmask = f"Sum$(ecal_lsfit_amp * (abs(ecal_iphi_within_5x5) < 2) * (abs(ecal_ieta_within_5x5) < 2))"
              print("allgood2")
              mask_charge = ecal_lsfit_amp[ecal_seed_ch] > 0.7 * {FitAmp_sum_5x5_string}
              chain.Draw(f"{FitAmp_sum_3x3_string_withmask}>>FitAmp_3x3_{run}_uncalibrated", mask_charge, "goff")

              hc = ROOT.TH1F(f"FitAmp_3x3_{run}_calibrated", "", 1000, 0, 15000)
#              FitAmp_sum_3x3_string_cal = "+".join([f"ecal_lsfit_amp[{ch}] / {intercalib_dict[ch]}" for ch in Channels3x3])
              print("allgood3")
              FitAmp_sum_3x3_string_cal_withmask = f"Sum$(ecal_lsfit_amp * (abs(ecal_iphi_within_5x5) < 2) * (abs(ecal_ieta_within_5x5) < 2) * (ecal_lsfit_amp[ecal_seed_ch] / {FitAmp_sum_5x5_string} > 0.7))"
              print("allgood4")
              chain.Draw(f"{FitAmp_sum_3x3_string_cal_withmask}>>FitAmp_3x3_{run}_calibrated", "", "goff")

            else:

              h = ROOT.TH1F(f"FitAmp_5x5_{run}_uncalibrated", "", 1000, 0, 15000)
#              FitAmp_sum_3x3_string = "+".join([f"ecal_lsfit_amp[{ch}]" for ch in Channels3x3])
              FitAmp_sum_5x5_string = "+".join([f"ecal_lsfit_amp[{ch}]" for ch in Channels5x5])
              chain.Draw(f"{FitAmp_sum_5x5_string}>>FitAmp_5x5_{run}_uncalibrated", "", "goff")

              hc = ROOT.TH1F(f"FitAmp_5x5_{run}_calibrated", "", 1000, 0, 15000)
              FitAmp_sum_5x5_string_cal = "+".join([f"ecal_lsfit_amp[{ch}] / {intercalib_dict[ch]}" for ch in Channels5x5])
              chain.Draw(f"{FitAmp_sum_5x5_string_cal}>>FitAmp_5x5_{run}_calibrated", "", "goff")

        else:

            if do_channel_matrix_3x3:

              h = ROOT.TH1F(f"Charge_3x3_{run}_uncalibrated", "", 1000, 0, 50000)
              Charge_sum_3x3_string = "+".join([f"ecal_charge[{ch}]" for ch in Channels3x3])
              chain.Draw(f"{Charge_sum_3x3_string}>>Charge_3x3_{run}_uncalibrated", "", "goff")

              hc = ROOT.TH1F(f"Charge_3x3_{run}_calibrated", "", 1000, 0, 50000)
              Charge_sum_3x3_string_cal = "+".join([f"ecal_charge[{ch}] / {intercalib_dict[ch]}" for ch in Channels3x3])
              chain.Draw(f"{Charge_sum_3x3_string_cal}>>Charge_3x3_{run}_calibrated", "", "goff")

            else:

              h = ROOT.TH1F(f"Charge_5x5_{run}_uncalibrated", "", 1000, 0, 50000)
              chain.Draw(f"ecal_charge_sum_5x5>>Charge_5x5_{run}_uncalibrated", "", "goff")

              hc = ROOT.TH1F(f"Charge_5x5_{run}_calibrated", "", 1000, 0, 50000)
              Charge_sum_5x5_string_cal = "+".join([f"ecal_charge[{ch}] / {intercalib_dict[ch]}" for ch in Channels5x5])
              chain.Draw(f"{Charge_sum_5x5_string_cal}>>Charge_5x5_{run}_calibrated", "", "goff")


        h.Draw()
        hc.Draw()

#####   uncalibrated histo

        max_bin = h.GetMaximumBin()
        max_position = h.GetBinCenter(max_bin)
        max_value = h.GetBinContent(max_bin)
        bin1 = h.FindFirstBinAbove(max_value/2)
        bin2 = h.FindLastBinAbove(max_value/2)
        fwhm = h.GetBinCenter(bin2) - h.GetBinCenter(bin1)

        min = max_position - 2.5*fwhm
        max = max_position + 2*fwhm

        results = cbFit(h,h.GetName(),run,energy,fit_output_dir,min,max)
        mu_val, emu_val = results["mean"]
        sig_val, esig_val = results["sigma"]

######  calibrated histo

        max_binc = hc.GetMaximumBin()
        max_positionc = hc.GetBinCenter(max_binc)
        max_valuec = hc.GetBinContent(max_binc)
        bin1c = hc.FindFirstBinAbove(max_valuec/2)
        bin2c = hc.FindLastBinAbove(max_valuec/2)
        fwhmc = hc.GetBinCenter(bin2c) - hc.GetBinCenter(bin1c)

        minc = max_positionc - 2.5*fwhmc
        maxc = max_positionc + 2*fwhmc

        print("all good")
        resultsc = cbFit(hc,hc.GetName(),run,energy,fit_output_dir,minc,maxc)
        mu_valc, emu_valc = resultsc["mean"]
        sig_valc, esig_valc = resultsc["sigma"]

#####   filling the plots

        resolution_error = sqrt((esig_val/mu_val)**2+emu_val**2*(sig_val/mu_val**2)**2+(5e-4)**2)
        resolution_errorc = sqrt((esig_valc/mu_valc)**2+emu_valc**2*(sig_valc/mu_valc**2)**2+(5e-4)**2)

        #print("Energy/Mean/eMean/Sigma/eSigma")
        #print(energy,mu_val,emu_val,sig_val,esig_val)

        lin.SetPoint(ie, mu_val, energy)                  #energy linearity
        lin.SetPointError(ie,emu_val,energy*0.025)

        res.SetPoint(ie,energy,100*(sig_val/mu_val))      #resolution vs beam energy
        res.SetPointError(ie,0,100*resolution_error)

        rescal.SetPoint(ie,energy,100*(sig_valc/mu_valc)) #calibrated resolution vs beam energy
        rescal.SetPointError(ie,0,100*resolution_errorc)

        rows_resolution.append({
            "run": run,
            "energy": energy,
            "resolution_uncalib": 100*(sig_val/mu_val),
            "resolution_uncalib_err": 100*resolution_error,
            "resolution_calib": 100*(sig_valc/mu_valc),
            "resolution_calib_err": 100*resolution_errorc,
        })

#####

    #saving data
    with open("resolution_points.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["run", "energy", "resolution_uncalib", "resolution_uncalib_err",
                         "resolution_calib", "resolution_calib_err"])
        for row in rows_resolution:
            writer.writerow([
                row["run"],
                row["energy"],
                f"{row['resolution_uncalib']:.5f}",
                f"{row['resolution_uncalib_err']:.5f}",
                f"{row['resolution_calib']:.5f}",
                f"{row['resolution_calib_err']:.5f}",
            ])

    canvas = ROOT.TCanvas()
    canvas.SetGrid()

    lin.SetMarkerStyle(24)
    lin.SetMarkerSize(0.8)
    lin.SetMarkerColor(ROOT.kBlack)
    res.SetMarkerStyle(22)
    res.SetMarkerSize(1.4)
    res.SetMarkerColor(ROOT.kBlue)
    rescal.SetMarkerStyle(33)
    rescal.SetMarkerSize(1.4)
    rescal.SetMarkerColor(ROOT.kGreen+2)
    ROOT.gStyle.SetOptTitle(1)
    ROOT.gStyle.SetTitleAlign(23)
    ROOT.gStyle.SetTitleX(0.5)

#####    saving linearity plot

    if do_fitamp:
      if do_channel_matrix_3x3:
        lin.SetTitle(f"Energy linearity ;#Mu_{{fitAmp_3x3}} [ADC];Beam energy [GeV]")
      else:
        lin.SetTitle(f"Energy linearity ;#Mu_{{fitAmp_5x5}} [ADC];Beam energy [GeV]")

    else:
      if do_channel_matrix_3x3:
        lin.SetTitle(f"Energy linearity ;#Mu_{{charge_3x3}} [ADC];Beam energy [GeV]")
      else:
        lin.SetTitle(f"Energy linearity ;#Mu_{{charge_5x5}} [ADC];Beam energy [GeV]")

    lin.Draw("AP")
    canvas.Update()

    filename_lin = f"Energy_linearity"
    output_path_lin = os.path.join(plot_output_dir, filename_lin)
    canvas.SaveAs(output_path_lin + ".pdf")
    canvas.SaveAs(output_path_lin + ".root")
    canvas.Clear()

#####    saving resolution plot

    if do_fitamp:
      if do_channel_matrix_3x3:
        res.SetTitle(f"Resolution 3x3 ;Beam energy [GeV];(#sigma/#mu)_{{fitAmp_3x3}} %")
      else:
        res.SetTitle(f"Resolution 5x5 ;Beam energy [GeV];(#sigma/#mu)_{{fitAmp_5x5}} %")

    else:
      if do_channel_matrix_3x3:
        res.SetTitle(f"Resolution 3x3 ;Beam energy [GeV];(#sigma/#mu)_{{charge_3x3}} %")
      else:
        res.SetTitle(f"Resolution 5x5 ;Beam energy [GeV];(#sigma/#mu)_{{charge_5x5}} %")

    ROOT.gStyle.SetOptFit(0)
    ROOT.gStyle.SetOptStat(0)
    res.Draw("AP")

    fit = ROOT.TF1("fit", "sqrt(([0]/x)**2 + ([1]/sqrt(x))**2 + [2]**2 )", 0, 250)
    fit.SetParLimits(0, 0, 70)
    #fit.FixParameter(0, 0.3)
    fit.SetParLimits(1, 0, 1)
    fit.SetParLimits(2, 0, 10)
    fit.SetLineColor(ROOT.kRed)
    fit_result = res.Fit(fit, "RS")

    p0    = fit.GetParameter(0)
    p0e   = fit.GetParError(0)
    p1    = fit.GetParameter(1)
    p1e   = fit.GetParError(1)
    p2    = fit.GetParameter(2)
    p2e   = fit.GetParError(2)
    chi2  = fit.GetChisquare()
    ndf   = fit.GetNDF()

    leg = ROOT.TLegend(0.15, 0.60, 0.60, 0.88)
    leg.SetBorderSize(1)
    leg.SetFillColor(0)
    leg.SetTextSize(0.032)
    if do_channel_matrix_3x3:
      leg.AddEntry(res, "Ecal 3x3", "lep")
    else:
      leg.AddEntry(res, "Ecal 5x5", "lep")
    leg.AddEntry(fit, "#sqrt{(N/E)^{2} + (S/#sqrt{E})^{2} + C^{2}}", "l")
    leg.AddEntry(ROOT.nullptr, f"N = ({p0/100:.4f} #pm {p0e/100:.4f}) GeV", "")
    leg.AddEntry(ROOT.nullptr, f"S = ({p1/100:.6f} #pm {p1e/100:.6f}) GeV^{{1/2}}", "")
    leg.AddEntry(ROOT.nullptr, f"C = {p2/100:.8f} #pm {p2e/100:.8f} ", "")
    leg.AddEntry(ROOT.nullptr, f"#chi^{{2}} / ndf = {chi2:.2f} / {ndf}", "")
    leg.Draw()

    status = fit_result.Status()
    covstatus = fit_result.CovMatrixStatus()
    print(f"Fit status: {status} (0=converged)")
    print(f"Covariance matrix status: {covstatus} (3=accurate)")

    if status != 0:
        print("WARNING: fit did not converge!")
    if covstatus != 3:
        print("WARNING: covariance matrix not accurate!")

    filename_res = f"Resolution_uncalib"
    output_path_res = os.path.join(plot_output_dir, filename_res)
    canvas.SaveAs(output_path_res + ".pdf")
    canvas.SaveAs(output_path_res + ".root")
    canvas.Clear()

#####    saving post-calib resolution plot

    if do_fitamp:
      if do_channel_matrix_3x3:
        rescal.SetTitle(f"Resolution 3x3 after calib;Beam energy [GeV];(#sigma/#mu)_{{fitAmp_3x3}} %")
      else:
        rescal.SetTitle(f"Resolution 5x5 after calib;Beam energy [GeV];(#sigma/#mu)_{{fitAmp_5x5}} %")

    else:
      if do_channel_matrix_3x3:
        rescal.SetTitle(f"Resolution 3x3 after calib;Beam energy [GeV];(#sigma/#mu)_{{charge_3x3}} %")
      else:
        rescal.SetTitle(f"Resolution 5x5 after calib;Beam energy [GeV];(#sigma/#mu)_{{charge_5x5}} %")

    rescal.Draw("AP")

    fitc = ROOT.TF1("fitcal", "sqrt(([0]/x)**2 + ([1]/sqrt(x))**2 + [2]**2 )", 0, 250)
    fitc.SetParLimits(0, 0, 70)
    #fitc.FixParameter(0, 0.3)
    fitc.SetParLimits(1, 0, 1)
    fitc.SetParLimits(2, 0, 10)
    fitc.SetLineColor(ROOT.kOrange)
    fit_resultc = rescal.Fit(fitc, "RS")

    p0    = fitc.GetParameter(0)
    p0e   = fitc.GetParError(0)
    p1    = fitc.GetParameter(1)
    p1e   = fitc.GetParError(1)
    p2    = fitc.GetParameter(2)
    p2e   = fitc.GetParError(2)
    chi2  = fitc.GetChisquare()
    ndf   = fitc.GetNDF()

    leg = ROOT.TLegend(0.15, 0.60, 0.60, 0.88)
    leg.SetBorderSize(1)
    leg.SetFillColor(0)
    leg.SetTextSize(0.032)
    if do_channel_matrix_3x3:
      leg.AddEntry(rescal, "Ecal 3x3", "lep")
    else:
      leg.AddEntry(rescal, "Ecal 5x5", "lep")
    leg.AddEntry(fitc, "#sqrt{(N/E)^{2} + (S/#sqrt{E})^{2} + C^{2}}", "l")
    leg.AddEntry(ROOT.nullptr, f"N = ({p0/100:.4f} #pm {p0e/100:.4f}) GeV", "")
    leg.AddEntry(ROOT.nullptr, f"S = ({p1/100:.4f} #pm {p1e/100:.4f}) GeV^{{1/2}}", "")
    leg.AddEntry(ROOT.nullptr, f"C = {p2/100:.5f} #pm {p2e/100:.5f} ", "")
    leg.AddEntry(ROOT.nullptr, f"#chi^{{2}} / ndf = {chi2:.2f} / {ndf}", "")
    leg.Draw()

    status = fit_resultc.Status()
    covstatus = fit_resultc.CovMatrixStatus()
    print(f"Fit status: {status} (0=converged)")
    print(f"Covariance matrix status: {covstatus} (3=accurate)")

    if status != 0:
        print("WARNING: fit did not converge!")
    if covstatus != 3:
        print("WARNING: covariance matrix not accurate!")

    filename_rescal = f"Resolution_calib"
    output_path_rescal = os.path.join(plot_output_dir, filename_rescal)
    canvas.SaveAs(output_path_rescal + ".pdf")
    canvas.SaveAs(output_path_rescal + ".root")
    canvas.Clear()

####    saving resolution both pre and after calib

    res.SetTitle(f"Resolution 3x3 with seed gain ratio (pre/post=3/7, baseline=8);Beam energy [GeV];(#sigma/#mu)_{{fitAmp_3x3}} %")

    if do_fitamp:
      if do_channel_matrix_3x3:
        rescal.SetTitle(f"Resolution 3x3 before/after calib;Beam energy [GeV];(#sigma/#mu)_{{fitAmp_3x3}} %")
      else:
        rescal.SetTitle(f"Resolution 5x5 before/after calib;Beam energy [GeV];(#sigma/#mu)_{{fitAmp_5x5}} %")

    else:
      if do_channel_matrix_3x3:
        rescal.SetTitle(f"Resolution 3x3 before/after calib;Beam energy [GeV];(#sigma/#mu)_{{charge_3x3}} %")
      else:
        rescal.SetTitle(f"Resolution 5x5 before/after calib;Beam energy [GeV];(#sigma/#mu)_{{charge_5x5}} %")

    res.Draw("AP")
    fit.Draw("SAME")
    rescal.Draw("P SAME")
    fitc.Draw("SAME")

#legends each with fit info
    box1 = make_fit_box(fit,  0.50, 0.72, 0.88, 0.88, ROOT.kRed,  "Pre-cal fit")
    box2 = make_fit_box(fitc, 0.50, 0.54, 0.88, 0.70, ROOT.kOrange,   "Post-cal fit")
    box1.Draw()
    box2.Draw()
    leg_both = ROOT.TLegend(0.15, 0.75, 0.45, 0.88)
    leg_both.AddEntry(res, "Pre-calibration", "lep")
    leg_both.AddEntry(rescal, "Post-calibration", "lep")
    leg_both.Draw()


    filename_resboth = f"Resolution_prepostcalib"
    output_path_resboth = os.path.join(plot_output_dir, filename_resboth) 
    canvas.SaveAs(output_path_resboth + ".pdf")
    canvas.SaveAs(output_path_resboth + ".root")

    input("finito")

if __name__ == "__main__":
    main(sys.argv[1:])
