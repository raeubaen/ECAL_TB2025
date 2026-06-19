import ROOT
import numpy as np
import array
import glob
from math import sqrt
import csv
import matplotlib.pyplot as plt
import pandas as pd
import mplhep as hep
hep.style.use(hep.style.CMS)

def main():

#    df = pd.read_csv("resgainratios_3x3scan.csv")
#
#    plt.figure(figsize=(10, 7))
##    plt.plot(df['gain_ratio'].values, df['resolution'].values*100, marker='o', linestyle='', color='b')
#
#    df['resolution_error_corr'] = np.sqrt(df['resolution_error']**2 - 0.0005**2)
##    plt.scatter(df['gain_ratio'].values,df['chi_squared'].values)
#    plt.errorbar(df['gain_ratio'].values,df['resolution'].values*100,df['resolution_error_corr'].values*100, marker='o', linestyle='')
#
#
##    plt.xlim(9,10.8)
##    plt.ylim(0,14)
#    plt.xlabel('Gain ratio')
#    plt.ylabel(r'$(\sigma/\mu)_{3x3charge}$ %')
##    plt.ylabel(r'$\chi^2$')
##    plt.title(r'$\chi^2$ variation with gain ratio - large scan')
#
#    plt.savefig('/eos/user/l/lfaiella/www/h4dqm/ECAL_TB_2026_latestDQM/GainRatio/ResPlots/ResvsGainRatio_3x3scan.pdf')

    df = pd.read_csv("resgainratios_3x3scan_definitive.csv")
    plt.figure(figsize=(10, 7))

    df['resolution_error_corr'] = np.sqrt(df['resolution_error']**2 - 0.0005**2)

    x = df['gain_ratio'].values
    y = df['resolution'].values * 100
    yerr = df['resolution_error_corr'].values * 100

    fit_range_min, fit_range_max = 9.9, 10.2
    mask = (x >= fit_range_min) & (x <= fit_range_max)\

    # weighted pol2 fit (weights = 1/sigma)
    coeffs, cov = np.polyfit(x[mask], y[mask], 2, w=(1/yerr)[mask], cov=True)
    p = np.poly1d(coeffs)

    # smooth curve for plotting
    x_fit = np.linspace(fit_range_min, fit_range_max, 200)
    y_fit = p(x_fit)

    plt.errorbar(x[mask], y[mask], yerr[mask], marker='o', linestyle='', color='b', capsize=3, label='Data')
    plt.plot(x_fit, y_fit, 'r-', label='pol2 fit')
    plt.title('Resolution vs gain ratio')

    # find minimum of the parabola
    a, b, c = coeffs
    x_min = -b / (2*a)
    y_min = p(x_min)
    plt.plot(x_min, y_min, 'g*', markersize=15, label=f'Min at x={x_min:.4f}')

    errors = np.sqrt(np.diag(cov))
    print(f"a = {a:.5g} ± {errors[0]:.2g}")
    print(f"b = {b:.5g} ± {errors[1]:.2g}")
    print(f"c = {c:.5g} ± {errors[2]:.2g}")
    print(f"Minimum at gain_ratio = {x_min:.5f}")

    plt.xlabel('Gain ratio')
    plt.ylabel(r'$(\sigma/\mu)_{3x3charge}$ %')
    plt.legend()
    plt.savefig('/eos/user/l/lfaiella/www/h4dqm/ECAL_TB_2026_latestDQM/GainRatio/ResPlots/ResvsGainRatio_3x3scan.pdf')



main()
