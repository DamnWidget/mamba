# -*- test-case-name: mamba.scripts.test.test_mamba_admin -*-
# Copyright (c) 2012 Oscar Campos <oscar.campos@member.fsf.org>
# See LICENSE for more details

from __future__ import print_function

import os
import sys
import glob
import time
import signal
import subprocess

from twisted import copyright
from twisted.python import usage, filepath
from storm import version as storm_version

from mamba import version, license
from mamba import copyright as mamba_copyright
from mamba.utils.output import darkgreen, darkred
from mamba.core import GNU_LINUX, BSD, OSX, WINDOWS, POSIX

from ._sql import SqlOptions, Sql
from .commons import import_services
from ._view import ViewOptions, View
from ._model import ModelOptions, Model
from ._package import PackageOptions, Package
from ._project import ApplicationOptions, Application
from ._controller import ControllerOptions, Controller


def mamba_services_not_found():
    print(
        'error: make sure you are inside a mmaba application root '
        'directory and then run this command again'
    )
    sys.exit(-1)


class StartOptions(usage.Options):
    """Start command options for mamba-admin tool
    """
    synopsis = '[options]'

    optParameters = [
        ['port', 'p', '', 'override already mamba configured port']
    ]


class Options(usage.Options):
    """Base options for mamba-admin tool
    """
    synopsis = 'Usage: mamba-admin [options]'

    subCommands = [
        ['application', None, ApplicationOptions, 'Generate new application'],
        ['sql', None, SqlOptions, 'Manipulate SQL database'],
        ['controller', None, ControllerOptions, 'Generate new controller'],
        ['model', None, ModelOptions, 'Generate new model'],
        ['view', None, ViewOptions, 'Generate new view'],
        ['package', None, PackageOptions,
            'Pack or install a reusable mamba application. See reusability '
            'documentation for more details about this specific topic'],
        ['start', None, StartOptions,
            'Start a mamba application (you should be in the app directory)'],
        ['stop', None, usage.Options,
            'Stop a mamba application (you should be in the app directory)'],
        ['restart', None, usage.Options,
            'Reatart a mamba application (you should be in the app directory)']
    ]

    optFlags = [
        ['version', 'V', 'Print version information and exit'],
        ['disclaimer', None, 'Display disclaimer details and exit'],
        ['license', None, 'Print LICENSE information and exit']
    ]

    def __init__(self):
        super(Options, self).__init__()

    def opt_version(self):
        """Print version information and exit
        """
        print('Mamba Framework v{}'.format(version.short()))
        print('Twisted version: v{}'.format(copyright.version))
        print('Storm ORM version v{}'.format(storm_version))
        print(mamba_copyright.copyright)

    def opt_disclaimer(self):
        """Display disclaimer details and exit
        """
        print(mamba_copyright.disclaimer)

    def opt_license(self):
        """Print LICENSE information and exit
        """
        print(license.__LICENSE__)

    def postOptions(self):
        """Post options processing
        """
        if len(sys.argv) == 1:
            print(self)


def handle_application_command(options):
    """I handle the application command
    """

    Application(
        options.subOptions.opts['name'],
        options.subOptions.opts['description'],
        options.subOptions.opts['app-version'],
        (options.subOptions.opts['configfile'],
            options.subOptions.opts['logfile']),
        options.subOptions.opts['port'],
        True if options.subOptions.opts['noquestions'] == 1 else False
    )


