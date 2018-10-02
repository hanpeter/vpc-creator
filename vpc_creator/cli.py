# -*- coding: utf-8 -*-

from __future__ import absolute_import
import click
from vpc_creator.creator import Creator


# To allow click to display help on '-h' as well
CONTEXT_SETTINGS = {
    'help_option_names': ['-h', '--help']
}


@click.command(context_settings=CONTEXT_SETTINGS)
def main():
    creator = Creator()
    creator.run()
