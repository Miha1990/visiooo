"""Editable catalogue versions of the public examples; no customer content."""
from copy import deepcopy
from .designs import DEFAULT, BLOCKS, validate_design

EXAMPLE_TEMPLATES = {
    'designer': ('75d4fb3d-5668-4a4f-92c2-a8070a95eb21', 'Форма · светлый редакционный',
                 'Тёплая бумажная палитра, выразительное имя и портрет рядом с описанием.'),
    'photographer': ('75d4fb3d-5668-4a4f-92c2-a8070a95eb22', 'Кадр · тёмный атмосферный',
                     'Большая фотообложка, глубокий тёмный фон и собранная композиция по центру.'),
    'property': ('75d4fb3d-5668-4a4f-92c2-a8070a95eb23', 'Адрес · деловой минимализм',
                 'Имя и портрет в одной строке, аккуратные действия и фото в завершении.'),
}


def definition(slug):
    design = deepcopy(DEFAULT)
    design.update(blocks=[key for key, _ in BLOCKS], sourceId=EXAMPLE_TEMPLATES[slug][0],
                  caption='', gap=14, iconSize=22, weight=600, nameSize=30, socialMode='icons',socialLabel='',buttonColumns=2,
                  carousel={'photos': [], 'visible': 1, 'height': 220, 'autoplay': False, 'interval': 6},
                  blockStyles={'contacts': {'align': 'left'}, 'socials': {'align': 'left'}})
    if slug == 'designer':
        design.update(presetStyle='forma',accent='#3F5745', background='#F8F5EF', text='#25372C',font='serif',
                      avatarShape='rounded',avatarSize=84, coverHeight=108, radius=24,nameSize=34,weight=400)
    elif slug == 'photographer':
        design.update(presetStyle='frame',accent='#275E64', background='#122B30', text='#F2F5F0',
                      align='center', avatarSize=88, coverHeight=230, buttonShape='pill', radius=24,
                      blockStyles={'identity': {'align': 'center'}, 'bio': {'align': 'center'},
                                   'contacts': {'align': 'left'}, 'socials': {'align': 'center'}})
    else:
        design.update(presetStyle='estate',accent='#263D51', background='#FFFFFF', text='#233345',font='ui',
                      blocks=['avatar','identity','bio','save','contacts','socials','cover','carousel','video','document','map'],
                      avatarShape='rounded', avatarSize=76, coverHeight=132, radius=24,
                      nameSize=29,weight=600,buttonShape='rounded')
    for style in design['blockStyles'].values():
        style.setdefault('iconPosition', 'left')
    return validate_design(design)
