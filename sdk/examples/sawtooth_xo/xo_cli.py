# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

from __future__ import print_function

import argparse
import configparser
import getpass
import logging
import os
import traceback
import sys
import shutil

from colorlog import ColoredFormatter

import sawtooth_signing.pbct as signing

from sawtooth_xo.xo_client import XoClient
from sawtooth_xo.xo_exceptions import XoException


def create_console_handler(verbose_level):
    clog = logging.StreamHandler()
    formatter = ColoredFormatter(
        "%(log_color)s[%(asctime)s %(levelname)-8s%(module)s]%(reset)s "
        "%(white)s%(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        })

    clog.setFormatter(formatter)

    if verbose_level == 0:
        clog.setLevel(logging.WARN)
    elif verbose_level == 1:
        clog.setLevel(logging.INFO)
    else:
        clog.setLevel(logging.DEBUG)

    return clog


def setup_loggers(verbose_level):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(create_console_handler(verbose_level))


def add_create_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('create', parents=[parent_parser])

    parser.add_argument(
        'name',
        type=str,
        help='an identifier for the new game')

    parser.add_argument(
        '--disable-client-validation',
        action='store_true',
        default=False,
        help='disable client validation')

    parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting')


def add_init_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('init', parents=[parent_parser])

    parser.add_argument(
        '--username',
        type=str,
        help='the name of the player')

    parser.add_argument(
        '--url',
        type=str,
        help='the url of the REST API')


def add_reset_parser(subparsers, parent_parser):
    subparsers.add_parser('reset', parents=[parent_parser])


def add_list_parser(subparsers, parent_parser):
    subparsers.add_parser('list', parents=[parent_parser])


def add_show_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('show', parents=[parent_parser])

    parser.add_argument(
        'name',
        type=str,
        help='the identifier for the game')


def add_take_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('take', parents=[parent_parser])

    parser.add_argument(
        'name',
        type=str,
        help='the identifier for the game')

    parser.add_argument(
        'space',
        type=int,
        help='the square number to take')


def create_parent_parser(prog_name):
    parent_parser = argparse.ArgumentParser(prog=prog_name, add_help=False)
    parent_parser.add_argument(
        '-v', '--verbose',
        action='count',
        help='enable more verbose output')

    return parent_parser


def create_parser(prog_name):
    parent_parser = create_parent_parser(prog_name)

    parser = argparse.ArgumentParser(
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers(title='subcommands', dest='command')

    add_create_parser(subparsers, parent_parser)
    add_init_parser(subparsers, parent_parser)
    add_reset_parser(subparsers, parent_parser)
    add_list_parser(subparsers, parent_parser)
    add_show_parser(subparsers, parent_parser)
    add_take_parser(subparsers, parent_parser)

    return parser


def do_init(args, config):
    username = config.get('DEFAULT', 'username')
    if args.username is not None:
        username = args.username

    url = config.get('DEFAULT', 'url')
    if args.url is not None:
        url = args.url

    config.set('DEFAULT', 'username', username)
    print("set username: {}".format(username))
    config.set('DEFAULT', 'url', url)
    print("set url: {}".format(url))

    save_config(config)

    wif_filename = config.get('DEFAULT', 'key_file')
    if wif_filename.endswith(".wif"):
        addr_filename = wif_filename[0:-len(".wif")] + ".addr"
    else:
        addr_filename = wif_filename + ".addr"

    if not os.path.exists(wif_filename):
        try:
            if not os.path.exists(os.path.dirname(wif_filename)):
                os.makedirs(os.path.dirname(wif_filename))

            privkey = signing.generate_privkey()
            encoded = signing.encode_privkey(privkey, 'wif')
            pubkey = signing.generate_pubkey(privkey)
            addr = signing.generate_identifier(pubkey)

            with open(wif_filename, "w") as wif_fd:
                print("writing file: {}".format(wif_filename))
                wif_fd.write(encoded)
                wif_fd.write("\n")

            with open(addr_filename, "w") as addr_fd:
                print("writing file: {}".format(addr_filename))
                addr_fd.write(addr)
                addr_fd.write("\n")
        except IOError as ioe:
            raise XoException("IOError: {}".format(str(ioe)))


def do_reset(args, config):
    home = os.path.expanduser("~")
    config_dir = os.path.join(home, ".sawtooth")

    if os.path.exists(config_dir):
        shutil.rmtree(home, ".sawtooth")


def do_list(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = XoClient(base_url=url, keyfile=key_file)
    game_list = client.list()

    if game_list is not None:
        fmt = "%-15s %-15.15s %-15.15s %-9s %s"
        print(fmt % ('GAME', 'PLAYER 1', 'PLAYER 2', 'BOARD', 'STATE'))
        for game_data in game_list:

            board, game_state, player1, player2, name = \
                game_data.decode().split(",")

            print(fmt % (name, player1[:6], player2[:6], board, game_state))
    else:
        raise XoException("Could not retrieve game listing.")


def do_show(args, config):
    name = args.name

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = XoClient(base_url=url, keyfile=key_file)
    game = client.show(name).decode()

    if game is not None:

        board_str, game_state, player1, player2, name = \
            game.split(",")

        board = list(board_str.replace("-", " "))

        print("GAME:     : {}".format(name))
        print("PLAYER 1  : {}".format(player1[:6]))
        print("PLAYER 2  : {}".format(player2[:6]))
        print("STATE     : {}".format(game_state))
        print("")
        print("  {} | {} | {}".format(board[0], board[1], board[2]))
        print(" ---|---|---")
        print("  {} | {} | {}".format(board[3], board[4], board[5]))
        print(" ---|---|---")
        print("  {} | {} | {}".format(board[6], board[7], board[8]))
        print("")

    else:
        raise XoException("Game not found: {}".format(name))


def do_create(args, config):
    name = args.name

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = XoClient(base_url=url,
                      keyfile=key_file)
    response = client.create(name)
    print("Response: {}".format(response))


def do_take(args, config):
    name = args.name
    space = args.space

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = XoClient(base_url=url,
                      keyfile=key_file)
    response = client.take(name, space)
    print("Response: {}".format(response))


def load_config():
    home = os.path.expanduser("~")
    real_user = getpass.getuser()

    config_file = os.path.join(home, ".sawtooth", "xo.cfg")
    key_dir = os.path.join(home, ".sawtooth", "keys")

    config = configparser.ConfigParser()
    config.set('DEFAULT', 'url', '127.0.0.1:8080')
    config.set('DEFAULT', 'key_dir', key_dir)
    config.set('DEFAULT', 'key_file', '%(key_dir)s/%(username)s.wif')
    config.set('DEFAULT', 'username', real_user)
    if os.path.exists(config_file):
        config.read(config_file)

    return config


def save_config(config):
    home = os.path.expanduser("~")

    config_file = os.path.join(home, ".sawtooth", "xo.cfg")
    if not os.path.exists(os.path.dirname(config_file)):
        os.makedirs(os.path.dirname(config_file))

    with open("{}.new".format(config_file), "w") as fd:
        config.write(fd)
    if os.name == 'nt':
        if os.path.exists(config_file):
            os.remove(config_file)
    os.rename("{}.new".format(config_file), config_file)


def main(prog_name=os.path.basename(sys.argv[0]), args=sys.argv[1:]):
    parser = create_parser(prog_name)
    args = parser.parse_args(args)

    if args.verbose is None:
        verbose_level = 0
    else:
        verbose_level = args.verbose

    setup_loggers(verbose_level=verbose_level)

    config = load_config()

    if args.command == 'create':
        do_create(args, config)
    elif args.command == 'init':
        do_init(args, config)
    elif args.command == 'reset':
        do_reset(args, config)
    elif args.command == 'list':
        do_list(args, config)
    elif args.command == 'show':
        do_show(args, config)
    elif args.command == 'take':
        do_take(args, config)
    else:
        raise XoException("invalid command: {}".format(args.command))


def main_wrapper():
    try:
        main()
    except XoException as err:
        print("Error: {}".format(err), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except SystemExit as err:
        raise err
    except BaseException as err:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
