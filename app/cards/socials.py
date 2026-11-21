SOCIAL_NETWORKS = (
    ('instagram', 'Инстаграм', 'https://www.instagram.com/username/'),
    ('threads', 'Тредс', 'https://www.threads.com/@username'),
    ('telegram', 'Телеграм', 'https://t.me/username'),
    ('vk', 'ВКонтакте', 'https://vk.com/username'),
    ('ok', 'Одноклассники', 'https://ok.ru/profile/123456789'),
    ('max', 'Макс', 'https://max.ru/username'),
    ('avito', 'Авито', 'https://www.avito.ru/user/username'),
)


def social_links(content):
    values = content.get('socials', {})
    links = [{'key': key, 'label': label, 'url': values[key]} for key, label, _ in SOCIAL_NETWORKS if values.get(key)]
    if content.get('website'):
        links.append({'key': 'website', 'label': 'Сайт', 'url': content['website']})
    return links
