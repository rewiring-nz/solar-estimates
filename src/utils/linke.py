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
        d = int(day_val)
    except (ValueError, TypeError):
        raise ValueError("🚫 day must be an integer")

    if d < 1 or d > 365:
        raise ValueError("🚫 day must be within 1..365")

    return d


def linke_by_day(day):
    import numpy
    from scipy import interpolate

    d = _validate_day_arg(day)

    ##### put monthly data here
    # e.g. northern hemisphere mountains:  (from the r.sun help page)
    #    [jan,feb,mar,...,dec]
    # numbers taken from Worldwide Linke turbidity information: https://hal.science/hal-00465791
    # Using Mount Gambier, Tasmania values as it's at -37.73 latitude
    linke_data = numpy.array(
        [2.9, 3.0, 2.8, 2.7, 3.0, 2.8, 2.5, 2.9, 3.3, 2.9, 3.1, 3.1]
    )

    linke_data_wrap = numpy.concatenate((linke_data[9:12], linke_data, linke_data[0:3]))

    monthDays = numpy.array([0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    # init empty
    midmonth_day = numpy.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    for i in range(1, 12 + 1):
        midmonth_day[i - 1] = 15 + sum(monthDays[0:i])

    midmonth_day_wrap = numpy.concatenate(
        (midmonth_day[9:12] - 365, midmonth_day, midmonth_day[0:3] + 365)
    )

    linke = interpolate.interp1d(midmonth_day_wrap, linke_data_wrap, kind="cubic")
    # return interpolated value
    return float(linke(d))


# CLI usage
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USAGE: linke.py [day number (1-365)]")
        sys.exit(1)
    try:
        val = linke_by_day(sys.argv[1])
        print("%.4f" % val)
    except (ValueError, TypeError) as e:
        print(f"🚫 Error: {e}")
        print("USAGE: linke.py [day number (1-365)]")

        sys.exit(1)
