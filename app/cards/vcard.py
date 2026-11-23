def escape(value):
    return str(value).replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace(
        '\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold(line):
    """RFC 2425: fold at 75 octets without splitting UTF-8 characters."""
    parts, current, size = [], '', 0
    for char in line:
        width = len(char.encode('utf-8'))
        if size + width > 75:
            parts.append(current)
            current, size = ' ', 1
        current += char
        size += width
    return '\r\n'.join(parts + [current])


def render_vcard(content, public_url):
    lines = ['BEGIN:VCARD', 'VERSION:3.0', 'FN:' + escape(content['name']),
             'N:;' + escape(content['name']) + ';;;']
    for key, prop in [('title', 'TITLE'), ('company', 'ORG'), ('phone', 'TEL;TYPE=CELL'),
                      ('email', 'EMAIL;TYPE=INTERNET'), ('website', 'URL')]:
        if content.get(key):
            lines.append(prop + ':' + escape(content[key]))
    phones = {content.get('phone')}; emails = {content.get('email')}
    for button in content.get('buttons', []):
        if button['kind'] in ('phone','other_phone') and button['value'] not in phones:
            prop = 'TEL;TYPE=CELL' if button['kind'] == 'phone' else 'TEL;TYPE=VOICE'
            lines.append(prop + ':' + escape(button['value'])); phones.add(button['value'])
        elif button['kind'] == 'email' and button['value'] not in emails:
            lines.append('EMAIL;TYPE=INTERNET:' + escape(button['value'])); emails.add(button['value'])
    address = content.get('map', {}).get('address')
    if address: lines.append('ADR;TYPE=WORK:;;' + escape(address) + ';;;;')
    notes = [content['bio']] if content.get('bio') else []
    for button in content.get('buttons', []):
        if button['kind'] in ('phone','other_phone') and button.get('extension'):
            notes.append(f"{button['label']}: {button['value']}, добавочный {button['extension']}")
    if notes: lines.append('NOTE:' + escape('\n'.join(notes)))
    lines += ['URL:' + escape(public_url), 'END:VCARD']
    return ('\r\n'.join(fold(line) for line in lines) + '\r\n').encode('utf-8')
