from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from cards.models import CardAddress
from cards.services import create_card, publish_card, save_card, Conflict
from tests import test_button_builder as fixtures


class CardAddressTests(TestCase):
    setUp = fixtures.ButtonBuilderTests.setUp
    payload = fixtures.ButtonBuilderTests.payload

    def test_change_requires_confirmation_and_updates_public_url_and_qr(self):
        publish_card(self.user,self.card.pk,1)
        old = self.card.public_id
        old_qr = self.client.get(f'/app/cards/{self.card.pk}/qr.png').content
        data = self.payload([])
        data.update(card_address='my-business')
        response = self.client.post(f'/app/cards/{self.card.pk}/edit',data)
        self.assertEqual(response.status_code,422)
        self.card.refresh_from_db();self.assertEqual(self.card.public_id,old)
        data['address_confirmed']='true'
        response = self.client.post(f'/app/cards/{self.card.pk}/edit',data,HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['address'],'my-business')
        self.assertTrue(response.json()['public_url'].endswith('/c/my-business'))
        self.assertEqual(Client().get('/c/my-business').status_code,200)
        self.assertEqual(Client().get('/c/'+old).status_code,404)
        self.assertNotEqual(self.client.get(f'/app/cards/{self.card.pk}/qr.png').content,old_qr)
        self.assertTrue(CardAddress.objects.filter(address=old,card=self.card).exists())

    def test_previous_address_is_not_available_to_another_card(self):
        save_card(self.user,self.card.pk,1,self.card.draft,address='permanent-name',address_confirmed=True)
        save_card(self.user,self.card.pk,2,self.card.draft,address='new-name',address_confirmed=True)
        other = create_card(self.user)
        with self.assertRaises(ValidationError):
            save_card(self.user,other.pk,1,other.draft,address='permanent-name',address_confirmed=True)
        other.refresh_from_db();self.assertEqual(other.draft_version,1)

    def test_availability_is_owner_only_and_checks_format_and_existing_cards(self):
        url=f'/app/cards/{self.card.pk}/address'
        self.assertEqual(Client().get(url,{'address':'free-name'}).status_code,302)
        self.assertTrue(self.client.get(url,{'address':'FREE-name'}).json()['available'])
        self.assertEqual(self.client.get(url,{'address':'FREE-name'}).json()['address'],'free-name')
        for value in ['ab','-name','name-','../path','русский','a'*41]:
            self.assertFalse(self.client.get(url,{'address':value}).json()['available'])
        other = create_card(self.user)
        self.assertFalse(self.client.get(url,{'address':other.public_id}).json()['available'])
        self.assertTrue(self.client.get(url,{'address':self.card.public_id}).json()['available'])

    def test_stale_save_cannot_change_address_and_invalid_content_rolls_back_reservation(self):
        with self.assertRaises(Conflict):
            save_card(self.user,self.card.pk,99,self.card.draft,address='fresh-name',address_confirmed=True)
        with self.assertRaises(ValidationError):
            save_card(self.user,self.card.pk,1,{**self.card.draft,'accent':'#ffffff'},address='fresh-name',address_confirmed=True)
        self.assertFalse(CardAddress.objects.filter(address='fresh-name').exists())
        self.card.refresh_from_db();self.assertEqual(self.card.draft_version,1)

    def test_customer_can_choose_button_colour_and_header_has_no_caption(self):
        self.user.is_staff=False;self.user.save(update_fields=['is_staff'])
        data=self.payload([{'kind':'link','label':'Сайт','value':'example.com'}])
        data['accent']='#683db0'
        self.assertEqual(self.client.post(f'/app/cards/{self.card.pk}/edit',data).status_code,303)
        self.card.refresh_from_db();self.assertEqual(self.card.draft['accent'],'#683db0')
        publish_card(self.user,self.card.pk,self.card.draft_version)
        response=Client().get('/c/'+self.card.public_id)
        self.assertContains(response,'--accent:#683db0')
        self.assertNotContains(response,'ПРИЯТНО ПОЗНАКОМИТЬСЯ')
