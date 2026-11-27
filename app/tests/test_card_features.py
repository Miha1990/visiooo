from copy import deepcopy
from datetime import datetime, timezone
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, Client
from cards.card_features import business_display, action_href, validate_features
from cards.forms import CardForm
from cards.services import save_card, publish_card
from cards.designs import DEFAULT
from tests import test_visual_editor as fixtures


class WorkingHoursTests(SimpleTestCase):
    def test_local_timezone_overnight_and_exact_closing_time(self):
        business = {'timezone':'Europe/Moscow', 'hours':[{'day':0,'open':'20:00','close':'02:00'}]}
        self.assertEqual(business_display(business, datetime(2026,11,23,18,tzinfo=timezone.utc))['status'], 'Открыто до 02:00')
        self.assertEqual(business_display(business, datetime(2026,11,23,22,tzinfo=timezone.utc))['status'], 'Открыто до 02:00')
        self.assertEqual(business_display(business, datetime(2026,11,23,23,tzinfo=timezone.utc))['status'], 'Сейчас закрыто')
        business['status'] = 'Ближайшая запись — завтра'
        self.assertEqual(business_display(business)['status'], business['status'])

    def test_actions_are_normalized_and_unsafe_urls_rejected(self):
        self.assertEqual(action_href({'kind':'phone','target':'8 (928) 909-18-17'}),'tel:+79289091817')
        self.assertEqual(action_href({'kind':'booking','target':'example.com/book'}),'https://example.com/book')
        for target in ('javascript:alert(1)', 'https://user:pass@example.com', 'https://example.com/a b'):
            with self.assertRaises(ValidationError):
                action_href({'kind':'message','target':target})
        with self.assertRaises(ValidationError):
            validate_features({'business':{'hours':[{'day':0,'open':'09:00','close':'18:00'}]*2}})


class CardFeaturesTests(TestCase):
    setUp = fixtures.VisualEditorTests.setUp

    def data(self, **values):
        return {'draft_version':self.card.draft_version, 'name':'Анна', 'template':'classic', 'accent':'#2457db',
                'work_status':'Принимаю заказы', 'work_timezone':'Europe/Moscow', 'work_0_open':'09:00',
                'work_0_close':'19:00', 'action_kind':'phone', 'action_target':'89289091817', 'motion':'on', **values}

    def test_work_schedule_is_a_separate_block_with_saved_order(self):
        import json
        form = CardForm.for_card(self.card, self.data(layout_data=json.dumps({'order':['identity','business','contacts']})))
        self.assertTrue(form.is_valid(), form.errors)
        save_card(self.user, self.card.pk, self.card.draft_version, form.content)
        self.card.refresh_from_db()
        self.assertIn('business', self.card.draft['layout']['order'])
        publish_card(self.user, self.card.pk, self.card.draft_version)
        response = Client().get(f'/c/{self.card.public_id}')
        self.assertContains(response, 'data-layout-block="business"', count=1)
        self.assertContains(response, '09:00–19:00')

    def test_form_validation_snapshot_publication_and_both_templates(self):
        form = CardForm.for_card(self.card, self.data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.content['primaryAction']['target'], '+79289091817')
        self.assertEqual(form.content['primaryAction']['label'], 'Позвонить')
        self.assertTrue(form.content['motion'])
        for designed in (False, True, 'canvas'):
            content=deepcopy(form.content)
            if designed:
                content['design']=fixtures.layout() if designed == 'canvas' else deepcopy(DEFAULT)
            save_card(self.user,self.card.pk,self.card.draft_version,content)
            self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
            response=Client().get(f'/c/{self.card.public_id}')
            self.assertContains(response, 'Принимаю заказы')
            self.assertContains(response, '09:00–19:00')
            self.assertContains(response, 'href="tel:+79289091817"')
            self.assertContains(response, 'data-primary-action')
            self.assertContains(response, 'data-work-summary', count=1)
            self.assertContains(response, 'data-card-motion="true"')
        invalid=CardForm.for_card(self.card,self.data(work_0_close=''))
        self.assertFalse(invalid.is_valid());self.assertIn('work_0_close',invalid.errors)
        invalid=CardForm.for_card(self.card,self.data(action_target='javascript:alert(1)',action_kind='booking'))
        self.assertFalse(invalid.is_valid());self.assertIn('action_target',invalid.errors)

    def test_blank_features_are_hidden_and_can_be_removed(self):
        form=CardForm.for_card(self.card,self.data())
        self.assertTrue(form.is_valid(),form.errors)
        save_card(self.user,self.card.pk,self.card.draft_version,form.content);self.card.refresh_from_db()
        blank=CardForm.for_card(self.card,self.data(work_status='',work_0_open='',work_0_close='',action_kind='',motion=''))
        self.assertTrue(blank.is_valid(),blank.errors)
        self.assertNotIn('business',blank.content);self.assertNotIn('primaryAction',blank.content)
        self.assertFalse(blank.content['motion'])
        save_card(self.user,self.card.pk,self.card.draft_version,blank.content);self.card.refresh_from_db()
        publish_card(self.user,self.card.pk,self.card.draft_version)
        response=Client().get(f'/c/{self.card.public_id}')
        self.assertNotContains(response,'data-work-summary');self.assertNotContains(response,'data-primary-action')
        self.assertContains(response,'data-card-motion="false"')
        self.assertContains(self.client.get(f'/app/cards/{self.card.pk}/edit'),'data-card-feature-fields')

    def test_legacy_edit_does_not_erase_features_or_publish_draft_early(self):
        form=CardForm.for_card(self.card,self.data())
        self.assertTrue(form.is_valid(),form.errors)
        save_card(self.user,self.card.pk,self.card.draft_version,form.content);self.card.refresh_from_db()
        publish_card(self.user,self.card.pk,self.card.draft_version)
        data=self.data();data={k:v for k,v in data.items() if not k.startswith(('work_','action_')) and k!='motion'}
        form=CardForm.for_card(self.card,data)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.content['business'],self.card.draft['business'])
        form.content['business']['status']='Пока только черновик'
        save_card(self.user,self.card.pk,self.card.draft_version,form.content)
        response=Client().get(f'/c/{self.card.public_id}')
        self.assertContains(response,'Принимаю заказы');self.assertNotContains(response,'Пока только черновик')
