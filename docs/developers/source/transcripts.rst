.. module:: transcripts

Transcripts
===========

**Transcripts workflow.**

This is multipage pdf version. Only first page is shown. Click on image to view
other pages.:

.. image:: transcripts_workflow.pdf
    :width: 100%
    :target: _images/transcripts_workflow.pdf

Open office graph version (source for pdf):

.. image:: transcripts_workflow.odg
    :width: 1%
    :target: _images/transcripts_workflow.odg

List of implemented acceptance tests

.. image:: transcripts_acceptance_tests.odt
    :width: 1%
    :target: _images/transcripts_acceptance_tests.odt

.. automodule:: contentstore.views.transcripts_ajax
    :members:
    :show-inheritance:

.. automodule:: contentstore.transcripts_utils
    :members:
    :show-inheritance:


Developer's workflow for the timed transcripts in CMS.
------------------------------------------------------

We provide 7 API methods to work with timed transcript
(edx-platform/cms/urls.py:23-29):
    * transcripts/upload
    * transcripts/download
    * transcripts/check
    * transcripts/choose
    * transcripts/replace
    * transcripts/rename
    * transcripts/save

**"transcripts/upload"** method is used for uploading SRT transcripts for the
HTML5 and Youtube video modules.

*Method:*
    POST
*Parameters:*
    - id - location ID of the Xmodule
    - video_list - list with information about the links currently passed in the editor/view.
    - file - BLOB file
*Response:*
    HTTP 400
    or
    HTTP 200 + JSON:
    .. code::
        {
            status: 'Success' or 'Error',
            subs: value of uploaded and saved sub field in the video item.
        }


**"transcripts/download"** method is used for downloading SRT transcripts for the
HTML5 and Youtube video modules.

*Method:*
    GET
*Parameters:*
    - id - location ID of the Xmodule
    - subs_id - file name that is used to find transcripts file in the storage.
*Response:*
    HTTP 404
    or
    HTTP 200 + BLOB of SRT file


**"transcripts/check"** method is used for checking availability timed transcripts
for the video module.
So,
   * **IF** youtube transcripts present locally **AND** on Youtube server **AND** both of these transcripts files are **DIFFERENT**, we respond with `replace` command. Ask user to replace local transcript file by Youtube's ones.
   * **IF** youtube transcripts present **ONLY** locally, we respond with `found` command.
   * **IF** youtube transcripts present **ONLY** on Youtube server, we respond with `import` command. Ask user to import transcripts file from Youtube server.
   * **IF** player in HTML5 video mode. It means that **ONLY** html5 sources are added:
        * **IF** just 1 html5 source was added or both html5 sources have **EQUAL** transcripts files, then we respond with `found` command.
        * **OTHERWISE**, when 2 html5 sources were added and founded transcripts files are **DIFFERENT**, we respond with `choose` command. In this case, user should choose which one transcripts file he want to use.
   * **IF** we are working just with 1 field **AND** item.sub field **HAS** a value **AND** user fill editor/view by the new value/video source without transcripts file, we respond with `use_existing` command. In this case, user will have possibility to use transcripts file from previous video.
   * **OTHERWISE**, we will respond with `not_found` command.

Command from front-end point of view is nothing else as a reference to the needed View with possible actions that user can do depending on conditions described above.

*Method:*
    GET
*Parameters:*
    - id - location ID of the Xmodule
*Response:*
    HTTP 400
    or
    HTTP 200 + JSON:
    .. code::
        {
            command: string with action to front-end what to do and what to show to user,
            subs: file name of transcripts file that was found in the storage,
            html5_local: [] or [True] or [True, True],
            is_youtube_mode: True/False,
            youtube_local: True/False,
            youtube_server: True/False,
            youtube_diff: True/False,
            current_item_subs: string with value of item.sub field,
            status: 'Error' or 'Success'
        }


**"transcripts/choose"** method is used for choosing which one transcripts file should be used.

*Method:*
    GET
*Parameters:*
    - id - location ID of the Xmodule
    - video_list - list with information about the links currently passed in the editor/view.
    - html5_id - file name of chosen transcripts file.

*Response:*
    HTTP 200 + JSON:
    .. code::
        {
            status: 'Success' or 'Error',
            subs: value of uploaded and saved sub field in the video item.
        }


**"transcripts/replace"** method is used for handling `import` and `replace` commands.
Invoking this method starts downloading new transcripts file from Youtube server.

*Method:*
    GET
*Parameters:*
    - id - location ID of the Xmodule
    - video_list - list with information about the links currently passed in the editor/view.

*Response:*
    HTTP 400
    or
    HTTP 200 + JSON:
    .. code::
        {
            status: 'Success' or 'Error',
            subs: value of uploaded and saved sub field in the video item.
        }


**"transcripts/rename"** method is used for handling `use_existing` command.
After invoking this method will be copied and renamed current transcripts file to another one with name of current video passed in the editor/view.

*Method:*
    GET
*Parameters:*
    - id - location ID of the Xmodule
    - video_list - list with information about the links currently passed in the editor/view.

*Response:*
    HTTP 400
    or
    HTTP 200 + JSON:
    .. code::
        {
            status: 'Success' or 'Error',
            subs: value of uploaded and saved sub field in the video item.
        }


**"transcripts/save"** method is used for handling `save` command.
After invoking this method will be saved all changes that were done before this moment.

*Method:*
    GET
*Parameters:*
    - id - location ID of the Xmodule
    - metadata - new values for the metadata fields.
    - currents_subs - list with the file names of videos passed in the editor/view.

*Response:*
    HTTP 400
    or
    HTTP 200 + JSON:
    .. code::
        {
            status: 'Success' or 'Error'
        }
