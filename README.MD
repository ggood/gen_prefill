Generate prefill files for ARRL November Sweepstakes

This is a python script that can ingest cabrillo log files from the ARRL November Sweepstakes and will output a prefill file. Supported formats include N1MM, WriteLog, and WinTest.

When a contact with a given station exists in more than one log, and any items in the exchange don't match, we choose the value for that item as follows:

Use only information from the most recent year's contest, e.g if the station was worked in 2011 and 2012, use the 2012 info as it's more likely to be up to date.
When more than one value was copied for the item in a given year, choose the most commonly copied value, if there is a most commonly copied value. If not, pick one.
