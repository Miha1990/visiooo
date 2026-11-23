from itertools import zip_longest
from django import forms


class LinkButtonsWidget(forms.Widget):
    template_name = 'cards/widgets/link_buttons.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        rows = []
        for line in (value or '').splitlines():
            label, separator, url = line.partition('|')
            rows.append({'label': label.strip(), 'url': url.strip() if separator else ''})
        # One new row is always available. Without JavaScript all ten are editable.
        rows += [{'label': '', 'url': ''} for _ in range(max(0, 10-len(rows)))]
        context['widget']['rows'] = rows
        return context

    def value_from_datadict(self, data, files, name):
        if name+'_label' not in data and name+'_url' not in data:
            return data.get(name, '')  # Older clients still submit the text format.
        labels = data.getlist(name+'_label')
        urls = data.getlist(name+'_url')
        return '\n'.join(f'{label.strip()} | {url.strip()}'
                         for label, url in zip_longest(labels, urls, fillvalue='')
                         if label.strip() or url.strip())

    def id_for_label(self, id_):
        return id_+'_label_1'
