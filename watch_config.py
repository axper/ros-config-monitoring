#!/usr/bin/env python2
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
import sys
import socket


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


    def append_diff(self, old_config, new_config, log_line):
        ''' Writes (appends) the difference between old and new
            configs in user's diff file
        '''
        old_splitlines = old_config.splitlines()
        new_splitlines = new_config.splitlines()

        filename_diff = self.username_changer + '_diff.txt'
        file_diff = open(filename_diff, 'a+')

        diff_mod_time = time.ctime(os.path.getmtime(filename_diff))

        diff_generator = difflib.unified_diff(old_splitlines[1:],
                                              new_splitlines[1:],
                                              fromfile='Prev Mod Time:',
                                              tofile='Current Time:',
                                              fromfiledate=diff_mod_time,
                                              tofiledate=time.ctime(),
                                              lineterm='')

        diff_result = ''
        for line in diff_generator:
            diff_result += line + '\n'

        if not diff_result:
            file_diff.close()
            return


        diff_result = self.hostname + '  ' + log_line + ':\n' + diff_result

        with open(self.username_changer + '_diff.txt', 'a+') as file_diff:
            print(diff_result)
            print(diff_result, file=file_diff)

        file_diff.close()


    def write_config_change(self, log_line):
        ''' Call this '''
        new_config = self.get_new_config()
        old_config = self.get_old_config(new_config)

        self.append_diff(old_config, new_config, log_line)

        create_backup(self.filename_config)

        # Update config file with new config
        with open(self.filename_config, 'w') as file_config:
            file_config.write(new_config)


class Watch(object):
    ''' Functions for watching router logs
    '''
    def __init__(self, hostname, username_auditor, passw):
        self.hostname = hostname
        self.username_auditor = username_auditor
        self.passw = passw

        # Initialized in connect()
        self.client = None


    def log_line_processor(self, log_line_raw):
        ''' Searches for specific words indicating a configuration change.
        '''
        log_line = log_line_raw.decode('ascii').strip()

        if ('changed by' in log_line or
                'moved by' in log_line or
                'added by' in log_line or
                'removed by' in log_line):
            username_changer = log_line.split()[-1]

            conf_instance = Config(self.client, username_changer)
            conf_instance.write_config_change(log_line)


    def watch_log(self):
        ''' Opens new channel and starts listening for new log lines
        '''
        transport = self.client.get_transport()

        # Just in case check if there were changes while program was down
        self.log_line_processor('config changed by UNKNOWN')

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

        disconnect_log = '='*10 + \
                         ' Router Disconnected: ' + self.hostname + \
                         ' at ' + time.ctime() + \
                         ' status: ' + str(client.recv_exit_status()) + ' ' + \
                         '='*10 + '\n'

        with open('UNKNOWN' + '_diff.txt', 'a+') as file_diff:
            print(disconnect_log)
            print(disconnect_log, file=file_diff)

        transport.close()
        client.close()


    def connect(self):
        ''' Connect to router with given parameters and call watcher '''
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.client.connect(self.hostname,
                                username=self.username_auditor,
                                password=self.passw)
        except paramiko.AuthenticationException:
            print('<Auth failed for', self.username_auditor + '@' +
                  self.hostname + '>')
            return

        connect_log = '='*10 + \
                      ' Router Connected: ' + self.hostname + \
                      ' at ' + time.ctime() + ' ' + \
                      '='*10 + '\n'

        with open('UNKNOWN' + '_diff.txt', 'a+') as file_diff:
            print(connect_log)
            print(connect_log, file=file_diff)

        self.watch_log()

        self.client.close()


    def watch(self):
        ''' Call this '''
        while True:
            try:
                self.connect()
            except socket.error:
                time.sleep(0.3)


def main():
    ''' Main loop '''
    while True:
        host = raw_input('Hostname:')
        username_auditor = raw_input('Username:')
        passw = getpass.getpass('Password:')

        watch = Watch(host, username_auditor, passw)

        proc = threading.Thread(target=watch.watch)
        proc.daemon = True
        proc.start()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)

