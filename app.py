

import os
import json
import logging
import uuid
import boto3
import pandas as pd
import panel as pn

from panel.chat import ChatInterface
from middleware import MidwayMiddleWare

from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler

os.environ['PANEL_ADMIN_LOG_LEVEL'] = 'debug'
print("env variable LAMBDA_FUNCTION_NAME: ", os.environ.get('LAMBDA_FUNCTION_NAME'))
print("os.environ: ", os.environ)

pn.extension('floatpanel', "perspective", "tabulator")

# logging.basicConfig(filename='myapp.log', level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROFILE_NAME = 'eu_beta'
REGION_NAME = 'eu-west-1'

APPROVE_TAGS = ['positive', 'like', 'approve']
DISAPPROVE_TAGS = ['negative', 'dislike', 'disapprove']
LAMBDA_FUNCTION_NAME = os.environ.get('LAMBDA_FUNCTION_NAME')

SESSION_ID = str(uuid.uuid4())

def feedback_button_factory(qa):
    like = pn.widgets.ButtonIcon(
        icon='thumb-up-filled',
        description='approve answer',
        on_click=lambda event: feedback_window_event_handler(event, qa),
        size='2em',
        tags=APPROVE_TAGS
    )
    dislike = pn.widgets.ButtonIcon(
        icon='thumb-down-filled',
        description='disapprove answer',
        on_click=lambda event: feedback_window_event_handler(event, qa),
        size='2em',
        tags=DISAPPROVE_TAGS
    )

    return pn.Column(like, dislike)

def invoke_quartz_lambda(data):
    
    session = boto3.Session()
    lambda_client = session.client('lambda', region_name=REGION_NAME)

    lambda_payload = json.dumps(data)
    api_response = lambda_client.invoke(FunctionName=LAMBDA_FUNCTION_NAME, InvocationType='RequestResponse', Payload=lambda_payload)
    response = json.loads(api_response['Payload'].read().decode('utf-8'))
    logging.info(response)
    
    return response

def invoke_feedback_lambda(data):

    session = boto3.Session()
    lambda_client = session.client('lambda', region_name=REGION_NAME)

    lambda_payload = json.dumps(data)
    api_response = lambda_client.invoke(FunctionName='quartz-interface-feedback', InvocationType='RequestResponse', Payload=lambda_payload)
    response = json.loads(api_response['Payload'].read().decode('utf-8'))
    logging.info(response)

def feedback_event_handler(event, feedback_type, feedback_content, qa):
    FEEDBACK_WINDOW_PLACEHODER[:] = []

    data = {
        'feedback_id': str(uuid.uuid4()),
        'session_id': SESSION_ID,
        'feedback_type': feedback_type,
        'feedback_content': feedback_content,
        'question': qa['question'],
        'answer': qa['answer']
    }
    invoke_feedback_lambda(data)

def feedback_window_event_handler(event, qa):
    
    if event.obj.tags[0] in APPROVE_TAGS:
        feedback_type = APPROVE_TAGS[0]
    elif event.obj.tags[0] in DISAPPROVE_TAGS:
        feedback_type = DISAPPROVE_TAGS[0]
    else:
        raise RuntimeError()
    
    input = pn.widgets.TextAreaInput(placeholder='Send a feedback')
    button = pn.widgets.Button(name='Send', button_type='primary', on_click=lambda event: feedback_event_handler(event, feedback_type, input.value, qa))

    floatpanel = pn.layout.FloatPanel(
        input,
        button,
        contained=True,
        position='center',
        config = {
            'headerControls': {
            'close': 'remove',
            'minimize': 'remove',
            'maximize': 'remove'
            }
        }
    )

    FEEDBACK_WINDOW_PLACEHODER[:] = [floatpanel]

def button_event_handler(event, chat_interface):
    message = event[2].tags[0]
    return chat_interface.send(message)

