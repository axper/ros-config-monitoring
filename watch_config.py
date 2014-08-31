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
import os
import shutil
import time
import difflib
import getpass
import threading
import sys
import socket
import Queue

import paramiko
from PyQt5 import QtCore, QtGui, QtWidgets


log_file = open('watch_config_log.txt', 'w')


class WriteStream(object):
    ''' stdout redirection to log window '''
    def __init__(self, queue):
        self.queue = queue

    def write(self, text):
        self.queue.put(text)
        log_file.write(text)


class MyReceiver(QtCore.QObject):
    mysignal = QtCore.pyqtSignal(str)

    def __init__(self,queue,*args,**kwargs):
        QtCore.QObject.__init__(self,*args,**kwargs)
        self.queue = queue

    from PyQt5.QtCore import pyqtSlot
    @pyqtSlot()
    def run(self):
        while True:
            text = self.queue.get()
            self.mysignal.emit(text)


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

    def create_backup(self, filename):
        ''' Copies filename into backup directory and returns full path of it
        '''
        backup_dir = 'backups'

        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        backup_filename = time.strftime('%d.%m.%Y_%H.%M.%S') + '__' + filename
        backup_full_path = os.path.join(backup_dir, backup_filename)
        shutil.copy2(filename, backup_full_path)

        return backup_full_path

    def write_config_change(self, log_line):
        ''' Call this '''
        new_config = self.get_new_config()
        old_config = self.get_old_config(new_config)

        self.append_diff(old_config, new_config, log_line)

        self.create_backup(self.filename_config)

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
            print('Auth failed for', self.username_auditor + '@' +
                  self.hostname + '\n')
            return 1
        except socket.error:
            print('Could not connect to', self.hostname + '\n')
            return 2

        connect_log = 'Connected to ' + self.hostname + \
                      ' at ' + time.ctime() + '\n'

        with open('UNKNOWN' + '_diff.txt', 'a+') as file_diff:
            print(connect_log)
            print(connect_log, file=file_diff)

        self.watch_log()

        self.client.close()

        return 0

    def watch(self):
        ''' Call this as new thread '''
        while True:
            if self.connect():
                break
            disconnect_log = 'Disconnected ' + self.hostname + \
                             ' at ' + time.ctime() + '\n' + \
                             'Will keep trying to reconnect ' + \
                             'every several seconds\n'

            with open('UNKNOWN' + '_diff.txt', 'a+') as file_diff:
                print(disconnect_log)
                print(disconnect_log, file=file_diff)

            time.sleep(0.3)


