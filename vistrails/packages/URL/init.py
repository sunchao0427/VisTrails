###############################################################################
##
## Copyright (C) 2014-2016, New York University.
## Copyright (C) 2011-2014, NYU-Poly.
## Copyright (C) 2006-2011, University of Utah.
## All rights reserved.
## Contact: contact@vistrails.org
##
## This file is part of VisTrails.
##
## "Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are met:
##
##  - Redistributions of source code must retain the above copyright notice,
##    this list of conditions and the following disclaimer.
##  - Redistributions in binary form must reproduce the above copyright
##    notice, this list of conditions and the following disclaimer in the
##    documentation and/or other materials provided with the distribution.
##  - Neither the name of the New York University nor the names of its
##    contributors may be used to endorse or promote products derived from
##    this software without specific prior written permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
## AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
## THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
## PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
## CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
## EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
## PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
## OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
## WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
## OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
## ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
###############################################################################

"""URL provides modules to download files via the network.

It can refer to HTTP and FTP files, which enables workflows to be distributed
without its associated data.

This package uses a local cache, inside the per-user VisTrails directory. This
way, files that haven't been changed do not need to be downloaded again. The
check is performed efficiently using HTTP headers.
"""

from __future__ import division

from datetime import datetime
import email.utils
import os
import re
import urllib
import urllib2

try:
    import hashlib
    sha_hash = hashlib.sha1
except ImportError:
    import sha
    sha_hash = sha.new

from vistrails.core.bundles.pyimport import py_import
from vistrails.core import debug
import vistrails.core.modules.basic_modules
from vistrails.core.modules.basic_modules import PathObject
import vistrails.core.modules.module_registry
from vistrails.core.modules.vistrails_module import Module, ModuleError
from vistrails.core.system import current_dot_vistrails, strptime
from vistrails.core.upgradeworkflow import UpgradeWorkflowHandler

from .identifiers import identifier
from .http_directory import download_directory
from .https_if_available import build_opener


package_directory = None

MAX_CACHE_FILENAME = 100


###############################################################################

def cache_filename(url):
    url = urllib.quote_plus(url)
    if len(url) <= MAX_CACHE_FILENAME:
        return url
    else:
        hasher = sha_hash()
        hasher.update(url)
        return url[:MAX_CACHE_FILENAME - 41] + "_" + hasher.hexdigest()


###############################################################################

class Downloader(object):
    def __init__(self, url, module, insecure):
        self.url = url
        self.module = module
        self.opener = build_opener(insecure=insecure)

    def execute(self):
        """ Tries to download a file from url.

        Returns the path to the local file.
        """
        self.local_filename = os.path.join(package_directory,
                                           cache_filename(self.url))

        # Before download
        self.pre_download()

        # Send request
        try:
            response = self.send_request()
        except urllib2.URLError, e:
            if self.is_in_local_cache:
                debug.warning("A network error occurred. DownloadFile will "
                              "use a cached version of the file")
                return self.local_filename
            else:
                raise ModuleError(
                        self.module,
                        "Network error: %s" % debug.format_exception(e))
        if response is None:
            return self.local_filename

        # Read response headers
        self.size_header = None
        if not self.read_headers(response):
            return self.local_filename

        # Download
        self.download(response)

        # Post download
        self.post_download(response)

        return self.local_filename

    def pre_download(self):
        pass

    def send_request(self):
        return self.opener.open(self.url)

    def read_headers(self, response):
        return True

    def download(self, response):
        try:
            dl_size = 0
            CHUNKSIZE = 4096
            f2 = open(self.local_filename, 'wb')
            while True:
                if self.size_header is not None:
                    self.module.logging.update_progress(
                            self.module,
                            dl_size * 1.0/self.size_header)
                chunk = response.read(CHUNKSIZE)
                if not chunk:
                    break
                dl_size += len(chunk)
                f2.write(chunk)
            f2.close()
            response.close()

        except Exception, e:
            try:
                os.unlink(self.local_filename)
            except OSError:
                pass
            raise ModuleError(
                    self.module,
                    "Error retrieving URL: %s" % debug.format_exception(e))

    def post_download(self, response):
        pass

    @property
    def is_in_local_cache(self):
        return os.path.isfile(self.local_filename)


