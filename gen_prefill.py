#!/usr/bin/env python

import getopt
import os
import sys
import time


callmap = {}
tot_qsos = 0
tot_logs = 0
start_time = time.time()

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
      Precedence
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
                    (_, freq, mode, ymd, time, mycall, mynr, myprec, mycheck, mysec, call, nr, prec, check, sec) = buf.split()[0:15]
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
    global tot_qsos
    tot_qsos += log_lines
    global tot_logs
    if log_lines > 0:
        tot_logs += 1
               


def pick_most_common(call, key, entries, latest_year):
    values = [entry[key] for entry in entries]
    values_set = set(values)
    ret = max(values_set, key=values.count)
    if len(values_set) > 1:
        sys.stderr.write("Ambiguous %s for %s: choosing %s from year %s, values %s\n" % (key, call, ret, latest_year, values))
    return ret


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
    ret_entry["sec"] = pick_most_common(call, "sec", latest_entries, latest_year)
    ret_entry["check"] = pick_most_common(call, "check", latest_entries, latest_year)
    ret_entry["prec"] = pick_most_common(call, "prec", latest_entries, latest_year)
    return ret_entry


def write_trlog(filename):
    # Format: AA0BA =ANE =K63 =VA
    with open(filename, "w") as fp:
        sys.stderr.write("Generating TR-LOG prefill file with %d callsigns\n" % len(callmap))
        for call in sorted(callmap.keys()):
            e = merge_entries(call, callmap[call])
            line = "%s%s%s%s%s" % (call,
                                      " =N%s" % e["name"] if e["name"] else "",
                                      " =A%s" %e["sec"] if e["sec"] else "",
                                      " =K%s" % e["check"] if e["check"] else "",
                                      " =V%s" % e["prec"] if e["prec"] else "")
            fp.write(line)
            fp.write("\r\n")


def write_n1mm(filename):
    with open(filename, "w") as fp:
        sys.stderr.write("Generating N1MM prefill file with %d callsigns\n" % len(callmap))
        for call in sorted(callmap.keys()):
            e = merge_entries(call, callmap[call])
            line = "%s,%s,%s,%s,%s,%s,%s,%s,%s" % (call, e["name"], e["grid1"], e["grid2"],
                                                   e["sec"], e["state"], e["check"], e["birthdate"],
                                                   e["prec"])
            fp.write(line)
            fp.write("\r\n")


def write_wintest(filename):
    """
    format:
    4U1WB    U 4U1WB    89 MDC 
    Update: N6TV suggested (1) adding a title line, and (2) using more generous padding, e.g.
    # TITLE 2013 NCCC data
    AA0A        U AA0A       60  MO 
    """
    with open(filename, "w") as fp:
        sys.stderr.write("Generating WinTest prefill file with %d callsigns\n" % len(callmap))
        year = time.strftime("%Y", time.gmtime())
        fp.write("# TITLE %s NCCC data\r\n" % year)
        for call in sorted(callmap.keys()):
            e = merge_entries(call, callmap[call])
            line = "%-11s %-2s%-10s %-4s%-4s%s" % (call,
                                               e["prec"] or "-",
                                               call,
                                               e["check"] or "--",
                                               e["sec"] or "---",
                                               "(%s)" % e["name"] if e["name"] else "")
            fp.write(line)
            fp.write("\r\n")


def write_writelog(filename):
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
    with open(filename, "w") as fp:
        sys.stderr.write("Generating WriteLog prefill file with %d callsigns\n" % len(callmap))
        i = 1
        time_on = 0
        fp.write("Writelog\r\n")
        fp.write("<EOH>\r\n")
        for call in sorted(callmap.keys()):
            e = merge_entries(call, callmap[call])
            stanza = [
                "<QSO_DATE:8>20021116 <TIME_ON:6>%06d <FREQ:6>28.375 <BAND:3>10m <STX:1>1 <MODE:3>SSB <M:1>1 <ML:1>2" % time_on,
                " <SRX:%d>%d"  % (len(str(i)), i),
                " <P:%d>%s" % (len(e["prec"]), e["prec"]),
                " <CALL:%d>%s" % (len(call), call),
                " <CK:%d>%s" % (len(e["check"]), e["check"]),
                " <ARRL_SECT:%d>%s" % (len(e["sec"]), e["sec"]),
                "<EOR>"
            ]
            fp.write("\r\n".join(stanza))
            fp.write("\r\n")
            i += 1
            time_on += 2


def enumerate_files(dir):
    """
    Recursively find all files within <topdir>, descending into
    any subdirectories.
    """
    files = []
    sys.stderr.write("PROCESS %s\n" % dir)
    for entry in os.listdir(dir):
        target = os.path.join(dir, entry)
        if os.path.isdir(target):
            sys.stderr.write("d %s\n" % target)
            files += enumerate_files(target)
        elif os.path.isfile(target):
            sys.stderr.write("f %s\n" % target)
            files.append(target)
        else:
            sys.stderr.write("? %s\n" % target)
    return files


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
        files = enumerate_files(cabrillo_dir)
        for file in files:
            load_cabrillo(file)

    write_n1mm("SS_2013_N1MM_prefill.txt")
    write_wintest("SS_2013_wintest_prefill.xdt")
    write_writelog("SS_2013_writelog_prefill.adi")
    write_trlog("SS_2013_trlog_prefill.asc")

    # For debugging is something's fishy with the calculations
    #import pprint
    #pprint.pprint(callmap)


    sys.stderr.write("Processed %d QSOs, %d unique callsigns, from %d logs, in %f seconds\n" % (tot_qsos, len(callmap), tot_logs, time.time() - start_time))
