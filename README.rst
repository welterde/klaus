klaus
=====
*a simple Git web viewer that Just Works™.* (beta quality)

Demo at http://klausdemo.lophus.org

|img1|_ |img2|_ |img3|_

.. |img1| image:: https://github.com/jonashaag/klaus/raw/master/assets/commit-view.thumb.gif
.. |img2| image:: https://github.com/jonashaag/klaus/raw/master/assets/tree-view.thumb.gif
.. |img3| image:: https://github.com/jonashaag/klaus/raw/master/assets/blob-view.thumb.gif

.. _img1: https://github.com/jonashaag/klaus/raw/master/assets/commit-view.gif
.. _img2: https://github.com/jonashaag/klaus/raw/master/assets/tree-view.gif
.. _img3: https://github.com/jonashaag/klaus/raw/master/assets/blob-view.gif


Requirements
------------
* Python 2.7
* Jinja2_
* Pygments_
* dulwich_ (>= 0.7.1)
* flask

.. _Jinja2: http://jinja.pocoo.org/
.. _Pygments: http://pygments.org/
.. _dulwich: http://www.samba.org/~jelmer/dulwich/
.. _flask: http://flask.pocoo.org/


Installation
------------
*The same procedure as every year, James.* ::

   virtualenv your-env
   source your-env/bin/activate

   pip install jinja2
   pip install pygments
   pip install dulwich
   pip install flask

   git clone https://github.com/welterde/klaus


Usage
-----
Using the ``quickstart.py`` script
..................................
::

   ./quickstart --help
   ./quickstart.py <host> <port> /path/to/repo1 [../path/to/repo2 [...]]

Example::

   ./quickstart.py 127.0.0.1 8080 ../klaus ../nano ../bjoern

This will make klaus serve the *klaus*, *nano* and *bjoern* repos at
``127.0.0.1:8080`` using Python's built-in wsgiref_ server (or, if installed,
the bjoern_ server).

.. _wsgiref: http://docs.python.org/library/wsgiref.html
.. _bjoern: https://github.com/jonashaag/bjoern

Using a real server
...................
The ``klaus.py`` module contains a WSGI ``application`` object. The repo list
is read from the ``KLAUS_REPOS`` environment variable (space-separated paths).

UWSGI example::

   uwsgi ... -m klaus --env KLAUS_REPOS="/path/to/repo1 /path/to/repo2 ..." ...