class HTTPDownloader(Downloader):
    def pre_download(self):
        # Get ETag from disk
        try:
            with open(self.local_filename + '.etag') as etag_file:
                self.etag = etag_file.read()
        except IOError:
            self.etag = None

    def send_request(self):
        try:
            request = urllib2.Request(self.url)
            if self.etag is not None:
                request.add_header(
                    'If-None-Match',
                    self.etag)
            try:
                mtime = email.utils.formatdate(
                        os.path.getmtime(self.local_filename),
                        usegmt=True)
                request.add_header(
                    'If-Modified-Since',
                    mtime)
            except OSError:
                pass
            return self.opener.open(request)
        except urllib2.HTTPError, e:
            if e.code == 304:
                # Not modified
                return None
            raise

    def read_headers(self, response):
        try:
            self.mod_header = response.headers['last-modified']
        except KeyError:
            self.mod_header = None
        try:
            size_header = response.headers['content-length']
            if not size_header:
                raise ValueError
            self.size_header = int(size_header)
        except (KeyError, ValueError):
            self.size_header = None
        return True

    def _is_outdated(self):
        local_time = datetime.utcfromtimestamp(
                os.path.getmtime(self.local_filename))
        try:
            remote_time = strptime(self.mod_header,
                                   "%a, %d %b %Y %H:%M:%S %Z")
        except ValueError:
            try:
                remote_time = strptime(self.mod_header,
                                       "%a, %d %B %Y %H:%M:%S %Z")
            except ValueError:
                # unable to parse last-modified header, download file again
                debug.warning("Unable to parse Last-Modified header, "
                              "downloading file")
                return True
        return remote_time > local_time

    def download(self, response):
        if (not self.is_in_local_cache or
                not self.mod_header or self._is_outdated()):
            Downloader.download(self, response)

    def post_download(self, response):
        try:
            etag = response.headers['ETag']
        except KeyError:
            pass
        else:
            with open(self.local_filename + '.etag', 'w') as etag_file:
                etag = etag_file.write(etag)


class SSHDownloader(object):
    """ SSH downloader: downloads files via SCP, using paramiko and scp.

    Recognized URL schemes are:
        ssh://user[:password]@host[:port]/absolute/path
            Examples:
                ssh://john@vistrails.nyu.edu/home/john/example.txt
                ssh://eve:my%20secret@google.com/tmp/test%20file.bin
            Note that both password and path are url-encoded, that the path
            is absolute, and that the username must be specified
        scp://[user@]host:path
            Examples:
                scp://john@vistrails.nyu.edu:files/test.txt
                scp://poly.edu:/tmp/test.bin
            Note that nothing is url encoded, that the path can be relative
            (to the user's home directory) and that no username or port can
            be specified
    """

    SSH_FORMAT = re.compile(
            r'^'
            'ssh://'                    # Protocol
            '([A-Za-z0-9_/+.-]+)'       # 1 Username
            '(?::([^@]+))?'             # 2 Password
            '@([A-Za-z0-9_.-]+)'        # 3 Hostname
            '(?::([0-9]+))?'            # 4 Port number
            '(/.+)'                     # 5 Path (url-encoded!)
            '$'
            )
    SCP_FORMAT = re.compile(
            r'^'
            '(?:scp://)?'               # Protocol
            '(?:([A-Za-z0-9_/+.-]+)@)?' # 1 Username
            '([A-Za-z0-9_.-]+)'         # 2 Hostname
            ':(.+)'                     # 3 Path (not url-encoded)
            '$'
            )

    def __init__(self, url, module, insecure):
        self.url = url
        self.module = module

    def execute(self):
        # Parse URL
        password = None
        portnum = None
        if self.url.startswith('ssh:'):
            m = self.SSH_FORMAT.match(self.url)
            if m is None:
                raise ModuleError(self.module,
                                  "SSH error: invalid URL %r" % self.url)
            username, password, hostname, portnum, path = m.groups()
            password = urllib.unquote_plus(password)
            path = urllib.unquote_plus(path)
        elif self.url.startswith('scp:'):
            m = self.SCP_FORMAT.match(self.url)
            if m is None:
                raise ModuleError(self.module,
                                  "SSH error: invalid URL %r" % self.url)
            username, hostname, path = m.groups()
        else:
            raise ModuleError(self.module, "SSHDownloader: Invalid URL")

        if portnum is None:
            portnum = 22
        else:
            portnum = int(portnum)
        return self._open_ssh(username, password, hostname, portnum, path)

    def _open_ssh(self, username, password, hostname, portnum, path):
        paramiko = py_import('paramiko', {
                'pip': 'paramiko',
                'linux-debian': 'python-paramiko',
                'linux-ubuntu': 'python-paramiko',
                'linux-fedora': 'python-paramiko'})
        scp = py_import('scp', {
                'pip': 'scp'})

        local_filename = os.path.join(package_directory,
                                      cache_filename(self.url))

        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        try:
            ssh.connect(hostname, port=portnum,
                        username=username, password=password)
        except paramiko.SSHException, e:
            raise ModuleError(self.module, debug.format_exception(e))
        client = scp.SCPClient(ssh.get_transport())

        client.get(path, local_filename)
        return local_filename


