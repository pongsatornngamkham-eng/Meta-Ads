import httpx
import pytest
from app.report_delivery import TelegramSender, TelegramSettings, DeliveryError

TOKEN='12345:FAKE_TELEGRAM_REPORT_TEST_ONLY'


def sender(send_response=None, wrong_bot=False, private=True):
    calls=[]
    def respond(request):
        calls.append(request)
        if request.url.path.endswith('/getMe'):return httpx.Response(200,json={'ok':True,'result':{'is_bot':True,'username':'wrongbot' if wrong_bot else 'Adscopefatherbot'}})
        if request.url.path.endswith('/getChat'):return httpx.Response(200,json={'ok':True,'result':{'id':99,'type':'private' if private else 'group'}})
        return send_response(request) if send_response else httpx.Response(200,json={'ok':True,'result':{'message_id':1,'chat':{'id':99}}})
    return TelegramSender(TelegramSettings(TOKEN,99),httpx.Client(transport=httpx.MockTransport(respond))),calls


def test_sender_validates_private_destination_and_sends_plain_text():
    s,calls=sender()
    assert s.send('ทดสอบ report')==1
    assert len(calls)==3 and all(c.method=='POST' and c.url.host=='api.telegram.org' for c in calls)
    import json
    body=json.loads(calls[-1].content)
    assert body['chat_id']==99 and 'parse_mode' not in body
    assert TOKEN not in repr(s.settings)


@pytest.mark.parametrize('kwargs',[{'wrong_bot':True},{'private':False}])
def test_destination_mismatch_never_sends(kwargs):
    s,calls=sender(**kwargs)
    with pytest.raises(DeliveryError):s.send('report')
    assert all(not r.url.path.endswith('/sendMessage') for r in calls)


def test_unknown_delivery_is_not_retried_or_leaked():
    def fail(request):raise httpx.ReadTimeout('raw token '+TOKEN,request=request)
    s,calls=sender(send_response=fail)
    with pytest.raises(DeliveryError) as error:s.send('report')
    assert error.value.uncertain and TOKEN not in str(error.value)
    assert len(calls)==3


def test_http_errors_and_unconfirmed_destination():
    s,_=sender(send_response=lambda r:httpx.Response(500,json={'description':TOKEN}))
    with pytest.raises(DeliveryError) as error:s.send('report')
    assert error.value.uncertain and TOKEN not in str(error.value)
    s,_=sender(send_response=lambda r:httpx.Response(200,json={'ok':True,'result':{'message_id':1,'chat':{'id':88}}}))
    with pytest.raises(DeliveryError) as error:s.send('report')
    assert error.value.uncertain
