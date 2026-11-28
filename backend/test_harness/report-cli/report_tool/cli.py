from argparse import ArgumentParser

import report_tool.preview as preview

from . import dispatch
from .reports import build_report


def build_parser():
    parser = ArgumentParser(description="Summarize a list of labels.")
    parser.add_argument("labels", nargs="+", help="Labels to summarize.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--preview", action="store_true", help="Show only the first label.")
    return parser


def main(argv=None):
    options = build_parser().parse_args(argv)
    if options.preview:
        report = preview.build_report(options.labels)
    else:
        report = build_report(options.labels)
    print(dispatch.render(report, options.format))
    return 0
