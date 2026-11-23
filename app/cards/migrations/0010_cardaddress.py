from django.db import migrations, models
import django.db.models.deletion


def reserve_existing(apps, schema_editor):
    Card = apps.get_model('cards', 'Card')
    Address = apps.get_model('cards', 'CardAddress')
    Address.objects.bulk_create([Address(card_id=pk, address=address)
        for pk, address in Card.objects.values_list('pk', 'public_id')], batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [('cards', '0009_carddailyviews')]
    operations = [
        migrations.CreateModel(name='CardAddress', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('address', models.CharField(max_length=40, unique=True)),
            ('card', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reserved_addresses', to='cards.card'))]),
        migrations.RunPython(reserve_existing, migrations.RunPython.noop),
    ]
