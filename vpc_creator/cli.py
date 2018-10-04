# -*- coding: utf-8 -*-

from __future__ import absolute_import
import getpass
import click
from vpc_creator.creator import Creator


# To allow click to display help on '-h' as well
CONTEXT_SETTINGS = {
    'help_option_names': ['-h', '--help']
}


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('--name', '-n', required=True, type=str)
@click.option('--cidr', '-c', type=str, default='10.0.0.0/16', show_default=True)
@click.option('--creator', type=str, default=getpass.getuser(), show_default=True)
@click.option('--subnet', '-s', required=True, multiple=True, type=str, nargs=2)
@click.option('--sns', default=None, show_default=True, type=str)
def main(name, cidr, creator, subnet, sns):
    subnets = {s[0]: s[1] for s in subnet}

    crt = Creator()
    crt.run(name=name, cidr=cidr, subnets=subnets, creator=creator, sns=sns)
