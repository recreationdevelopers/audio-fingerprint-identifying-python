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

############### From recognize-from-microphone.py###################################################

import argparse
import sys
from argparse import RawTextHelpFormatter
from itertools import zip_longest as izip_longest

import numpy as np
from termcolor import colored

import libs.fingerprint as fingerprint
from libs.config import get_config
from libs.db_sqlite import SqliteDatabase, SQLITE_MAX_VARIABLE_NUMBER
from libs.reader_microphone import MicrophoneReader
from libs.visualiser_console import VisualiserConsole as visual_peak
from libs.visualiser_plot import VisualiserPlot as visual_plot

# from libs.db_mongo import MongoDatabase
####################################################################################################


############### From recognize-from-file.py###################################################

import argparse
from itertools import zip_longest

from termcolor import colored

import libs.fingerprint as fingerprint
from libs.db_sqlite import SqliteDatabase, SQLITE_MAX_VARIABLE_NUMBER
from libs.reader_file import FileReader

####################################################################################################


class UiWindow(qtw.QMainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.listenAndSearchBtn.clicked.connect(self.listenAndSearchCmd)
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

    def listenAndSearchCmd(self):

        ################ Taken the code from recognize-from-microphone.py#################
        def align_matches(matches):
            diff_counter = {}
            largest = 0
            largest_count = 0
            song_id = -1

            for tup in matches:
                sid, diff = tup

                if diff not in diff_counter:
                    diff_counter[diff] = {}

                if sid not in diff_counter[diff]:
                    diff_counter[diff][sid] = 0

                diff_counter[diff][sid] += 1

                if diff_counter[diff][sid] > largest_count:
                    largest = diff
                    largest_count = diff_counter[diff][sid]
                    song_id = sid

            songM = db.get_song_by_id(song_id)

            nseconds = round(float(largest) / fingerprint.DEFAULT_FS *
                            fingerprint.DEFAULT_WINDOW_SIZE *
                            fingerprint.DEFAULT_OVERLAP_RATIO, 5)

            return {
                "SONG_ID": song_id,
                "SONG_NAME": songM[1],
                "CONFIDENCE": largest_count,
                "OFFSET": int(largest),
                "OFFSET_SECS": nseconds
            }


        def grouper(iterable, n, fillvalue=None):
            args = [iter(iterable)] * n
            return (filter(None, values)
                    for values in izip_longest(fillvalue=fillvalue, *args))


        def find_matches(samples, Fs=fingerprint.DEFAULT_FS):
            hashes = fingerprint.fingerprint(samples, Fs=Fs)
            return return_matches(hashes)


        def return_matches(hashes):
            mapper = {}
            for hash, offset in hashes:
                mapper[hash.upper()] = offset
            values = mapper.keys()

            for split_values in map(list, grouper(values, SQLITE_MAX_VARIABLE_NUMBER)):
                # @todo move to db related files
                query = """
            SELECT upper(hash), song_fk, offset
            FROM fingerprints
            WHERE upper(hash) IN (%s)
        """
                query = query % ', '.join('?' * len(split_values))

                x = db.executeAll(query, split_values)
                matches_found = len(x)

                if matches_found > 0:
                    msg = '   ** found %d hash matches (step %d/%d)'
                    print(colored(msg, 'green') % (
                        matches_found,
                        len(split_values),
                        len(values)
                    ))
                else:
                    msg = '   ** not matches found (step %d/%d)'
                    print(colored(msg, 'red') % (len(split_values), len(values)))

                for hash_code, sid, offset in x:
                    # (sid, db_offset - song_sampled_offset)
                    if isinstance(offset, bytes):
                        # offset come from fingerprint.py and numpy extraction/processing
                        offset = np.frombuffer(offset, dtype=np.int)[0]
                    yield sid, offset - mapper[hash_code]


        config = get_config()

        db = SqliteDatabase()

        # parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter)
        # parser.add_argument('-s', '--seconds', nargs='?')
        # args = parser.parse_args()

        # if not args.seconds:
        #     parser.print_help()
        #     sys.exit(0)

        # seconds = int(args.seconds)

        seconds = 5 # Take 5 seconds of input audio (making it fixed)

        chunksize = 2 ** 12  # 4096
        channels = 2  # int(config['channels']) # 1=mono, 2=stereo

        record_forever = False
        visualise_console = bool(config['mic.visualise_console'])
        visualise_plot = bool(config['mic.visualise_plot'])

        reader = MicrophoneReader(None)

        reader.start_recording(seconds=seconds,
                            chunksize=chunksize,
                            channels=channels)

        self.ui.outputMessageLabel.setText('Recording started...')
        msg = ' * started recording..'
        print(colored(msg, attrs=['dark']))

        while True:
            bufferSize = int(reader.rate / reader.chunksize * seconds)

            for i in range(0, bufferSize):
                nums = reader.process_recording()

                if visualise_console:
                    msg = colored('   %05d', attrs=['dark']) + colored(' %s', 'green')
                    print(msg % visual_peak.calc(nums))
                else:
                    msg = '   processing %d of %d..' % (i, bufferSize)
                    print(colored(msg, attrs=['dark']))

            if not record_forever:
                break

        if visualise_plot:
            data = reader.get_recorded_data()[0]
            visual_plot.show(data)

        reader.stop_recording()

        self.ui.outputMessageLabel.setText('Recording stopped')
        msg = ' * recording has been stopped'
        print(colored(msg, attrs=['dark']))

        data = reader.get_recorded_data()

        msg = ' * recorded %d samples'
        print(colored(msg, attrs=['dark']) % len(data[0]))

        # reader.save_recorded('test.wav')

        Fs = fingerprint.DEFAULT_FS
        channel_amount = len(data)

        result = set()
        matches = []

        for channeln, channel in enumerate(data):
            # TODO: Remove prints or change them into optional logging.
            msg = '   fingerprinting channel %d/%d'
            print(colored(msg, attrs=['dark']) % (channeln + 1, channel_amount))

            matches.extend(find_matches(channel))

            msg = '   finished channel %d/%d, got %d hashes'
            print(colored(msg, attrs=['dark']) % (channeln + 1,
                                                channel_amount, len(matches)))

        total_matches_found = len(matches)

        print('')

        song = align_matches(matches)
        print(song['CONFIDENCE'])

        if total_matches_found > 0:
            msg = ' ** totally found %d hash matches'
            print(colored(msg, 'green') % total_matches_found)

            self.ui.outputMessageLabel.setText('Track name: ' + song['SONG_NAME'] +'\n' +
                                                'Track ID: ' + str(song['SONG_ID']) +'\n' +
                                                'Confidence of Search: ' + str(song['CONFIDENCE']))

            msg = ' => song: %s (id=%d)\n'
            msg += '    offset: %d (%d secs)\n'
            msg += '    confidence: %d'

            print(colored(msg, 'green') % (song['SONG_NAME'], song['SONG_ID'],
                                        song['OFFSET'], song['OFFSET_SECS'],
                                        song['CONFIDENCE']))

        else:
            self.ui.outputMessageLabel.setText("No matches found. Try again.")

            msg = ' ** not matches found at all'
            print(colored(msg, 'red'))

    def listenFromFileAndSearchCmd(self):

        def grouper(iterable, n, fillvalue=None):
            """Collect data into fixed-length chunks or blocks"""
            # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
            args = [iter(iterable)] * n
            return zip_longest(*args, fillvalue=fillvalue)


        def find_matches(db, samples, Fs=fingerprint.DEFAULT_FS):
            hashes = fingerprint.fingerprint(samples, Fs=Fs)
            return return_matches(db, hashes)


        def return_matches(db, hashes):
            mapper = {}
            for audio_hash, offset in hashes:
                mapper[audio_hash.upper()] = offset
            values = mapper.keys()

            for split_values in grouper(values, SQLITE_MAX_VARIABLE_NUMBER):
                # @todo move to db related files
                query = """
            SELECT upper(hash), song_fk, offset
            FROM fingerprints
            WHERE upper(hash) IN (%s)
            """
                query = query % ', '.join('?' * len(split_values))

                x = db.executeAll(query, split_values)
                matches_found = len(x)

                if matches_found > 0:
                    msg = '   ** found %d hash matches (step %d/%d)'
                    print(colored(msg, 'green') % (
                        matches_found,
                        len(split_values),
                        len(values)
                    ))
                else:
                    msg = '   ** not matches found (step %d/%d)'
                    print(colored(msg, 'red') % (
                        len(split_values),
                        len(values)
                    ))

                for audio_hash, sid, offset in x:
                    yield sid, offset - mapper[audio_hash]


        def align_matches(db, matches):
            diff_counter = {}
            largest = 0
            largest_count = 0
            song_id = -1

            for tup in matches:
                sid, diff = tup

                if diff not in diff_counter:
                    diff_counter[diff] = {}

                if sid not in diff_counter[diff]:
                    diff_counter[diff][sid] = 0

                diff_counter[diff][sid] += 1

                if diff_counter[diff][sid] > largest_count:
                    largest = diff
                    largest_count = diff_counter[diff][sid]
                    song_id = sid

            songM = db.get_song_by_id(song_id)

            nseconds = round(float(largest) / fingerprint.DEFAULT_FS *
                            fingerprint.DEFAULT_WINDOW_SIZE *
                            fingerprint.DEFAULT_OVERLAP_RATIO, 5)

            return {
                "SONG_ID": song_id,
                "SONG_NAME": songM[1],
                "CONFIDENCE": largest_count,
                "OFFSET": int(largest),
                "OFFSET_SECS": nseconds
            }


        def main():
            parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
            parser.add_argument("-f", "--file", type=argparse.FileType("r"), required=True)
            args = parser.parse_args()

            song = args.file.name
            args.file.close()

            r = FileReader(song)  # only get filename

            # get data,fs,file_hash,extension,songname,num_channels
            data = r.parse_audio()
            Fs = data["Fs"]

            db = SqliteDatabase()
            matches = []
            for channel in data['channels']:
                # TODO: Remove prints or change them into optional logging.
                matches.extend(find_matches(db, channel, Fs=Fs))

            total_matches_found = len(matches)

            print("")

            if total_matches_found:
                print(colored(f" ** totally found {total_matches_found} hash matches", "green"))

                song = align_matches(db, matches)

                print(
                    colored(
                        f" => song: {song['SONG_NAME']} (id={song['SONG_ID']})\n"
                        f"    offset: {song['OFFSET']} ({song['OFFSET_SECS']} secs)\n"
                        f"    confidence: {song['CONFIDENCE']}",
                        "green"
                    )
                )
            else:
                print(colored(" ** not matches found at all", "red"))

        main()

if __name__ == '__main__':
    # print("This script is not supposed to be run directly from here")

    app = qtw.QApplication([])
    widget = UiWindow()
    widget.show()
    app.exec_()