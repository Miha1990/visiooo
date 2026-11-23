"""Editable catalogue versions of the public examples; no customer content."""
from copy import deepcopy
from .designs import DEFAULT, BLOCKS, validate_design

EXAMPLE_TEMPLATES = {
    'designer': ('75d4fb3d-5668-4a4f-92c2-a8070a95eb21', 'Классика · оливковый',
                 'Спокойный оливковый акцент, фото поверх обложки и лаконичные кнопки.'),
    'photographer': ('75d4fb3d-5668-4a4f-92c2-a8070a95eb22', 'Профиль · морской',
                     'Крупный портрет, выравнивание по центру и мягкие формы.'),
    'property': ('75d4fb3d-5668-4a4f-92c2-a8070a95eb23', 'Минимализм · графит',
                 'Светлый фон, книжная типографика и тонкие контурные кнопки.'),
}


def definition(slug):
    design = deepcopy(DEFAULT)
    design.update(blocks=[key for key, _ in BLOCKS], sourceId=EXAMPLE_TEMPLATES[slug][0],
                  caption='', gap=18, iconSize=22, weight=600, nameSize=30,
                  carousel={'photos': [], 'visible': 1, 'height': 220, 'autoplay': False, 'interval': 6},
                  blockStyles={'contacts': {'align': 'left'}, 'socials': {'align': 'left'}})
    if slug == 'designer':
        design.update(accent='#526C50', background='#FFFFFF', text='#233027',
                      avatarSize=96, coverHeight=160, radius=20)
    elif slug == 'photographer':
        design.update(accent='#286B76', background='#F4F6F5', text='#203437',
                      align='center', avatarSize=112, coverHeight=180, buttonShape='pill', radius=24,
                      blockStyles={'identity': {'align': 'center'}, 'bio': {'align': 'center'},
                                   'contacts': {'align': 'left'}, 'socials': {'align': 'center'}})
    else:
        design.update(accent='#695B4B', background='#FFFFFF', text='#302C28', font='serif',
                      avatarShape='rounded', avatarSize=88, coverHeight=140, radius=12,
                      nameSize=32, weight=400, buttonStyle='outline', buttonShape='rounded')
    for style in design['blockStyles'].values():
        style.setdefault('iconPosition', 'left')
    return validate_design(design)
