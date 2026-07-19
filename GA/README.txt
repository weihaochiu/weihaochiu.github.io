Place graphical abstract images in this folder.

Filename rule:
DOI: 10.1002/adfm.202306367
Image: 10.1002_adfm.202306367.JPG or 10.1002_adfm.202306367.PNG

Supported extensions: JPG, PNG, jpg, png, JPEG, jpeg.
The build script detects the image automatically when graphicalAbstract is empty.

If a publisher has been checked and no graphical abstract exists, use this in
the corresponding publications.json record so it is excluded from the missing
statistics:

"contentStatus": {
  "graphicalAbstract": "not-available"
}

The same statuses are supported for abstract, highlights and keywords:
available, pending, not-available.
