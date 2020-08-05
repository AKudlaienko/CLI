#!/usr/bin/env python

""" A simple script for Jinja2 Template rendering """
from jinja2 import Template
import traceback
import argparse
import sys

arg_parser = argparse.ArgumentParser(description='Jinja2 Teplete rendering',
                                     usage='\n{} --path /tmp/test_template.j2'.format(sys.argv[0]))
arg_parser.add_argument('-p', '--path', help='Full path to the *.j2 template', required=True)
all_args_raw = arg_parser.parse_args()


if len(vars(all_args_raw)['path']) > 2:
    file_path = vars(all_args_raw)['path']
else:
    print("\nHey, it seems that you provided an empty path value!\n--path '{}'".format(vars(all_args_raw)['path']))
    sys.exit(1)

with open(file_path, 'r') as temp:
    try:
        raw = Template(temp.read())
        print(raw.render())
    except Exception:
        print(traceback.format_exc())

