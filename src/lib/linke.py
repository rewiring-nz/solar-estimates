############################################################################
#
# MODULE:       linke_by_day.py
#
# AUTHOR(S):    Hamish Bowman, Dunedin, New Zealand
#               Shreyas Rama, Christchurch, New Zealand
#
# PURPOSE:      Interpolate day of year into Linke turbidity value
#
# COPYRIGHT:    (c) 2009 Hamish Bowman, and The GRASS Development Team
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
############################################################################
#
# Requires Numeric module (NumPy) and SciPy from  http://numpy.scipy.org/
#   (older versions only implement linear interpolation & will throw an error)
# Assumes monthly value corresponds to the actual mid-month value

import sys

def _validate_day_arg(day_val):
    try:
        d = float(day_val)
    except Exception:
        raise ValueError("day must be a number")
    if d < 1 or d > 365:
        raise ValueError("day must be within 1..365")
    return d


def linke_by_day(day):
    import numpy
    from scipy import interpolate

    d = _validate_day_arg(day)

    ##### put monthly data here
    # e.g. northern hemisphere mountains:  (from the r.sun help page)
    #    [jan,feb,mar,...,dec]
    linke_data = numpy.array ([2.9, 3.0, 2.8, 2.7, 3.0, 2.8, 2.5, 2.9, 3.3, 2.9, 3.1, 3.1])

    linke_data_wrap = numpy.concatenate((linke_data[9:12],
                                         linke_data,
                                         linke_data[0:3]))
    
    monthDays = numpy.array ([0,31,28,31,30,31,30,31,31,30,31,30,31])
    #init empty
    midmonth_day = numpy.array ([0,0,0,0,0,0,0,0,0,0,0,0])
    for i in range(1, 12+1):
        midmonth_day[i-1] = 15 + sum(monthDays[0:i])
    
    midmonth_day_wrap = numpy.concatenate((midmonth_day[9:12]-365, \
                                           midmonth_day,
                                           midmonth_day[0:3]+365))
    
    linke = interpolate.interp1d(midmonth_day_wrap, 
                                 linke_data_wrap,
                                 kind='cubic')
    # return interpolated value
    return float(linke(d))


if __name__ == "__main__":
    # CLI: accept one argument and print value (preserve original behaviour)
    if len(sys.argv) != 2:
        print("USAGE: g.linke_by_day [day number (1-365)]")
        sys.exit(1)
    try:
        day = float(sys.argv[1])
    except Exception:
        print("USAGE: g.linke_by_day [day number (1-365)]")
        sys.exit(1)
    # call the function (let any ImportError or other exceptions surface)
    val = linke_by_day(day)
    print("%.4f" % val)
