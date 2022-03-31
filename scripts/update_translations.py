#!/usr/bin/env python3

import re
import subprocess
from pathlib import Path


TRANS_DIR = Path('po')
TRANS_TEMPLATE = TRANS_DIR / 'gajim_plugins.pot'
REPO_DIR = Path.cwd()
TRANSLATABLE_FILES = [
    '*.py',
    '*.ui',
]


if not TRANS_DIR.exists():
    exit('Execute this script from the root dir')


def template_is_equal(old_template_path: Path, new_template: str) -> bool:
    with open(old_template_path, 'r') as f:
        old_template = f.read()

    pattern = r'"POT-Creation-Date: .*\n"'

    old_template = re.sub(pattern, '', old_template, count=1)
    new_template = re.sub(pattern, '', new_template, count=1)

    return old_template == new_template


def update_translation_template() -> bool:
    paths: list[Path] = []
    for file_path in TRANSLATABLE_FILES:
        paths += list(REPO_DIR.rglob(file_path))

    cmd = [
        'xgettext',
        '-o', '-',
        '-c#',
        '--from-code=utf-8',
        '--keyword=Q_',
        '--no-location',
        '--sort-output',
        '--package-name=Gajim Plugins'
    ]

    for path in paths:
        cmd.append(str(path))

    result = subprocess.run(cmd,
                            cwd=REPO_DIR,
                            text=True,
                            check=True,
                            capture_output=True)

    template = result.stdout

    if (TRANS_TEMPLATE.exists() and
            template_is_equal(TRANS_TEMPLATE, template)):
        # No new strings were discovered
        return False

    with open(TRANS_TEMPLATE, 'w') as f:
        f.write(template)
    return True


def update_translation_files() -> None:
    for file in TRANS_DIR.glob('*.po'):
        subprocess.run(['msgmerge',
                        '-U',
                        '--sort-output',
                        str(file),
                        TRANS_TEMPLATE],
                       cwd=REPO_DIR,
                       check=True)


update_translation_template()
update_translation_files()