downloaders = {
    'http': HTTPDownloader,
    'https': HTTPDownloader,
    'ssh': SSHDownloader,
    'scp': SSHDownloader}


class DownloadFile(Module):
    """ Downloads file from URL.

    This modules downloads a remote file. It tries to cache files on the local
    filesystem so as to not re-download unchanged files.

    Recognized URL schemes are:
      - `http://...`
      - `https://...`
      - `ftp://...`
      - `ssh://user[:password]@host[:port]/absolute/path`

        Examples:

        - `ssh://john@vistrails.nyu.edu/home/john/example.txt`
        - `ssh://eve:my%20secret@google.com/tmp/test%20file.bin`

        Note that both password and path are url-encoded, that the path
        is absolute, and that the username must be specified
      - `scp://[user@]host:path`

        Examples:

        - `scp://john@vistrails.nyu.edu:files/test.txt`
        - `scp://poly.edu:/tmp/test.bin`

        Note that nothing is url encoded, that the path can be relative
        (to the user's home directory) and that no username or port can
        be specified

    If `insecure` is set, an invalid TLS certificate will not cause an error.
    """

    def compute(self):
        self.check_input('url')
        url = self.get_input('url')
        insecure = self.get_input('insecure')
        local_filename = self.download(url, insecure)
        self.set_output('local_filename', local_filename)
        result = PathObject(local_filename)
        self.set_output('file', result)

    def download(self, url, insecure):
        """ Tries to download a file from url.

        Returns the path to the local file.
        """
        scheme = urllib2.splittype(url)[0]
        DL = downloaders.get(scheme, Downloader)
        return DL(url, self, insecure).execute()


class HTTPDirectory(Module):
    """Downloads a whole directory recursively from a URL.

    If `insecure` is set, an invalid TLS certificate will not cause an error.
    """

    def compute(self):
        self.check_input('url')
        url = self.get_input('url')
        insecure = self.get_input('insecure')
        local_path = self.download(url, insecure)
        self.set_output('local_path', local_path)
        local_dir = PathObject(local_path)
        self.set_output('directory', local_dir)

    def download(self, url, insecure):
        local_path = self.interpreter.filePool.create_directory(
                prefix='vt_http').name
        download_directory(url, local_path, insecure)
        return local_path


class URLEncode(Module):
    """Encode special characters to a format suitable for URLs.

    This uses Python's `urllib.quote_plus()` function, which encodes special
    characters as `%xx` escapes and a space ' ' with a plus sign '+'.

    Example::

    '~/abc def' -> '%7e/abc+def'
    """

    def compute(self):
        value = self.get_input('string')
        self.set_output('encoded', urllib.quote_plus(value))


