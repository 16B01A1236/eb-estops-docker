
from python_amazon_interceptor import amazon_handler


class MidwayMiddleWare:
    def __init__(self, application, environment_config):
        self.config = environment_config
        self.app = application

    def __call__(self, environment, start_response):
        environment["HTTP_HOST"] = "estops.beta-eu.quartz.rme.amazon.dev"
        handler = amazon_handler.AmazonHandlerRequest(environment, self.config)
        response = handler.authenticate()
        # Request is intercepted by the interceptor
        if response:
            start_response(response.status, response.headers)
            return [b"Auth Done!"]
        else:
            return self.app(environment, start_response)