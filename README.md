ffloader
========

Finite Fault Loader

This project loads the Finite Fault product onto the USGS web site.

Installation:
=============
To install, navigate in a Terminal to a directory above where this code should live, and type:

git clone https://github.com/mhearne-usgs/ffloader.git

This will create a folder called ffloader under your current directory.

Updating:
=========

In the ffolder directory you created during the installation process above, type:

git pull 

Usage:
=======
There is a single program to run, called ffault.py.

<pre>
Usage: ffault.py [options] NET EVENTID FFMDIR1 [FFMDIR2]
    Use this script to send finite fault data to PDL.
    Example: (for a single plane solution)
    ffault.py us b0006bqc /home/ghayes/ffmdata/b0006bqc
    OR (for a double plane solution)
    ffault.py us b0006bqc /home/ghayes/ffmdata/b0006bqc /home/ghayes/ffmdata/b0006bqc2
    OR (single plane solution with comment)
    ffault.py us b0006bqc /home/ghayes/ffmdata/b0006bqc /home/ghayes/ffmdata/b0006bqc2 -c"This earthquake is very deadly."
    

Options:
  -h, --help            show this help message and exit
  -c COMMENT, --comment=COMMENT
                        add a 'scientific analysis' comment to the HTML output
  -v COMMENT, --version=COMMENT
                        Add a version number to the finite fault output
  -r, --review          don't send products to PDL
</pre>