class URLDecode(Module):
    """Decode special characters formatted into a URL.

    This uses Python's `urllib.unquote_plus()` function, which decodes '%xx'
    escapes and replaces a plus sign '+' with a space ' '.

    Example::

    '%7e/abc+def' -> '~/abc def'
    """

    def compute(self):
        encoded = self.get_input('encoded')
        self.set_output('string', urllib.unquote_plus(encoded))


def initialize(*args, **keywords):
    reg = vistrails.core.modules.module_registry.get_module_registry()
    basic = vistrails.core.modules.basic_modules

    reg.add_module(DownloadFile)
    reg.add_input_port(DownloadFile, "url", (basic.String, 'URL'))
    reg.add_input_port(DownloadFile, 'insecure',
                       (basic.Boolean, "Allow invalid SSL certificates"),
                       optional=True, defaults="['False']")
    reg.add_output_port(DownloadFile, "file",
                        (basic.File, 'local File object'))
    reg.add_output_port(DownloadFile, "local_filename",
                        (basic.String, 'local filename'), optional=True)

    reg.add_module(HTTPDirectory)
    reg.add_input_port(HTTPDirectory, 'url', (basic.String, "URL"))
    reg.add_input_port(HTTPDirectory, 'insecure',
                       (basic.Boolean, "Allow invalid SSL certificates"),
                       optional=True, defaults="['False']")
    reg.add_output_port(HTTPDirectory, 'directory',
                        (basic.Directory, "local Directory object"))
    reg.add_output_port(HTTPDirectory, 'local_path',
                        (basic.String, "local path"), optional=True)

    reg.add_module(URLEncode)
    reg.add_input_port(URLEncode, "string", basic.String)
    reg.add_output_port(URLEncode, "encoded", basic.String)

    reg.add_module(URLDecode)
    reg.add_input_port(URLDecode, "encoded", basic.String)
    reg.add_output_port(URLDecode, "string", basic.String)

    global package_directory
    dotVistrails = current_dot_vistrails()
    package_directory = os.path.join(dotVistrails, "HTTP")

    if not os.path.isdir(package_directory):
        try:
            debug.log("Creating HTTP package directory: %s" % package_directory)
            os.mkdir(package_directory)
        except Exception, e:
            raise RuntimeError("Failed to create cache directory: %s" %
                               package_directory, e)

    # Migrate files to new naming scheme: max 100 characters, with a hash if
    # it's too long
    handled = set()

    def move(old, new):
        if os.path.exists(new):
            os.remove(new)
            handled.add(new)
        os.rename(old, new)
        handled.add(old)

        old += '.etag'
        new += '.etag'
        if os.path.exists(new):
            os.remove(new)
            handled.add(new)
        if os.path.exists(old):
            os.rename(old, new)
            handled.add(old)

    renamed = 0
    for old_name in sorted(os.listdir(package_directory)):
        old_filename = os.path.join(package_directory, old_name)
        if old_filename in handled:
            continue
        if len(old_name) > MAX_CACHE_FILENAME:
            hasher = sha_hash()
            hasher.update(old_name)
            new_name = (old_name[:MAX_CACHE_FILENAME - 41] +
                        '_' + hasher.hexdigest())
            new_filename = os.path.join(package_directory, new_name)
            if os.path.exists(new_filename):
                oldtime = os.path.getmtime(old_filename)
                newtime = os.path.getmtime(new_filename)
                if oldtime > newtime:
                    move(old_filename, new_filename)
                    renamed += 1
                else:
                    os.remove(old_filename)
                    handled.add(old_filename)
                    if os.path.exists(old_filename + '.etag'):
                        os.remove(old_filename + '.etag')
                        handled.add(old_filename + '.etag')
            else:
                move(old_filename, new_filename)
                renamed += 1
        else:
            handled.add(old_filename + '.etag')
    if renamed:
        debug.warning("Renamed %d downloaded cache files" % renamed)


