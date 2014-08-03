#!/usr/bin/env python
# -*- coding: utf-8

'''
    RouterOS config monitoring

    Generates LaTeX reports containing each user's diff file
    and opens resulting PDF in system's default PDF viewer

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
import sys
import time
import subprocess
import shutil
import os
import xml.etree.ElementTree



latex_command = 'xelatex'
backup_dir_name = 'report_backups'
config_dir_name = 'config_backups'


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


def move(source, destination):
    ''' Moves/Renames file source to destination '''
    try:
        os.remove(destination)
    except OSError:
        pass

    shutil.copyfile(source, destination)

    os.remove(source)


def get_users_from_file(filename):
    ''' Reads and returns user info dictionary from file filename '''
    users_dict = {}

    tree = xml.etree.ElementTree.parse(filename)
    root = tree.getroot()

    for user_info in root:
        username = user_info.get('username')
        realname = user_info.find('realname').text

        users_dict[username] = realname

    return users_dict


def create_report(user, realname):
    print('Generating report for "' + user, '" (' + realname + '):')

    filename_user_diff = user + '_diff.txt'

    if not os.path.exists(filename_user_diff):
        print('No diff file found for ' + user + ', skipping...')
        return


    create_backup(filename_user_diff)
    move(filename_user_diff, 'diff.txt')


    # Write users's real name into 'nameit.txt' (for LaTeX)
    with open('nameit.txt', 'w') as nameit:
        nameit.write(realname)

    # Generate LaTeX report
    if subprocess.call([latex_command, 'report.tex']) != 0:
        print('Could not execute', latex_command, '!!!')
        exit()


    filename_user_report = user + '_report.pdf'
    move('report.pdf', filename_user_report)
    file_report_backup = create_backup(filename_user_report)


    # Open file
    if sys.platform.startswith('linux'):
        subprocess.call(['xdg-open', file_report_backup])
    else:
        os.startfile(file_report_backup)


def main():
    users = get_users_from_file('users.xml')

    for user in users.keys():
        create_report(user, users[user])


if __name__ == '__main__':
    main()

