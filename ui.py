import os
import zipfile
import xml.etree.ElementTree as ET

from qt.core import QProgressDialog, Qt, QApplication
from calibre.gui2 import error_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction


def chapter_count_from_ncx(data):
    """Count every navPoint in an NCX.

    Every navPoint is treated as one TOC entry/chapter.
    """
    root = ET.fromstring(data)

    total = 0

    for elem in root.iter():
        # Handle both namespaced and non-namespaced NCX files.
        tag = elem.tag
        if isinstance(tag, str) and tag.rsplit('}', 1)[-1] == 'navPoint':
            total += 1

    return total


def chapter_count_from_epub(fileobj):
    """Find an NCX inside an EPUB and count its navPoints."""
    fileobj.seek(0)

    with zipfile.ZipFile(fileobj, 'r') as zf:
        ncx_names = [
            name for name in zf.namelist()
            if name.lower().endswith('.ncx')
        ]

        if not ncx_names:
            raise ValueError('No .ncx file found in the EPUB')

        # Prefer toc.ncx when there is more than one NCX.
        ncx_names.sort(
            key=lambda name: (
                os.path.basename(name).lower() != 'toc.ncx',
                name
            )
        )

        with zf.open(ncx_names[0], 'r') as f:
            return chapter_count_from_ncx(f.read())


class TOCChapterCounterAction(InterfaceAction):
    name = 'TOC Chapter Counter'

    action_spec = (
        'TOC Chapter Counter',
        None,
        'Count chapters from EPUB TOC and fill #chapter_count',
        None
    )

    def genesis(self):
        self.qaction.setIcon(
            get_icons('images/icon.png', 'TOC Chapter Counter')
        )
        self.qaction.triggered.connect(self.run_counter)

    def run_counter(self):
        db = self.gui.current_db.new_api

        # Require a normal integer custom column named #chapter_count.
        if '#chapter_count' not in db.fields:
            return error_dialog(
                self.gui,
                'TOC Chapter Counter',
                'The custom column #chapter_count does not exist.\n\n'
                'Create it in Preferences → Add your own columns:\n'
                '  Lookup name: chapter_count\n'
                '  Column heading: Chapter Count\n'
                '  Column type: Integer\n\n'
                'Then run this plugin again.',
                show=True
            )

        # Get the books currently selected in the library view.
        selected_ids = set(
            self.gui.library_view.get_selected_ids()
        )

        book_ids = list(db.all_book_ids())
        
        epub_ids = []

        for book_id in book_ids:
            # Only EPUB books can be processed.
            if not db.has_format(book_id, 'EPUB'):
                continue

            # Always process selected books.
            if book_id in selected_ids:
                epub_ids.append(book_id)
                continue

            # Unselected books are processed only when `#chapter_count` has no value.
            chapter_count = db.field_for('#chapter_count', book_id, None)

            if chapter_count is None:
                epub_ids.append(book_id)

        if not epub_ids:
            return info_dialog(
                self.gui,
                'TOC Chapter Counter',
                'No EPUB books need processing.\n\n',
                'Selected books are always processed. ',
                'Unselected books are processed only when #chapter_count has no value.',
                show=True
            )

        progress = QProgressDialog(
            'Counting chapters in EPUBs...',
            'Cancel',
            0,
            len(epub_ids),
            self.gui
        )

        progress.setWindowTitle('TOC Chapter Counter')
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        values = {}
        errors = []
        processed = 0

        for index, book_id in enumerate(epub_ids, 1):
            progress.setValue(index - 1)
            progress.setLabelText(
                'Reading EPUB %d of %d...'
                % (index, len(epub_ids))
            )

            QApplication.processEvents()

            if progress.wasCanceled():
                break

            title = db.field_for(
                'title',
                book_id,
                'Book %d' % book_id
            )

            try:
                fobj = db.format(
                    book_id,
                    'EPUB',
                    as_file=True
                )

                if fobj is None:
                    raise ValueError('Could not read EPUB')

                values[book_id] = chapter_count_from_epub(fobj)

            except Exception as e:
                errors.append('%s: %s' % (title, e))

            processed += 1

        progress.setValue(len(epub_ids))
        progress.close()

        if values:
            db.set_field('#chapter_count', values)

        # Ask the library view to refresh its displayed rows.
        try:
            self.gui.library_view.model().refresh()
        except Exception:
            try:
                self.gui.library_view.model().resort()
            except Exception:
                pass

        msg = (
            'Updated %d EPUB book(s) in #chapter_count.'
            % len(values)
        )

        if errors:
            msg += (
                '\n\n%d book(s) could not be processed.'
                % len(errors)
            )
            msg += '\n' + '\n'.join(errors[:10])

            if len(errors) > 10:
                msg += (
                    '\n...and %d more.'
                    % (len(errors) - 10)
                )

        if processed < len(epub_ids):
            msg += '\n\nProcessing was cancelled.'

        info_dialog(
            self.gui,
            'TOC Chapter Counter',
            msg,
            show=True
        )