def chat_handler(content: str, user: str, instance: pn.chat.ChatInterface):
    data = {
        'request': 'query',
        'text': content,
        'session_id': SESSION_ID
    }
    response_content = invoke_quartz_lambda(data)
    print("response_content: ",response_content)

    if not (response := response_content.get('response', {})):
        return pn.Column(*['Could not find anything based on the inputs', pn.layout.Divider()])

    renderable_content = []

    messages = response.get('messages', {}).get('content', [])
    messages = messages[:-1] if messages[-1] == '' else messages

    qa = {
        'question': content,
        'answer': '\n'.join(messages)
    }
    for message in messages[:-1]:
        renderable_content.append(pn.Row(message))
    
    # chat
    renderable_content.append(pn.Row(messages[-1], feedback_button_factory(qa)))

    # generate response UI based on content type
    content_type = response.get('data', {}).get('contentType', {})
    response_content = response.get('data', {}).get('content', {})
    print("content_type: ", content_type)
    print("response_content: ", response_content)

    # render response in perspective
    if content_type == "table" and len(response_content)>0:
        df = pd.DataFrame(response_content)
        renderable_content.append(pn.Column(pn.pane.Perspective(df, width=700, height=400)))
        # renderable_content.append(pn.Column(pn.pane.Perspective(df, width=1, height=400),sizing_mode="stretch_width", styles=dict(background='Blue')))

    # render response in tabulator
    elif content_type == "json" and len(response_content)>0:
        PAGE_SIZE_TABULATOR = 50
        df = pd.DataFrame(response_content)
        tabulator = pn.widgets.Tabulator(df, pagination="local", page_size=PAGE_SIZE_TABULATOR, show_index=False)
        renderable_content.append(tabulator)
        # filename, button = tabulator.download_menu(
        #     text_kwargs={'name': 'Enter filename', 'value': 'default.csv'},
        #     button_kwargs={'name': 'Download table'}
        # )
        # renderable_content.append(pn.Column(button))
        button = pn.widgets.Button(name='Download table', button_type='primary')
        button.on_click(lambda event: tabulator.download(content+".csv"))
        renderable_content.append(pn.Column(button))

    if (action_buttons := response.get('actions', {}).get('content', [])):
        buttons = []
        for button in action_buttons:
            buttons.append(pn.widgets.Button(name=button['text'], tags=[button['value']], on_click=lambda event: button_event_handler(event, instance), button_type='primary'))

        renderable_content.append(pn.Row(*buttons))

    renderable_content.append(pn.layout.Divider())

    return pn.Column(*renderable_content)

def create_chat_interface():
    CHAT_INTERFACE = ChatInterface(
        callback=chat_handler,
        user="You",
        avatar="Y",
        callback_user="Quartz",
        show_rerun=False,
        show_undo=False,
        show_button_name=False,
        callback_exception='verbose',
    )

    FEEDBACK_WINDOW_PLACEHODER = pn.Column(height=0, width=0)
    TEMPLATE = pn.template.FastListTemplate(
        site='Quartz Cognitive Assistant',
        title='',
        main=[pn.Column(FEEDBACK_WINDOW_PLACEHODER, CHAT_INTERFACE)]
    )

    CHAT_INTERFACE.send("Hi, Quartz!", respond=True)
    return TEMPLATE

client_id = "Quartz_EU_Beta"
client_secret = "RgjvkZpWHNZCcEGXPjX5t3EFtizsGtoh5yZpCuIGmdM6"

panel_app = create_chat_interface()
panel_app.servable()

# def modify_doc(doc):
#     doc.add_root(panel_app.get_root())

# bokeh_app = Application(FunctionHandler(modify_doc))

# # Create Bokeh server
# server = Server({'/': bokeh_app}, allow_websocket_origin=["*"])

# def get_wsgi_app():
#     return server

application = MidwayMiddleWare(panel_app)

# if __name__ == "__main__":
#     #appli.run(debug=False, port=8000)
#     pn.serve(
#         create_chat_interface,
#         start=True,
#         port= 80,
#         address= '0.0.0.0',
#         websocket_origin="*"
#     )
#         login_endpoint='/login',
#         logout_endpoint='/logout',
#         oauth_key = client_id, 
#         oauth_secret = client_secret,
#         oauth_extra_params={'token_url': 'https://idp-integ.federate.amazon.com/api/oauth2/v2/certs', 'authorize_url': 'https://idp-integ.federate.amazon.com/api/oauth2/v1/authorize' }

 

