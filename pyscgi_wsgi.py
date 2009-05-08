#!python

"""
A port of SWAT (SCGI->WSGI Application Proxy) to using the Cherokee Project
SCGI implementation
"""

# References:
# http://trac.pythonpaste.org/pythonpaste/browser/Paste/trunk/paste/util/scgiserver.py
# http://www.cherokee-project.com/download/pyscgi/

import sys

from pyscgi import ServerFactory, SCGIHandler, SCGIServer

class SCGItoWSGIHandler(SCGIHandler):
    def __init__(self, request, client_address, server):
        self.application = server.application
        SCGIHandler.__init__(self, request, client_address, server)

    def handle_request(self):
        input = self.rfile
        output = self.wfile
        environ = self.env
        environ['wsgi.input']        = input
        environ['wsgi.errors']       = sys.stderr
        environ['wsgi.version']      = (1, 0)
        environ['wsgi.multithread']  = False
        environ['wsgi.multiprocess'] = True
        environ['wsgi.run_once']     = False

        if environ.get('HTTPS','off') in ('on','1'):
            environ['wsgi.url_scheme'] = 'https'
        else:
            environ['wsgi.url_scheme'] = 'http'

        prefix = '/sgcitest'
        path = environ['REQUEST_URI'][len(prefix):].split('?', 1)[0]
        
        environ['SCRIPT_NAME'] = prefix
        environ['PATH_INFO'] = path
        
        headers_set = []
        headers_sent = []
        chunks = []

        def write(data):
            chunks.append(data)
        
        def start_response(status, response_headers, exc_info=None):
            if exc_info:
                try:
                    if headers_sent:
                        # Re-raise original exception if headers sent
                        raise exc_info[0], exc_info[1], exc_info[2]
                finally:
                    exc_info = None     # avoid dangling circular ref
            elif headers_set:
                raise AssertionError("Headers already set!")
        
            headers_set[:] = [status, response_headers]
            return write
        
        result = self.application(environ, start_response)
        try:
            for data in result:
                chunks.append(data)
               
            # Before the first output, send the stored headers
            if not headers_set:
                # Error -- the app never called start_response
                status = '500 Server Error'
                response_headers = [('Content-type', 'text/html')]
                chunks = ["XXX start_response never called"]
            else:
                status, response_headers = headers_sent[:] = headers_set
               
            output.write('Status: %s\r\n' % status)
            for header in response_headers:
                output.write('%s: %s\r\n' % header)
            output.write('\r\n')
        
            for data in chunks:
                output.write(data)
        finally:
            if hasattr(result,'close'):
                result.close()
        
        # SCGI backends use connection closing to signal 'fini'.
        try:
            input.close()
            output.close()
            conn.close()
        except IOError, err:
            debug("IOError while closing connection ignored: %s" % err)

def simple_app(environ, start_response):
    status = '200 OK'
    response_headers = [('Content-type','text/plain')]
    start_response(status, response_headers)
    return ['Hello world!\n']

def serve_application(application, host="", port=4000):
    handler_class = SCGItoWSGIHandler
    server = SCGIServer(handler_class)
    server.application = application
    server.serve_forever()

serve_application(simple_app)