class Ui_MainWindow(QtWidgets.QWidget):
    window_visible = True

    def valid_ip_address(self, ip_address):
        try:
            socket.inet_aton(ip_address)
        except socket.error:
            return False

        return True

    def setupUi(self, MainWindow):
        MainWindow.setObjectName('MainWindow')
        MainWindow.resize(700, 450)
        self.centralWidget = QtWidgets.QWidget(MainWindow)
        self.centralWidget.setObjectName('centralWidget')
        self.gridLayout_2 = QtWidgets.QGridLayout(self.centralWidget)
        self.gridLayout_2.setObjectName('gridLayout_2')
        self.plainTextEdit = QtWidgets.QPlainTextEdit(self.centralWidget)
        font = QtGui.QFont()
        font.setFamily('Monospace')
        font.setPointSize(8)
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        self.plainTextEdit.setFont(font)
        self.plainTextEdit.setReadOnly(True)
        self.plainTextEdit.setObjectName('plainTextEdit')
        self.gridLayout_2.addWidget(self.plainTextEdit, 1, 0, 1, 1)
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName('gridLayout')
        self.lineEdit_hostname = QtWidgets.QLineEdit(self.centralWidget)
        self.lineEdit_hostname.setFocus()
        self.lineEdit_hostname.setObjectName('lineEdit_hostname')
        self.gridLayout.addWidget(self.lineEdit_hostname, 0, 1, 1, 1)
        self.lineEdit_login = QtWidgets.QLineEdit(self.centralWidget)
        self.lineEdit_login.setObjectName('lineEdit_login')
        self.gridLayout.addWidget(self.lineEdit_login, 1, 1, 1, 1)
        self.lineEdit_password = QtWidgets.QLineEdit(self.centralWidget)
        self.lineEdit_password.setEchoMode(QtWidgets.QLineEdit.EchoMode(QtWidgets.QLineEdit.Password))
        self.lineEdit_password.setObjectName('lineEdit_password')
        self.gridLayout.addWidget(self.lineEdit_password, 2, 1, 1, 1)
        self.pushButton_connect = QtWidgets.QPushButton(self.centralWidget)
        self.pushButton_connect.setAutoDefault(True)
        self.pushButton_connect.setDefault(True)
        self.pushButton_connect.setObjectName('pushButton_connect')
        self.gridLayout.addWidget(self.pushButton_connect, 0, 2, 1, 1)
        self.label_connect = QtWidgets.QLabel(self.centralWidget)
        self.label_connect.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_connect.setObjectName('label_connect')
        self.gridLayout.addWidget(self.label_connect, 0, 0, 1, 1)
        self.label_login = QtWidgets.QLabel(self.centralWidget)
        self.label_login.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_login.setObjectName('label_login')
        self.gridLayout.addWidget(self.label_login, 1, 0, 1, 1)
        self.label_password = QtWidgets.QLabel(self.centralWidget)
        self.label_password.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_password.setObjectName('label_password')
        self.gridLayout.addWidget(self.label_password, 2, 0, 1, 1)
        self.gridLayout_2.addLayout(self.gridLayout, 0, 0, 1, 1)
        MainWindow.setCentralWidget(self.centralWidget)
        self.menuBar = QtWidgets.QMenuBar(MainWindow)
        self.menuBar.setGeometry(QtCore.QRect(0, 0, 483, 19))
        self.menuBar.setObjectName('menuBar')
        MainWindow.setMenuBar(self.menuBar)
        self.statusBar = QtWidgets.QStatusBar(MainWindow)
        self.statusBar.setObjectName('statusBar')
        MainWindow.setStatusBar(self.statusBar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def on_pushButton_connect_clicked(self):
        host = self.lineEdit_hostname.text()
        if not self.valid_ip_address(host):
            self.statusBar.showMessage('Wrong IP address format')
            return

        username_auditor = self.lineEdit_login.text()
        if not username_auditor:
            self.statusBar.showMessage('Login is empty')
            return

        passw = self.lineEdit_password.text()

        watch = Watch(host, username_auditor, passw)

        proc = threading.Thread(target=watch.watch)
        proc.daemon = True
        proc.start()

        self.statusBar.clearMessage()

    def tray_icon_clicked(self):
        if self.window_visible:
            MainWindow.hide()
        else:
            MainWindow.show()

        self.window_visible = not self.window_visible

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate('MainWindow', 'MainWindow'))
        self.pushButton_connect.setText(_translate('MainWindow', 'Connect'))
        self.label_connect.setText(_translate('MainWindow', 'Connect:'))
        self.label_login.setText(_translate('MainWindow', 'Login:'))
        self.label_password.setText(_translate('MainWindow', 'Password:'))

        self.pushButton_connect.clicked.connect(self.on_pushButton_connect_clicked)

        self.system_tray = QtWidgets.QSystemTrayIcon(QtGui.QIcon('router_icon_noalpha.png'), ui)
        self.system_tray.setToolTip('RouterOS Config Monitoring')
        self.system_tray.show()

        self.system_tray.activated.connect(self.tray_icon_clicked)

    from PyQt5.QtCore import pyqtSlot
    @pyqtSlot(str)
    def append_text(self, text):
        self.plainTextEdit.moveCursor(QtGui.QTextCursor.End)
        self.plainTextEdit.insertPlainText(text)

    def closeEvent(self, event):
        print('nope.')

    '''
    def closeEvent(self, event):
        if self.okayToClose(): 
            #user asked for exit
            self.trayIcon.hide()
            event.accept()
        else:
            #"minimize"
            self.hide()
            self.trayIcon.show() #thanks @mojo
            event.ignore()
    '''


if __name__ == '__main__':
    queue = Queue.Queue()
    sys.stdout = WriteStream(queue)
    sys.stderr = WriteStream(queue)

    app = QtWidgets.QApplication(sys.argv)

    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()

    thread = QtCore.QThread()
    my_receiver = MyReceiver(queue)
    my_receiver.mysignal.connect(ui.append_text)
    my_receiver.moveToThread(thread)
    thread.started.connect(my_receiver.run)
    thread.start()

    sys.exit(app.exec_())

