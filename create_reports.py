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
        realname = user_info.find('realname').text.encode('utf-8')

        users_dict[username] = realname

    return users_dict


def compile_latex(filename_tex):
    ''' Compiles the filename_tex to PDF using xelatex
        LaTeX distribution is first searched in $PATH.
        If not found, it looks for a local miktex_portable directory.
    '''
    try:
        subprocess.call(['xelatex', filename_tex])
    except OSError:
        print('Did not find xelatex in $PATH, looking for dir miktex_porable')
        try:
            subprocess.call(['miktex_portable\\miktex\\bin\\xelatex.exe',
                             filename_tex])
        except OSError:
            print('Could not find local porable directory either. Aborting')
            sys.exit(1)


def view_file(filename):
    ''' Opens a file in OS's default file viewer '''
    if sys.platform.startswith('linux'):
        subprocess.call(['xdg-open', filename])
    else:
        os.startfile(filename)


def create_report(user, realname):
    ''' Reads user's diff file and generates PDF report and opens the file '''
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

    compile_latex('report.tex')

    filename_user_report = user + '_report.pdf'
    move('report.pdf', filename_user_report)
    file_report_backup = create_backup(filename_user_report)


    view_file(file_report_backup)


def main():
    ''' Main function '''
    users = get_users_from_file('users.xml')

    for user in users.keys():
        create_report(user, users[user].decode())


if __name__ == '__main__':
    main()