def handle_module_upgrade_request(controller, module_id, pipeline):
    module_remap = {
            # HTTPFile was renamed DownloadFile
            'HTTPFile': [
                (None, '1.0.0', 'DownloadFile'),
            ],
            'RepoSync': [
                (None, '1.1.0', 'org.vistrails.vistrails.reposync:RepoSync'),
            ]
        }

    return UpgradeWorkflowHandler.remap_module(controller,
                                               module_id,
                                               pipeline,
                                               module_remap)


###############################################################################

import unittest


class TestNaming(unittest.TestCase):
    def test_short(self):
        self.assertEqual(cache_filename('http://www.google.com/search'),
                         'http%3A%2F%2Fwww.google.com%2Fsearch')
        self.assertEqual(cache_filename('scp://admin@machine:/etc/passwd'),
                         'scp%3A%2F%2Fadmin%40machine%3A%2Fetc%2Fpasswd')

    def test_long(self):
        self.assertEqual(cache_filename('https://www.google.com/url?sa=t&rct=j'
                                        '&q=&esrc=s&source=web&cd=1&cad=rja&ua'
                                        'ct=8&ved=0ahUKEwjFlbDQ1ovLAhVsv4MKHcr'
                                        'LAjMQFggcMAA&url=http%3A%2F%2Fwww.vis'
                                        'trails.org%2Fusersguide%2Fdev%2Fhtml%'
                                        '2Fjob_submission.html&usg=AFQjCNHc6W3'
                                        'lWQShmPfYOMsT21kwckBEzw&sig2=3i2AMtOw'
                                        'njJQsKtnqOSfQg&bvm=bv.114733917,d.dm'
                                        'o'),
                         'https%3A%2F%2Fwww.google.com%2Furl%3Fsa%3Dt%26rct%3D'
                         'j%26q%3'
                         '_f7d14d30f12413851cc222a61618d5bad6119f77')
        self.assertEqual(cache_filename('ssh://admin@machine.domain.tld:22022/'
                                        'var/lib/apt/lists/security.debian.org'
                                        '_dists_jessie_updates_main_binary-amd'
                                        '64_Packages'),
                         'ssh%3A%2F%2Fadmin%40machine.domain.tld%3A22022%2Fvar'
                         '%2Flib%'
                         '_e1f69dccfec6f14cdb08f6041a2a43e63d21863d')


class TestDownloadFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vistrails.core.packagemanager import get_package_manager
        from vistrails.core.modules.module_registry import MissingPackage
        pm = get_package_manager()
        try:
            pm.get_package('org.vistrails.vistrails.http')
        except MissingPackage:
            pm.late_enable_package('URL')

    def testIncorrectURL(self):
        from vistrails.tests.utils import execute
        self.assertTrue(execute([
                ('DownloadFile', identifier, [
                    ('url', [('String', 'http://idbetthisdoesnotexistohrly')]),
                ]),
            ]))

    def testIncorrectURL_2(self):
        from vistrails.tests.utils import execute
        self.assertTrue(execute([
                ('DownloadFile', identifier, [
                    ('url', [('String', 'http://neitherodesthisohrly')]),
                ]),
            ]))


class TestHTTPDirectory(unittest.TestCase):
    def test_download(self):
        url = 'http://www.vistrails.org/testing/httpdirectory/test/'

        import shutil
        import tempfile
        testdir = tempfile.mkdtemp(prefix='vt_test_http_')
        try:
            download_directory(url, testdir)
            files = {}
            def addfiles(dirpath):
                td = os.path.join(testdir, dirpath)
                for name in os.listdir(td):
                    filename = os.path.join(testdir, dirpath, name)
                    dn = os.path.join(dirpath, name)
                    if os.path.isdir(filename):
                        addfiles(os.path.join(dirpath, name))
                    else:
                        with open(filename, 'rb') as f:
                            files[dn.replace(os.sep, '/')] = f.read()
            addfiles('')
            self.assertEqual(len(files), 4)
            del files['f.html']
            self.assertEqual(files, {
                    'a': 'aa\n',
                    'bb': 'bb\n',
                    'cc/d': 'dd\n',
                })
        finally:
            shutil.rmtree(testdir)


if __name__ == '__main__':
    unittest.main()
