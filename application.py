
import panel as pn
import tornado.web
from tornado.web import RequestHandler
from panel.io.server import get_server
from tornado.ioloop import IOLoop
import subprocess

# Import your Panel app
from app import *

from python_amazon_interceptor import amazon_handler
from python_amazon_interceptor.amazon_handler import Config

environment_config = Config(
    auth_path="https://idp-integ.federate.amazon.com/api/oauth2/v1/authorize",
    auth_redirect_path="https://idp-integ.federate.amazon.com/api/oauth2/v1/authorize",
    client_id="estops-ui-beta",
    identity_provider_host="idp-integ.federate.amazon.com",
    jwks_url="https://idp-integ.federate.amazon.com/api/oauth2/v2/certs",
    redirect_uri="",  
)


class MiddlewareHandler(tornado.web.RequestHandler):
    def initialize(self, actual_handler_class):
        self.actual_handler_class = actual_handler_class
        #self.actual_handler_args = args
        #self.actual_handler_kwargs = kwargs
        print('self in middleware handler')
    

    def prepare(self):
        #self.config = environment_config
        environment["HTTP_HOST"] = "estops.beta-eu.quartz.rme.amazon.dev"
        handler = amazon_handler.AmazonHandlerRequest(environment, environment_config)
        response = handler.authenticate()
        print('here in the prepare function')

        if response:
            self.actual_handler_class(self)
            '''pn.serve(
                create_chat_interface,
                #{'/':create_chat_interface,'/health':HealthCheckHandler,'/error/403.html':render_403_error},
                start=True,
                port= 80,
                address= '0.0.0.0',
                websocket_origin="*"
            ) '''

            
        else:
            self.set_status(401)
            self.write("Unauthorized")
            self.finish()
            return
 
class PanelHandler(tornado.web.RequestHandler):
    async def get(self):
        print('panel get')
        panel_app = create_chat_interface()
       
        self.write(panel_app.server_doc().to_json())

def make_app():
    return tornado.web.Application([
        (r"/", MiddlewareHandler, dict(actual_handler=PanelHandler)),
        (r"/panel", PanelHandler)
    ])



if __name__ == "__main__":
    

    panel_chatbot = pn.serve(
                {'/':create_chat_interface,'/health':HealthCheckHandler,'/error/403.html':render_403_error},
                start=True,
                port= 80,
                address= '0.0.0.0',
                websocket_origin="*"
            )
    app_loader = make_app()
    app_loader.listen(80)
    tornado.ioloop.IOLoop.current().start()