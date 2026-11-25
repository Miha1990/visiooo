import json
from copy import deepcopy
from django.test import SimpleTestCase, TestCase, Client
from cards.validation import VALIDATOR
from cards.forms import CardForm
from cards.services import save_card, publish_card
from tests import test_visual_editor as fixtures


def sizes():
    return {'order':['cover','avatar','identity','bio','save','contacts','carousel','daisy'], 'buttonOrder':[2,0,1],
            'blocks':{'identity':{'width':100,'height':0},'carousel':{'width':100,'height':240}},
            'buttons':{str(i):{'width':25,'shape':'square','radius':12} for i in range(4)},
            'carousel':{'visible':1,'height':240,'fit':'contain','aspect':'custom'}}


class LayoutSchemaTests(SimpleTestCase):
    def test_rejects_arbitrary_css_coordinates_and_unbounded_sizes(self):
        base={'schemaVersion':1,'name':'Анна','template':'classic','accent':'#2457db','links':[]}
        self.assertFalse(list(VALIDATOR.iter_errors({**base,'layout':sizes()})))
        for layout in ({'blocks':{'identity':{'width':900}}}, {'blocks':{'identity':{'height':-1}}},
                       {'blocks':{'identity':{'position':'absolute'}}}, {'blocks':{'unknown':{'width':50}}},
                       {'buttons':{'30':{'width':50}}}, {'carousel':{'visible':100}}, {'carousel':{'fit':'url(javascript:1)'}},
                       {'order':['bio','bio']}, {'order':['unknown']}, {'buttonOrder':[0,0]}, {'buttonOrder':[30]}):
            self.assertTrue(list(VALIDATOR.iter_errors({**base,'layout':layout})),layout)


class ResponsiveLayoutTests(TestCase):
    setUp=fixtures.VisualEditorTests.setUp

    def data(self,**values):
        return {'draft_version':self.card.draft_version,'name':'Анна','template':'classic','accent':'#2457db',
                'builder_mode':'tiles','button_items':json.dumps([{'kind':'phone','label':'Позвонить','value':'89289091817'}]),
                'layout_data':json.dumps(sizes()),'daisy_data':json.dumps({'label':'Связаться','items':[
                    {'kind':'telegram','label':'Личный Telegram','value':'@anna'},
                    {'kind':'email','label':'Почта','value':'anna@example.test'}]}),**values}

    def test_customer_can_save_publish_and_reload_responsive_sizes_and_daisy(self):
        response=self.client.post(f'/app/cards/{self.card.pk}/edit',self.data())
        self.assertEqual(response.status_code,303)
        self.card.refresh_from_db()
        self.assertEqual(self.card.draft['layout'],sizes())
        self.assertEqual(self.card.draft['daisy']['items'][0]['value'],'https://t.me/anna')
        form=CardForm.for_card(self.card)
        self.assertEqual(json.loads(form['layout_data'].value()),sizes())
        publish_card(self.user,self.card.pk,self.card.draft_version)
        for designed in (False,True):
            if designed:
                content=deepcopy(self.card.draft);content['design']=fixtures.layout()
                save_card(self.user,self.card.pk,self.card.draft_version,content);self.card.refresh_from_db()
                publish_card(self.user,self.card.pk,self.card.draft_version)
            response=Client().get(f'/c/{self.card.public_id}')
            self.assertContains(response,'data-card-layout')
            self.assertContains(response,'class="daisy-center-icon"')
            self.assertContains(response,'class="daisy-center-label">Связаться</span>')
            self.assertContains(response,'href="https://t.me/anna"')
            self.assertContains(response,'aria-label="Почта"')
            self.assertNotContains(response,'size-handle')
        self.assertEqual(self.client.get(f'/app/cards/{self.card.pk}/design').status_code,200)

    def test_empty_daisy_hidden_and_legacy_save_preserves_layout(self):
        form=CardForm.for_card(self.card,self.data())
        self.assertTrue(form.is_valid(),form.errors)
        save_card(self.user,self.card.pk,self.card.draft_version,form.content);self.card.refresh_from_db()
        data=self.data();data.pop('layout_data');data['daisy_data']='{}'
        form=CardForm.for_card(self.card,data)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.content['layout'],sizes());self.assertNotIn('daisy',form.content)
        save_card(self.user,self.card.pk,self.card.draft_version,form.content);self.card.refresh_from_db()
        publish_card(self.user,self.card.pk,self.card.draft_version)
        self.assertNotContains(Client().get(f'/c/{self.card.public_id}'),'data-daisy-toggle')

    def test_invalid_layout_and_daisy_are_not_saved(self):
        for extra in ({'layout_data':'[]'}, {'layout_data':'{"blocks":{"bio":{"width":999}}}'},
                      {'daisy_data':json.dumps({'label':'Контакты','items':[{'kind':'link','label':'Вредная','value':'javascript:alert(1)'}]})},
                      {'daisy_data':json.dumps({'label':'Контакты','items':[{'kind':'phone','label':'Звонок','value':'+79289091817'}]*9})}):
            form=CardForm.for_card(self.card,self.data(**extra))
            self.assertFalse(form.is_valid(),extra)
