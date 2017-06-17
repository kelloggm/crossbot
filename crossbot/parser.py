import argparse
import datetime
import re

import pytz

import crossbot.settings

# use this to prevent ArgumentParser from printing to the commandline
# we can instead catch this and send to Slack
class ParserException(Exception):
    pass

# subclass ArgumentParser so it doesn't just exit the program on error
# also we want the help messages to go to slack if we are using slack
class ArgumentParser(argparse.ArgumentParser):

    def print_help(self):  raise ParserException(self.format_help())
    def print_usage(self): raise ParserException(self.format_usage())

    def error(self, message):
        raise ParserException('Parse Error:\n' + message)

    def exit(self, status=0, message=None):
        if status != 0:
            raise ParserException('Parse Error:\n' + message)

class Parser:

    def __init__(self, limit_commands):

        self.parser = ArgumentParser(
            prog='@' + crossbot.settings.bot_name,
            description = '''
            You can either @ me in a channel or just DM me to give me a command.
            Play here: https://www.nytimes.com/crosswords/game/mini
            I live here: https://github.com/mwillsey/crossbot
            Times look like this `1:30` or this `:32` (the `:` is necessary).
            Dates look like this `2017-05-05` or simply `now` for today.
            `now` or omitted dates will automatically become tomorrow if the
            crossword has already been released (10pm weekdays, 6pm weekends).
            Here are my commands:\n\n
            '''
        )

        self.subparsers = self.parser.add_subparsers(help = 'subparsers help')

        help_parser = self.subparsers.add_parser('help')
        help_parser.set_defaults(command = 'help')
        help_parser.add_argument('help_subcommands', nargs='*')

        if not limit_commands:
            # add hidden (command line only) commands
            pass

    def print_help(self, args):
        # always raises ParserException so the client can print how it wants

        if args.help_subcommands:
            msg = ''
            for cmd in args.help_subcommands:
                try:
                    self.parser.parse_args([cmd, '--help'])
                except ParserException as e:
                    msg += str(e)
            raise ParserException(msg)

        else:
            # no subcommands specified, just print the regular message
            self.parser.print_help()

    def parse(self, string):
        # will raise ParserException if it fails or prints help

        args = self.parser.parse_args(string.split())
        command = getattr(args, 'command', None)

        if command is None or command == 'help':
            self.print_help(args) # should raise
            raise RuntimeError('Should never be here')

        return command, args



# helper functions that can be used in the `type` field of
# parser.add_argument()

time_rx = re.compile(r'(\d*):(\d\d)')
def time(time_str):
    '''Parses a time that looks like ":32", "3:42", or "fail".'''

    if time_str == 'fail':
        return 0

    match = time_rx.match(time_str)
    if not match:
        raise argparse.ArgumentTypeError(
            'Cannot parse time "{}", should look like ":32" or "fail"'
            .format(time_str))

    minutes, seconds = ( int(x) if x else 0
                         for x in match.groups() )

    return minutes * 60 + seconds


date_fmt = '%Y-%m-%d'
nyt_timezone = pytz.timezone('US/Eastern')

def date(date_str):
    '''If date_str is a date, this does nothing. If it's 'now' or None, then
    this gets either today's date or tomorrow's if the crossword has already
    come out (10pm on weekdays, 6pm on weekends)'''

    if date_str is None or date_str == 'now':

        dt = datetime.datetime.now(nyt_timezone)

        release_hour = 22 if dt.weekday() < 5 else 18
        release_dt = dt.replace(hour=release_hour, minute=0, second=30, microsecond=0)

        # if it's already been released (with a small buffer), use tomorrow
        if dt > release_dt:
            dt += datetime.timedelta(days=1)

    else:

        try:
            dt = datetime.datetime.strptime(date_str, date_fmt)
        except ValueError:
            raise argparse.ArgumentTypeError(
                'Cannot parse date "{}", should look like "YYYY-MM-DD" or "now".'
                .format(date_str))

    return dt.strftime(date_fmt)