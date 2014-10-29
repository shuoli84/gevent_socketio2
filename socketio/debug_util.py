import traceback
import re


def print_call_stack(exclude_pattern=None):

    print """
    ##############################################
    #### CALL STACK                           ####
    ##############################################
    """

    lines = [line for line in traceback.format_stack()]
    exclude_regex = re.compile(exclude_pattern) if exclude_pattern else None

    lineno = 0
    while lineno < len(lines):
        if lines[lineno].strip().startswith('File'):
            file_line = lines[lineno]
            content_line = ""

            lineno += 1

            if lineno < len(lines):
                content_line = lines[lineno]
                lineno += 1

            if exclude_regex is not None and exclude_regex.match(file_line):
                continue

            print file_line
            print content_line
        else:
            lineno += 1
