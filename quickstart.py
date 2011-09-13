#!/usr/bin/env python2
# coding: utf-8
import sys, os
import argparse

try:
    from bjoern import run
except ImportError:
    from wsgiref.simple_server import make_server
    def run(app, host, port):
        make_server(host, port, app).serve_forever()

def valid_directory(path):
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError('%r: No such directory' % path)
    return path

def main():
    parser = argparse.ArgumentParser(epilog='Gemüse kaufen!')
    parser.add_argument('host', help='(without http://)')
    parser.add_argument('port', type=int)
    parser.add_argument('--display-host', dest='custom_host')
    parser.add_argument('repo', nargs='+', type=valid_directory,
                        help='repository directories to serve')
    args = parser.parse_args()
    sys.argv = ['this is a hack'] + args.repo

    from klaus import app
    if args.custom_host:
        app.custom_host = args.custom_host

    run(app, args.host, args.port)

if __name__ == '__main__':
    main()
