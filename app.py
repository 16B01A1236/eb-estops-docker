import os
import json
import logging
import uuid
import boto3

import panel as pn

from panel.chat import ChatInterface




js_files = {'amplify': '\\custom_static\\aws-amplify.min.js','midway': '\\custom_static\\midway.js'}
pn.extension(js_files=js_files)
print(js_files['midway'])
print('Hi from app')
os.environ['PANEL_ADMIN_LOG_LEVEL'] = 'debug'

pn.extension('floatpanel')


# logging.basicConfig(filename='myapp.log', level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROFILE_NAME = 'eu_beta'
REGION_NAME = 'eu-west-1'

APPROVE_TAGS = ['positive', 'like', 'approve']
DISAPPROVE_TAGS = ['negative', 'dislike', 'disapprove']

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
    api_response = lambda_client.invoke(FunctionName='quartz-estops', InvocationType='RequestResponse', Payload=lambda_payload)
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

def chat_handler(content: str, user: str, instance: pn.chat.ChatInterface):

    data = {
        'request': 'query',
        'text': content,
        'session_id': SESSION_ID
    }
    response_content = invoke_quartz_lambda(data)

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

'''def login():
    project_name = "quartz-eu-beta"
    app_client_id = "2fq8dtalchrevle04i6tdkvmrd"
    redirect_uri = "https://estops.beta-eu.quartz.rme.amazon.dev/"
    redirect(f'https://{project_name}.auth.eu-west-1.amazoncognito.com/oauth2/authorize?client_id={app_client_id}&response_type=code&scope=email+openid+phone+profile&redirect_uri={redirect_uri}')


pn.route("/", create_chat_interface)
pn.route("/login", login)
'''

if __name__ == "__main__":
    pn.serve(
        create_chat_interface,
        static_dirs={'/custom_static': './custom_static'},
        start=True,
        port= 80,
        address= '0.0.0.0',
        websocket_origin="*"
    )   