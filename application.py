
import panel as pn
import tornado.web
from tornado.web import RequestHandler
from panel.io.server import get_server
from tornado.ioloop import IOLoop

# Import your Panel app
from app import *

from python_amazon_interceptor import amazon_handler
from python_amazon_interceptor.amazon_handler import Config




class MiddlewareHandler(tornado.web.RequestHandler):
    def initialize(self, next_handler, environment_config):
        self.app = next_handler
        self.config = environment_config
        print('self in middleware handler')

    def prepare(self):
        environment["HTTP_HOST"] = "estops.beta-eu.quartz.rme.amazon.dev"
        handler = amazon_handler.AmazonHandlerRequest(environment, self.config)
        response = handler.authenticate()
        print('here in the prepare function')

        if response:
            self.next_handler(self)
            
        else:
            self.set_status(401)
            self.write("Unauthorized")
            self.finish()
            return
       
    


def make_app():
    environment_config = Config(
      auth_path="https://idp-integ.federate.amazon.com/api/oauth2/v1/authorize",
      auth_redirect_path="https://idp-integ.federate.amazon.com/api/oauth2/v1/authorize",
      client_id="estops-ui-beta",
      identity_provider_host="idp-integ.federate.amazon.com",
      jwks_url="https://idp-integ.federate.amazon.com/api/oauth2/v2/certs",
      redirect_uri="",  
    )
    panel_handler = tornado.web.Application('/', create_chat_interface)
    
    routes = [
        (r"/", MainHandler),
        (r"/ws", ChatWebSocket)
    ]
    wrapped_routes = [(path, MiddlewareHandler, dict(next_handler=handler, environment_config=environment_config)) for path, handler in routes]
    return tornado.web.Application(wrapped_routes)


class MainHandler:
    def get(self, handler):
        handler.write("Panel app is running at http://localhost:5006/")

class ChatWebSocket(tornado.websocket.WebSocketHandler):
    clients = set()

    def open(self):
        self.clients.add(self)
        self.write_message("Welcome to the chat!")

    def on_message(self, message):
        for client in self.clients:
            if client != self:
                client.write_message(message)

    def on_close(self):
        self.clients.remove(self)



if __name__ == "__main__":
    panel_proc = subprocess.Popen(['python', 'app.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    app_loader = make_app()
    server = tornado.httpserver.HTTPServer(app_loader)
    app_loader.listen(80)
    IOLoop.current().start()