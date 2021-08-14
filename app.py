import sys
import ui
from ui import Ui_MainWindow

from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from PyQt5 import QtGui as qtg

from PyQt5.QtWidgets import QFileDialog, QMessageBox

################ Importing for the code taken from collect-finderprints-of-songs.py#################
import os

from termcolor import colored

import libs.fingerprint as fingerprint
from libs.config import get_config
from libs.db_sqlite import SqliteDatabase
from libs.reader_file import FileReader
####################################################################################################

class UiWindow(qtw.QMainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # self.ui.selectSourceFolderBtn.clicked.connect(self.sourceFolderCmd)
        self.ui.addFingerprintsBtn.clicked.connect(self.fingerprintCmd)

    def fingerprintCmd(self):
        folderPath = QFileDialog.getExistingDirectory() + "/"
        print(folderPath)

        ################ Taken the code from collect-finderprints-of-songs.py#################
        config = get_config()

        db = SqliteDatabase()
        # path = "mp3/"
        path = folderPath

        # fingerprint all files in a directory

        for filename in os.listdir(path):
            if filename.endswith(".mp3"):
                reader = FileReader(path + filename)
                audio = reader.parse_audio()

                song = db.get_song_by_filehash(audio['file_hash'])
                song_id = db.add_song(filename, audio['file_hash'])

                msg = ' * %s %s: %s' % (
                    colored('id=%s', 'white', attrs=['dark']),  # id
                    colored('channels=%d', 'white', attrs=['dark']),  # channels
                    colored('%s', 'white', attrs=['bold'])  # filename
                )
                print(msg % (song_id, len(audio['channels']), filename))

                if song:
                    hash_count = db.get_song_hashes_count(song_id)

                    if hash_count > 0:
                        msg = '   already exists (%d hashes), skip' % hash_count
                        print(colored(msg, 'red'))

                        continue

                print(colored('   new song, going to analyze..', 'green'))

                hashes = set()
                channel_amount = len(audio['channels'])

                for channeln, channel in enumerate(audio['channels']):
                    msg = '   fingerprinting channel %d/%d'
                    print(colored(msg, attrs=['dark']) % (channeln + 1, channel_amount))

                    channel_hashes = fingerprint.fingerprint(channel, Fs=audio['Fs'],
                                                            plots=config['fingerprint.show_plots'])
                    channel_hashes = set(channel_hashes)

                    msg = '   finished channel %d/%d, got %d hashes'
                    print(colored(msg, attrs=['dark']) % (channeln + 1, channel_amount, len(channel_hashes)))

                    hashes |= channel_hashes

                msg = '   finished fingerprinting, got %d unique hashes'

                values = []
                for hash, offset in hashes:
                    values.append((song_id, hash, offset))

                msg = '   storing %d hashes in db' % len(values)
                print(colored(msg, 'green'))

                db.store_fingerprints(values)

        print('end')

if __name__ == '__main__':
    # print("This script is not supposed to be run directly from here")

    # If we want to run uiDesign.py along with its functionalities in this code, un-comment the following:
    # app = QtWidgets.QApplication(sys.argv)
    # MainWindow = QtWidgets.QMainWindow()
    # ui = Ui_MainWindow()
    # ui.setupUi(MainWindow)
    # MainWindow.show()
    # sys.exit(app.exec_())

    app = qtw.QApplication([])
    widget = UiWindow()
    widget.show()
    app.exec_()