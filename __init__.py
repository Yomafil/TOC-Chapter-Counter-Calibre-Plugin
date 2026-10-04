from calibre.customize import InterfaceActionBase

class TOCChapterCounter(InterfaceActionBase):
    name = 'TOC Chapter Counter'
    description = 'Count chapters in an EPUB NCX Table of Contents and store the result in #chapter_count.'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Yomafil x ChatGPT'
    version = (1, 1, 0)
    minimum_calibre_version = (5, 0, 0)
    actual_plugin = 'calibre_plugins.toc_chapter_counter.ui:TOCChapterCounterAction'