def handle_start_command(options=None, dropin_cache_wa=False):
    """I handle the start command
    """

    try:
        mamba_services = import_services()
        mamba_services.config.Application('config/application.json')
    except ImportError:
        print(
            'error: make sure you are inside a mamba application root '
            'directory and then run this command again'
        )
        sys.exit(-1)

    if POSIX:
        app = mamba_services.config.Application()
        if app.port is None:
            print(
                'Your application configuration file does not define a valid '
                'port. Is your configuration file valid JSON format?'
            )
            sys.exit(-1)
        elif app.port <= 1024:
            if os.getuid() != 0:
                print(
                    '[{e}]: This application is configured to use a reserved '
                    'port (a port under 1025) only root can open a port from '
                    'this range root access is needed to start this '
                    'application using the {port} port.\n\nTry something '
                    'like: sudo mamba-admin start\n\nYou can also change the '
                    'configuration for this application editing '
                    '\'config/application.json\''.format(
                        e=darkred('ERROR'), port=app.port
                    )
                )
                sys.exit(-1)

    args = ['twistd']
    try:
        app_name = glob.glob(
            'twisted/plugins/*.py')[0].split(os.sep)[-1].rsplit('_', 1)[0]
    except IndexError:
        print(
            'error: twisted directory can\'t be found. You should be in '
            'the application directory in order to start it'
        )
        sys.exit(-1)

    if filepath.exists('twistd.pid'):
        print(
            'error: twistd.pid found, seems like the application is '
            'running already. If the application is not running, please '
            'delete twistd.pid and try again'
        )
        sys.exit(-1)

    # determine if we are running in heroku
    in_heroku = '.heroku' in os.environ.get('PYTHONHOME', '')

    args.append('--nodaemon')
    if not in_heroku:
        if not mamba_services.config.Application().auto_select_reactor:
            args.append(determine_platform_reactor(mamba_services))
        if not mamba_services.config.Application().development:
            args.remove('--nodaemon')
            args.append('--syslog')

    args.append(app_name)

    if options is not None and options.subOptions.opts['port']:
        args.append('--port={}'.format(options.subOptions.opts['port']))

    if in_heroku or mamba_services.config.Application().development:
        os.execlp('twistd', *args)
    else:
        if not dropin_cache_wa:
            print(
                'starting application {}...'.format(app_name).ljust(73), end=''
            )
        proc = subprocess.Popen(
            args, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out, err = proc.communicate()
        if not err:
            if 'exception' in out:
                result = darkred('Fail')
                exit_code = -1
            elif 'already installed' in out:
                return handle_start_command(options, True)
            else:
                result = darkgreen('Ok')
                exit_code = 0
        else:
            result = darkred('Fail')
            exit_code = -1

        print('[{}]'.format(result))
        print(err if exit_code == -1 else out)
        sys.exit(exit_code)


def handle_stop_command():
    """I handle the stop command
    """

    try:
        import_services()
    except ImportError:
        print(
            'error: make sure you are inside a mamba application root '
            'directory and then run this command again'
        )
        sys.exit(-1)

    twisted_pid = filepath.FilePath('twistd.pid')
    if not twisted_pid.exists():
        print(
            'error: twistd.pid file can\'t be found. You should be in the '
            'applicatin directory in order to stop it'
        )
        sys.exit(-1)

    pid = twisted_pid.open().read()
    print('killing process id {} with SIGINT signal'.format(
        pid).ljust(73), end='')
    try:
        filepath.os.kill(int(pid), signal.SIGINT)
        print('[{}]'.format(darkgreen('Ok')))
    except:
        print('[{}]'.format(darkred('Fail')))
        raise


def handle_restart_command():
    """I handle the restart command
    """

    handle_stop_command()
    while os.path.exists('twistd.pid'):
        time.sleep(0.1)
    handle_start_command()


def determine_platform_reactor(mamba_services):
    """Determine the reactor to use for the running platform

    If there is a configured reactor for this application, we force it
    """

    reactor = '--reactor={}'
    if hasattr(mamba_services.config.Application(), 'reactor'):
        return reactor.format(mamba_services.config.Application().reactor)

    default = 'select'
    if GNU_LINUX:
        default = 'epoll'
    elif BSD:
        default = 'kqueue'
    elif OSX:
        default = 'cf'
    elif WINDOWS:
        default = 'iocp'

    return reactor.format(default)


def run():

    try:
        options = Options()
        options.parseOptions()
    except usage.UsageError as errortext:
        print('{}: {}'.format(sys.argv[0], errortext))
        sys.exit(1)

    if options.subCommand == 'application':
        handle_application_command(options)

    if options.subCommand == 'start':
        handle_start_command(options)

    if options.subCommand == 'stop':
        handle_stop_command()

    if options.subCommand == 'restart':
        handle_restart_command()

    if options.subCommand == 'sql':
        Sql(options.subOptions)

    if options.subCommand == 'controller':
        Controller(options)

    if options.subCommand == 'model':
        Model(options)

    if options.subCommand == 'view':
        View(options)

    if options.subCommand == 'package':
        Package(options.subOptions)


if __name__ == '__main__':
    run()
