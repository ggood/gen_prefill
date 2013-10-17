#!/usr/bin/env python

import getopt
import os
import sys


callmap = {}


def load_pre(fn):
    """
    Load a file of pre-existing calls. This is typically a prefill file
    from a previous year. N1MM format only, which is a comma-separated
    file with fields:
      Call
      Name
      Grid1
      Grid2
      Section
      State
      CK
      Birthdate
    """
    sys.stderr.write("Seeding from file %s\n" % fn)
    total_lines = valid_lines = 0
    with open(fn, "r") as fp:
        buf = fp.readline()
        while buf != "":
            total_lines += 1
            buf = buf.strip()
            try:
                # WZ6Z,HOWARD,,,EB,CA,64,-1,A
                (call, name, grid1, grid2, sec, state, check, birthdate, prec) = buf.split(",")
                callmap[call.upper()] = [{
                    "name": name,
                    "grid1": grid1,
                    "grid2": grid2,
                    "sec": sec,
                    "state": state,
                    "check": check,
                    "birthdate": birthdate,
                    "prec": prec,
                    "year": -1,  # Used when breaking ties
                }]
                valid_lines += 1
            except ValueError:
                sys.stderr.write("Ignoring pre-existing call line \"%s\"" % buf)
            buf = fp.readline()
    sys.stderr.write("Read %d lines (%d valid)\n" % (total_lines, valid_lines))


def load_cabrillo(fn):
    """
    Format:
    QSO: 21039 CW 2012-11-03 2100 KM6I       0001 U 75 SCV N3EN       0001 A 56 MDC
    """
    sys.stderr.write("Processing %s\n" % fn)
    total_lines = log_lines = 0
    with open(fn, "r") as fp:
        buf = fp.readline()
        while buf != "":
            total_lines += 1
            buf = buf.strip()
            if buf.startswith("QSO:"):
                try:
                    (_, freq, mode, ymd, time, mycall, mynr, myprec, mycheck, mysec, call, nr, prec, check, sec) = buf.split()
                    log_lines += 1
                    call = call.upper()
                    if call not in callmap:
                        callmap[call] = []
                    callmap[call].append({
                        "name": "",
                        "grid1": "",
                        "grid2": "",
                        "sec": sec,
                        "state": "",
                        "check": check,
                        "birthdate": "-1",
                        "prec": prec,
                        "year": int(ymd[0:4]),
                    })
                    
                except ValueError:
                    pass
            buf = fp.readline()
    sys.stderr.write("Read %d lines (%d QSOs)\n" % (total_lines, log_lines))
               


def pick_most_common(call, key, entries):
    values = [entry[key] for entry in entries]
    values_set = set(values)
    ret = max(values_set, key=values.count)
    if len(values_set) > 1:
        sys.stderr.write("Ambiguous %s for %s: choosing %s from %s\n" % (key, call, ret, values))


def merge_entries(call, entries):
    """
    When this callsign appears in more than one log, there may be discrepancies,
    due to (a) the exchange changed from one year to another, or (b) the
    copying station busted one or more items. We pick the "best" value for
    each field accoding to the following algorithm:
    - we alwways prefer data from a more recent year, so discard all but the
      latest year
    - if the callsign appears in more than one log for the latest year,
      compute the most-often copied value for each item in the exchange
    """
    # Figure out which years this call was copied
    latest_year = sorted([entry["year"] for entry in entries])[-1]
    # And only use those entries
    latest_entries = [entry for entry in entries if entry["year"] == latest_year]
    if len(latest_entries) < 3:
        # If we have one entry, return it. If we have two entries, we
        # might as well pick one
        return latest_entries[0]
    ret_entry = dict(latest_entries[0])  # Make a copy
    ret_entry["sec"] = pick_most_common(call, "sec", latest_entries)
    ret_entry["check"] = pick_most_common(call, "check", latest_entries)
    ret_entry["prec"] = pick_most_common(call, "prec", latest_entries)
    return ret_entry


def write_n1mm():
    sys.stderr.write("Generating N1MM prefill file with %d callsigns\n" % len(callmap))
    for call in sorted(callmap.keys()):
        e = merge_entries(call, callmap[call])
        line = "%s,%s,%s,%s,%s,%s,%s,%s,%s" % (call, e["name"], e["grid1"], e["grid2"],
                                               e["sec"], e["state"], e["check"], e["birthdate"],
                                               e["prec"])
        sys.stdout.write(line)
        sys.stdout.write("\r\n")


def write_wintest():
    """
    format:
    4U1WB    U 4U1WB    89 MDC 
    """
    sys.stderr.write("Generating WinTest prefill file with %d callsigns\n" % len(callmap))
    for call in sorted(callmap.keys()):
        e = merge_entries(call, callmap[call])
        line = "%-9s%-2s%-9s%-3s%-4s" % (call, e["prec"] or "-", call, e["check"] or "--", e["sec"])
        sys.stdout.write(line)
        sys.stdout.write("\r\n")


def write_writelog():
    """
    format:
    <QSO_DATE:8>20021116 <TIME_ON:6>000008 <FREQ:6>28.375 <BAND:3>10m <STX:1>1 <MODE:3>SSB <M:1>1 <ML:1>2
     <SRX:1>5
     <P:0>
     <CALL:4>AA0B
     <CK:0>
     <ARRL_SECT:2>MO
    <EOR>
    """
    sys.stderr.write("Generating WriteLog prefill file with %d callsigns\n" % len(callmap))
    i = 1
    time_on = 0
    for call in sorted(callmap.keys()):
        e = merge_entries(call, callmap[call])
        stanza = """<QSO_DATE:8>20021116 <TIME_ON:6>%06d <FREQ:6>28.375 <BAND:3>10m <STX:1>1 <MODE:3>SSB <M:1>1 <ML:1>2
 <SRX:%d>%d
 <P:%d>%s>
 <CALL:%d>%s
 <CK:%d>%s
 <ARRL_SECT:%d>%s
<EOR>""" % (time_on, len(str(i)), i, len(e["prec"]), e["prec"], len(call), call, len(e["check"]), e["check"], len(e["sec"]), e["sec"])
        sys.stdout.write(stanza)
        sys.stdout.write("\r\n")
        i += 1
        time_on += 2



def usage():
    sys.stderr.write(
"""
usage: %s [-p pre_existing_fills] -d dir
""" % sys.argv[0])

if __name__ == "__main__":
    pre_ex_file = None
    cabrillo_dir = None
    try:
        optlist, args = getopt.getopt(sys.argv[1:], "p:d:")
    except getopt.GetoptError as ex:
        sys.stderr.write(str(ex))
        sys.stderr.write("\n")
        usage()
        sys.exit(1)
    for arg, opt in optlist:
        if arg == "-p":
            pre_ex_file = opt
        elif arg == "-d":
            cabrillo_dir = opt

    if pre_ex_file:
        load_pre(pre_ex_file)
    if cabrillo_dir:
        files = os.listdir(cabrillo_dir)
        for file in files:
            load_cabrillo(os.path.join(cabrillo_dir, file))

    write_n1mm()
    #write_wintest()
    #write_writelog()
