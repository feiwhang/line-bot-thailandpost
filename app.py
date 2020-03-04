import io
import re
import urllib3
import requests
import pytesseract
from PIL import Image
from flask import Flask, abort, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage

# have to disable warning due to a primitive version of ThailandPOST API
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

with open("keys/Channel_access_token.txt", "r") as file:
    channel_access_token = file.read()
with open("keys/Channel_secret.txt", "r") as file:
    channel_secret = file.read()

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


def get_token():
    url = "https://trackwebhook.thailandpost.co.th/post/api/v1/authenticate/token"
    with open("keys/thaipost_token.txt", "r") as file:
        my_token = file.read()

    headers = {'Authorization': "Token " + my_token,
               'Content-Type': 'application/json'}

    r = requests.post(url, headers=headers, verify=False)
    token = r.json()['token']

    return token


def api_track(trackcode, token):
    params = {
        "status": "all",
        "language": "TH",
        "barcode": [trackcode]
    }
    url = "https://trackapi.thailandpost.co.th/post/api/v1/track"
    headers = {'Authorization': "Token " + token,
               'Content-Type': 'application/json'}

    r = requests.post(url, headers=headers, json=params, verify=False)

    steps = r.json()['response']['items'][trackcode]
    status = 'Tracking Number: ' + trackcode
    for step in steps:
        status += '\n' + 'Status: ' + step["status_description"]
        status += '\n' + 'Location: ' + step["location"]

    return status


def extract_code(text):

    # start with E end with TH have 13 digit
    regex = r"[E]{1}[A-Z]{1}[0-9]{9}[T,H]{2}"
    trackcodes = re.findall(regex, str(text))

    return trackcodes


def status(text):
    trackcodes = extract_code(text)
    tmp_token = get_token()

    output_message = 'ผลการติดตามพัสดุ'
    if len(trackcodes) == 0:
        return "ไม่สามารถหาหมายเลขติดตามพัสดุได้ กรุณาลองใหม่อีกครั้งค่ะ"
    for trackcode in trackcodes:
        output_message += "\n" + api_track(trackcode, tmp_token)

    return output_message


def image_to_text(message_id):

    url = "https://api-data.line.me/v2/bot/message/" + message_id + "/content"
    headers = {'Authorization': "Bearer " + channel_access_token}

    r = requests.get(url, headers=headers, verify=False)
    img = Image.open(io.BytesIO(r.content))

    # get all text from the image
    text = pytesseract.image_to_string(img)

    # try to extract the tracking code
    # remove all spaces and new lines
    text = text.replace(" ", "")
    text = text.replace("\n", "")

    return text


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    input_message = event.message.text      # input message

    if input_message.startswith('track '):
        trackcodes = extract_code(input_message)
        output_message = status(trackcodes)
    else:
        output_message = "พิมคำสั่งให้ถูกต้องครับ/ค่ะ"

    message = TextSendMessage(text=output_message)  # output message
    line_bot_api.reply_message(event.reply_token, message)


@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_id = event.message.id    # message id
    tmp_token = get_token()

    text = image_to_text(message_id)
    trackcodes = extract_code(text)
    output_message = status(trackcodes)

    message = TextSendMessage(text=output_message)  # output message
    line_bot_api.reply_message(event.reply_token, message)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
