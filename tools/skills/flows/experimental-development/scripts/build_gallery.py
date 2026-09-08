#!/usr/bin/env python3
"""Build one local-file-friendly static gallery from numbered generation folders."""
import argparse
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import quote


def read_json(path):
    if path.is_symlink():
        raise ValueError(f"Implicit gallery input cannot be a symlink: {path}")
    if not path.exists():
        return {}
    try:
        result = json.loads(path.read_text())
    except (ValueError, OSError) as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(result, dict):
        raise ValueError(f"Expected an object in {path}")
    return result


def note(folder, names):
    for name in names:
        path = folder / name
        if path.is_symlink():
            raise ValueError(f"Implicit gallery note cannot be a symlink: {path}")
        if path.is_file():
            return path.read_text().strip()
    return ""


def experiment(config, folder):
    value = config.get('experiment')
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"Experiment must be an object: {folder}")
    task_id = value.get('id', '')
    if not isinstance(task_id, str) or not re.fullmatch(r'TASK-\d+(?:\.\d+)*', task_id):
        raise ValueError(f"Expected experiment ID TASK-N or TASK-N.N: {folder}")
    for field in ('title', 'status', 'body', 'task_file'):
        if field in value and not isinstance(value[field], str):
            raise ValueError(f"Experiment {field} must be a string: {folder}")
    source = None
    if value.get('task_file'):
        path = Path(value['task_file'])
        if not path.is_absolute() or path.suffix.lower() != '.md':
            raise ValueError(f"Experiment task_file must be an absolute Markdown path: {folder}")
        source = path.resolve()
    body = value.get('body')
    if body is None:
        if source is None or not source.is_file():
            raise ValueError(f"Experiment needs inline body or a readable task_file: {folder}")
        body = source.read_text(encoding='utf-8')
    return {'id': task_id, 'title': value.get('title', ''),
            'status': value.get('status', ''), 'body': body,
            'source': source.as_uri() if source else '',
            'generation_title': 'Generation E' + task_id.removeprefix('TASK-')}


def collect(root):
    folders = sorted((p for p in root.iterdir() if p.is_dir() and re.fullmatch(r"generation-\d+", p.name)),
                     key=lambda p: int(p.name.split('-')[-1]))
    records = []
    previous_outgoing = ""
    for folder in folders:
        if folder.is_symlink():
            raise ValueError(f"Generation directory cannot be a symlink: {folder}")
        config = read_json(folder / 'gallery.json')
        task = experiment(config, folder)
        incoming = config.get('incoming', note(folder, ['incoming.md'])) or previous_outgoing
        feedback = note(folder, ['feedback.md'])
        if feedback:
            incoming = (incoming + '\n\nUser feedback:\n' + feedback).strip()
        outgoing = config.get('outgoing', note(folder, ['next-technique.md', 'recommendations.md']))
        if not isinstance(incoming, str) or not isinstance(outgoing, str):
            raise ValueError(f"Recommendation text must be strings: {folder}")
        images = config.get('images')
        if images is None:
            for filename in ['settings.json', 'pass.json']:
                data = read_json(folder / filename)
                images = data.get('preferred_images', data.get('preferred'))
                if isinstance(images, list):
                    break
            if not isinstance(images, list):
                images = sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'})
        if not isinstance(images, list):
            raise ValueError(f"Image list must be an array: {folder}")
        pictures = []
        for entry in images:
            src = entry if isinstance(entry, str) else entry.get('src', '')
            path = folder / src
            if not path.suffix:
                path = path.with_suffix('.png')
            if not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError(f"Image escapes its generation: {src}")
            if not path.is_file():
                continue  # An in-progress pass may list images still rendering.
            caption = path.stem.replace('-', ' ') if isinstance(entry, str) else entry.get('caption', path.stem)
            pictures.append({'src': quote(path.relative_to(root).as_posix(), safe='/'), 'caption': caption})
        records.append({'id': folder.name, 'title': task['generation_title'] if task else config.get('title', folder.name.replace('-', ' ').title()),
                        'experiment': task,
                        'status': config.get('status', 'Images available' if pictures else 'Awaiting images'),
                        'incoming': incoming or 'No incoming recommendations recorded.',
                        'outgoing': outgoing or 'Recommendations pending or not recorded.', 'images': pictures})
        previous_outgoing = outgoing
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    records = collect(root)
    template = (Path(__file__).resolve().parent.parent / 'assets/gallery.html').read_text()
    payload = json.dumps(records, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    output = template.replace('__GENERATION_DATA__', payload)
    with tempfile.NamedTemporaryFile(mode='w', dir=root, prefix='.gallery-', suffix='.html', delete=False) as out:
        out.write(output)
        temporary = Path(out.name)
    destination = root / 'galleries.html'
    temporary.replace(destination)
    print(f"{destination}: {len(records)} generations, {sum(len(r['images']) for r in records)} images")


if __name__ == '__main__':
    main()
