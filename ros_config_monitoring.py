#!/usr/bin/env python
# -*- coding: utf-8

'''
    RouterOS config monitoring

    Connects to specified MikroTik RouterOS machines via SSH
    and writes down any configuration changes in a file

    Copyright (C) 2014  Babken Vardanyan

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import os
import time
import difflib
import socket
import logging
import logging.handlers
import sys
import configparser

import paramiko


config = configparser.ConfigParser()
config.read('config.txt')


def initialize_logging():
    global logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    handler_stdout = logging.StreamHandler(sys.stdout)
    handler_stdout.setLevel(logging.DEBUG)
    handler_log_file = logging.FileHandler(config['DEFAULT']['LOG_FILE_NAME'])
    handler_log_file.setLevel(logging.DEBUG)
    handler_email = logging.handlers.SMTPHandler(config['DEFAULT']['MAIL_SERVER'],
                                                 config['DEFAULT']['MAIL_FROM'],
                                                 config['DEFAULT']['MAIL_TO'],
                                                 config['DEFAULT']['MAIL_SUBJECT'])

    logger.addHandler(handler_stdout)
    logger.addHandler(handler_log_file)


def create_backup(filename):
    ''' Copies filename into backup directory and returns full path of
        the resulting copy
    '''
    import shutil

    backup_dir = 'backups'

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    backup_filename = time.strftime('%Y.%m.%d_%H.%M.%S') + '__' + filename
    backup_full_path = os.path.join(backup_dir, backup_filename)
    shutil.copy2(filename, backup_full_path)

    return backup_full_path


class Config(object):
    ''' Functions for receiving and diff'ing configs
    '''
    def __init__(self, client, username_changer):
        self.client = client
        self.username_changer = username_changer

        temp_transport = self.client.get_transport()
        self.hostname = temp_transport.getpeername()[0]

        self.filename_config = self.hostname + '_config.txt'

    def get_new_config(self):
        ''' Fetch and return current configuration from the router
        '''
        stdin, stdout, stderr = self.client.exec_command('/export compact')

        stderr_text = stderr.read().decode()
        if stderr_text:
            with open('stderr.txt') as file_stderr_log:
                file_stderr_log.write(stderr_text)

        new_config_raw = stdout.read()
        new_config_string = new_config_raw.decode()
        new_config_full_lines = new_config_string.replace('\\\r\n    ', '')

        new_config = ''
        top_command = ''

        for line in new_config_full_lines.splitlines():
            if not line:
                continue

            if line[0] == '#':
                new_config += line + '\n'
                continue

            if line[0] == '/':
                top_command = line
                continue

            new_config += top_command + ' ' + line + '\n'

        return new_config

    def get_old_config(self, new_config):
        ''' If config file exists, reads and returns it's contents
            If config file doesn't exist, write new config and return it
        '''
        try:
            file_config = open(self.filename_config, 'r')

            old_config = file_config.read()
        except IOError:
            logger.warning('Creating new config file %s', self.filename_config)

            file_config = open(self.filename_config, 'w')
            file_config.write(new_config)

            old_config = new_config

        file_config.close()

        return old_config

    def get_diff_result(self, old_config, new_config):
        old_splitlines = old_config.splitlines()
        new_splitlines = new_config.splitlines()

        diff_generator = difflib.unified_diff(old_splitlines[1:],
                                              new_splitlines[1:],
                                              n=0,
                                              lineterm='')

        diff_result = '\n'.join(list(diff_generator)[2:])

        return diff_result

    def handle_config_change(self, log_line):
        ''' Call this.

            Calculates difference between new_config and old_config.
            Backs up the old config file.
            Writes new configuration in config file.
        '''
        new_config = self.get_new_config()
        old_config = self.get_old_config(new_config)


        #self.hostname
        date_and_time = time.ctime()
        #log_line
        diff_result = self.get_diff_result(old_config, new_config)

        if not diff_result:
            logger.info('No config was changed at %s', self.hostname)
            return

        full_diff_text = self.hostname + ' ' + date_and_time + '\n' + \
                         log_line + '\n' + \
                         diff_result

        logger.info(full_diff_text)

        create_backup(self.filename_config)
        with open(self.filename_config, 'w') as file_config:
            file_config.write(new_config)


class Watch(object):
    ''' Router log watcher
    '''
    def __init__(self, hostname, passw, username_auditor):
        self.hostname = hostname
        self.username_auditor = username_auditor
        self.passw = passw
        self.client = None

    def log_line_processor(self, log_line_raw):
        ''' Searches for specific words indicating a configuration change.
        '''
        log_line = log_line_raw.decode('utf-8').strip()

        if ('changed by' in log_line or
                'moved by' in log_line or
                'added by' in log_line or
                'removed by' in log_line):
            username_changer = log_line.split()[-1]

            conf_instance = Config(self.client, username_changer)
            conf_instance.handle_config_change(log_line)

    def watch_log(self):
        ''' Opens new channel and starts listening for new log lines
        '''
        transport = self.client.get_transport()

        # Just in case check if there were changes while program was down
        self.log_line_processor(b'WARNING: While program down the config was '
                                b'changed by an unknown user')

        client = transport.open_session()
        client.exec_command('/log print follow-only')

        while not client.exit_status_ready():
            if client.recv_ready():
                recovered = client.recv(float(config['DEFAULT']['LOG_LINE_MAX']))

                for line in recovered.splitlines():
                    self.log_line_processor(line)

            if client.recv_stderr_ready():
                logger.error('Stderr: %s', str(client.recv_stderr(float(config['DEFAULT']['LOG_LINE_MAX']))))

            time.sleep(float(config['DEFAULT']['LOG_WATCH_INTERVAL']))

        client.close()
        transport.close()

    def connect(self):
        ''' Connect to the router and call watch_log()

            Return values:
                0: Disconnected
                1: Unable to connect
                2: Authentication failed
        '''

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.client.connect(self.hostname,
                                username=self.username_auditor,
                                password=self.passw)
        except socket.error:
            logger.error('Socket error: Could not connect to %s', self.hostname)
            return 1
        except paramiko.AuthenticationException:
            logger.error('Auth failed for %s@%s',
                          self.username_auditor,
                          self.hostname)
            #      self.hostname)
            return 2

        logger.info('Connected to %s as %s',
                     self.hostname,
                     self.username_auditor)

        self.watch_log()

        self.client.close()

        logger.warning('Disconnected from %s as %s',
                        self.hostname,
                        self.username_auditor)

        return 0

    def watch(self):
        ''' Call this as new thread.

            Connects to the router and tries to reconnect to the router on
            recoverable error.
        '''
        while True:
            if self.connect() in [0, 1]:
                logger.warning('Will keep trying to reconnect every %s '
                                'seconds to %s as %s',
                                config['DEFAULT']['RECONNECT_INTERVAL'],
                                self.hostname,
                                self.username_auditor)

                time.sleep(config['DEFAULT']['RECONNECT_INTERVAL'])
            else:
                break


def main():
    initialize_logging()

    watch = Watch('192.168.56.26', '', 'admin')
    watch.watch()


if __name__ == '__main__':
    main()

