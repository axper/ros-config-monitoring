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

from __future__ import print_function
import paramiko
import os
import shutil
import time
import difflib
import getpass
import threading


def create_backup(filename):
    ''' Copies filename into backup directory and returns full path of it
    '''
    backup_dir = 'backups'

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    backup_filename = time.strftime('%d.%m.%Y_%H.%M.%S') + '__' + filename
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
            print('Note: Old config file does not exist. '
                  'Creating new config file and writing new config')

            file_config = open(self.filename_config, 'w')
            file_config.write(new_config)

            old_config = new_config

        file_config.close()

        return old_config


    def append_diff(self, old_config, new_config):
        ''' Writes (appends) the difference between old and new
            configs in user's diff file
        '''
        old_splitlines = old_config.splitlines()
        new_splitlines = new_config.splitlines()

        diff_result = difflib.ndiff(old_splitlines[2:], new_splitlines[2:])

        diff_filtered = ''

        for diffline in diff_result:
            if diffline[:2] in ['+ ', '- ']:
                diff_filtered += diffline + '\n'

        if len(diff_filtered) > 0:
            filename_diff = self.username_changer + '_diff.txt'
            file_diff = open(filename_diff, 'a+')

            header_line = self.hostname + ' ' + new_splitlines[0]
            print(header_line)
            print(header_line, file=file_diff)

            print(diff_filtered)
            print(diff_filtered, file=file_diff)

            file_diff.close()


    def write_config_change(self):
        ''' Call this '''
        new_config = self.get_new_config()
        old_config = self.get_old_config(new_config)

        self.append_diff(old_config, new_config)

        create_backup(self.filename_config)

        # Update config file with new config
        with open(self.filename_config, 'w') as file_config:
            file_config.write(new_config)


class Watch(object):
    ''' Functions for watching router logs
    '''
    def __init__(self, hostname, client):
        self.hostname = hostname
        self.client = client


    def log_line_processor(self, log_line_raw):
        ''' Searches for specific words indicating a configuration change.
        '''
        log_line = log_line_raw.decode('ascii').strip()

        if ('changed by' in log_line or
                'moved by' in log_line or
                'added by' in log_line or
                'removed by' in log_line):
            print(log_line)
            username_changer = log_line.split()[-1]
            print('Config changed by', username_changer + ':')

            conf_instance = Config(self.client, username_changer)
            conf_instance.write_config_change()


    def watch_log(self):
        ''' Opens new channel and starts listening for new log lines
        '''
        transport = self.client.get_transport()

        # Just in case check if there were changes while program was down
        conf_instance = Config(self.client, 'UNKNOWN')
        conf_instance.write_config_change()

        client = transport.open_session()
        client.exec_command('/log print follow-only')

        while not client.exit_status_ready():
            if client.recv_ready():
                recovered = client.recv(500)

                for line in recovered.splitlines():
                    self.log_line_processor(line)

            if client.recv_stderr_ready():
                print('Stderr:', str(client.recv_stderr(500)))

            time.sleep(0.05)

        print('Exit status:', client.recv_exit_status())

        transport.close()
        client.close()


def connect(hostname, username_auditor, passw):
    ''' Connect to router with given parameters and call watcher '''
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname, username=username_auditor, password=passw)

    watch = Watch(hostname, client)
    watch.watch_log()

    client.close()


def main():
    ''' Main loop '''

    while True:
        host = raw_input('Hostname:')
        username_auditor = raw_input('Username:')
        passw = getpass.getpass('Password:')

        proc = threading.Thread(target=connect, args=(host,
                                                      username_auditor,
                                                      passw))
        proc.daemon = True
        proc.start()

if __name__ == '__main__':
    main()

