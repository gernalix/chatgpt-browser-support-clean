"""On-demand browser connectivity diagnostic; no global task control."""
import argparse
import json
import os
import sys

from .browser import ChatGPTBrowser


def main(argv=None):
    parser=argparse.ArgumentParser(prog='chatgpt-rdc-supervisor')
    parser.add_argument('--endpoint',default=os.environ.get('CHATGPT_RDC_ENDPOINT','chrome'))
    parser.add_argument('cmd')
    parser.add_argument('legacy_arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args(argv)
    if args.cmd!='doctor':
        print('global_supervisor_retired: use C3 directly',file=sys.stderr)
        return 2
    browser=ChatGPTBrowser(args.endpoint)
    try:
        browser.connect()
        pages=sum(len(context.pages) for context in browser.browser.contexts)
        print(json.dumps({'cdp':'ok','pages':pages,'endpoint':args.endpoint}))
        return 0
    except Exception as exc:
        print(json.dumps({'cdp':'error','error':f'{type(exc).__name__}: {exc}'}))
        return 2
    finally:
        browser.close()


if __name__=='__main__':
    raise SystemExit(main())
