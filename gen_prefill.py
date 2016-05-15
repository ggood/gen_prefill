#!/usr/bin/env python

import getopt
import os
import sys
import time


callmap = {}
tot_qsos = 0
tot_logs = 0
start_time = time.time()


def load_pre(filename):
    """
    Load data from an N1MM-style prefill file.
    This version of load_pre() reads the N1MM !!Order!! directive if available.

    Default N1MM format is:
    Call, Name, Loc1, Loc2, Sect, State, CK, BirthDate, Exch1, Misc, UserText
    Exch1 is used for Prec in Sweepstakes.
    N1MM does not care about capitalization.  Call, call, CALL are all the same for N1MM.

    The following directive, as an example, might be found at the top of the file:
    !!Order!!, Call, Exch1, Ck, Sect, State

    A corresponding example line of the file would be:
    WZ6Z,A,64,EB,CA
    """
    print("Reading prefill file {:s}".format(filename))
    total_lines, valid_lines = 0, 0

    # N1MM default
    fields = ['CALL', 'NAME', 'LOC1', 'LOC2', 'SECT', 'STATE', 'CK', 'BIRTHDATE', 'EXCH1', 'MISC', 'USERTEXT']
    # field needed for Sweepstakes prefill
    sweeps_fields = ['CALL', 'SECT', 'CK', 'EXCH1']
    missing_field = False

    for line in open(filename, "r"):

        total_lines += 1

        if line.startswith('!!Order!!' or '!!ORDER!!' or '!!order!!'):
            fields = [item.strip().upper() for item in line.split(',')]
            fields.remove('!!ORDER!!')

            # check if all sweepstakes fields are present
            for item in sweeps_fields:
                if item not in fields:
                    print('The {:s} field is missing!'.format(item))
                    missing_field = True

        if not (line.startswith('#') or line.startswith('!!') or missing_field):
            try:
                data = [item.strip().upper() for item in line.split(',')]
                d = dict(zip(fields, data))
                d['YEAR'] = -1
                call = d['CALL']
                del d['CALL']
                callmap[call.upper()] = [d]
                valid_lines += 1
            except ValueError:
                print('Ignoring prefill call line: {:s}'.format(line))

    print('Read {:d} lines ({:d} valid) from prefill file.'.format(total_lines, valid_lines))


def load_cabrillo(fn):
    """
    Format:
    QSO: 21039 CW 2012-11-03 2100 KM6I       0001 U 75 SCV N3EN       0001 A 56 MDC
    """
    print('Processing {:s}'.format(fn))
    total_lines, log_lines = 0, 0
    with open(fn, "r") as fp:
        buf = fp.readline()
        while buf != "":
            total_lines += 1
            buf = buf.strip()
            if buf.startswith("QSO:"):
                try:
                    (_, freq, mode, ymd, time, mycall, mynr, myprec, mycheck, mysec, call, nr, prec, check,
                     sec) = buf.split()[0:15]
                    log_lines += 1
                    call = call.upper()
                    if call not in callmap:
                        callmap[call] = []
                    callmap[call].append({
                        "SECT": sec,
                        "CK": check,
                        "EXCH1": prec,
                        "YEAR": int(ymd[0:4]),
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
        sys.stderr.write(
            "Ambiguous %s for %s: choosing %s from year %s, values %s\n" % (key, call, ret, latest_year, values))
    return ret


def merge_entries_new(call, entries):
    """
    When this callsign appears in more than one log, there may be discrepancies,
    due to (a) the exchange changed from one year to another, or (b) the
    copying station busted one or more items. We pick the "best" value for
    each field according to the following algorithm:
    - we always prefer data from a more recent year, so discard all but the
      latest year
    - if the callsign appears in more than one log for the latest year,
      compute the most-often copied value for each item in the exchange
    """
    # Figure out which years this call was copied
    latest_year = sorted([entry["YEAR"] for entry in entries])[-1]
    # And only use those entries
    latest_entries = [entry for entry in entries if entry["YEAR"] == latest_year]
    if len(latest_entries) < 3:
        # If we have one entry, return it. If we have two entries, we
        # might as well pick one
        return latest_entries[0]
    ret_entry = dict(latest_entries[0])  # Make a copy
    ret_entry["SECT"] = pick_most_common(call, "SECT", latest_entries, latest_year)
    ret_entry["CK"] = pick_most_common(call, "CK", latest_entries, latest_year)
    ret_entry["EXCH1"] = pick_most_common(call, "EXCH1", latest_entries, latest_year)
    return ret_entry


def write_trlog(filename):
    # Format: AA0BA =ANE =K63 =VA
    with open(filename, "w") as fp:
        sys.stderr.write("Generating TR-LOG prefill file with %d callsigns\n" % len(callmap))
        for call in sorted(callmap.keys()):
            e = merge_entries_new(call, callmap[call])
            line = "%s%s%s%s" % (call,
                                 " =A%s" % e["SECT"] if e["SECT"] else "",
                                 " =K%s" % e["CK"] if e["CK"] else "",
                                 " =V%s" % e["EXCH1"] if e["EXCH1"] else "")
            fp.write(line)
            fp.write("\r\n")


def write_n1mm(filename):
    """
    This version of write_n1mm() takes advantage of N1MM's !!Order!! and !!MapStateToSect!! directives.
    See: http://n1mm.hamdocs.com/tiki-index.php?page=Call+History+and+Reverse+Call+History+Lookup
    """
    with open(filename, "w") as fp:
        sys.stderr.write("Generating N1MM prefill file with %d callsigns\n" % len(callmap))

        fp.write('# NCCC N1MM Logger Sweepstakes Call History File\n')
        fp.write('!!Order!!, CALL, EXCH1, CK, SECT\n')

        for call in sorted(callmap.keys()):
            e = merge_entries_new(call, callmap[call])
            line = "%s,%s,%s,%s" % (call, e["EXCH1"], e["CK"], e["SECT"])
            fp.write(line)
            fp.write("\n")


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
            e = merge_entries_new(call, callmap[call])
            line = "%-11s %-2s%-10s %-4s%-4s" % (call,
                                                 e["EXCH1"] or "-",
                                                 call,
                                                 e["CK"] or "--",
                                                 e["SECT"] or "---")
            fp.write(line)
            fp.write("\r\n")


def write_writelog(filename):
    """
    format:
    <CALL:4>AA0B
    <P:0>
    <CK:0>
    <ARRL_SECT:2>MO
    <EOR>
    """
    with open(filename, "w") as fp:
        sys.stderr.write("Generating WriteLog prefill file with %d callsigns\n" % len(callmap))

        fp.write("NCCC Writelog Sweepstakes Call History File\n")
        fp.write("<EOH>\n")

        for call in sorted(callmap.keys()):
            e = merge_entries_new(call, callmap[call])

            stanza = ["<CALL:%d>%s" % (len(call), call),
                      "<P:%d>%s" % (len(e["EXCH1"]), e["EXCH1"]),
                      "<CK:%d>%s" % (len(e["CK"]), e["CK"]),
                      "<ARRL_SECT:%d>%s" % (len(e["SECT"]), e["SECT"]),
                      "<EOR>"]

            fp.write("\n".join(stanza))
            fp.write("\n")


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
    # import pprint
    # pprint.pprint(callmap)

    sys.stderr.write("Processed %d QSOs, %d unique callsigns, from %d logs, in %f seconds\n" % (
        tot_qsos, len(callmap), tot_logs, time.time() - start_time))
