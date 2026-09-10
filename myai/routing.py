"""Fast, transparent local intent routing. No inference, network or downloads."""
import re


def plan_request(body, models, media):
    prompt = body.get('prompt')
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 16000:
        raise ValueError('Enter a request of up to 16,000 characters.')
    text = prompt.lower().strip()
    # Quoted code/doc contents are never examined as routing instructions.
    create = r'\b(?:create|generate|draw|paint|make|design|render)\b'
    visual = r'\b(?:image|picture|photo|illustration|logo|wallpaper|portrait|poster)\b'
    code = bool(re.search(r'\b(?:code|python|javascript|typescript|function|bug|debug|refactor|repository|repo|unit tests?|implement|html|css|sql)\b', text))
    explaining = bool(re.search(r'^(?:how (?:do|can|does|to)|explain|what is|why|tell me how)\b', text))
    negated = bool(re.search(r'\b(?:do not|don.t|never) (?:create|generate|draw|make|edit)\b', text))
    image = not (explaining or negated) and bool(re.search(create + r'.{0,65}' + visual, text)) and not code
    edit_image = not (explaining or negated) and bool(body.get('has_image')) and bool(re.search(r'\b(?:edit|transform|restyle|recolor|remove|replace|change|background)\b', text)) and not code
    video = not (explaining or negated) and bool(re.search(create + r'.{0,45}\b(?:video|animation|clip)\b', text)) and not code
    research = bool(re.search(r'\b(?:research|search (?:the )?(?:web|internet)|look up|latest|current|today|news|browse|find sources|fact.check)\b|https?://', text))
    project = bool(re.search(r'\b(?:fix|edit|modify|refactor|implement|update|change|test|inspect|review|build)\b', text)) and (bool(body.get('project_path')) or bool(re.search(r'\b(?:my|this|the) (?:project|repo|repository|codebase|app)\b', text)))
    kind = 'video' if video else 'image' if image or edit_image else 'project' if project else 'research' if research else 'code' if code else 'chat'
    result = {'kind': kind, 'image_edit': edit_image and kind == 'image', 'model': None, 'ready': True,
              'reason': {'chat': 'Answer locally', 'code': 'Write or explain code', 'project': 'Work on a reviewed project copy', 'research': 'Read public sources and save a report', 'image': 'Create or edit an image locally', 'video': 'Create an experimental local video'}[kind]}
    if kind in ('image', 'video'):
        available = [p for p in media.get('presets', []) if p['kind'] == kind and p['ready']]
        if available:
            result['preset'] = available[0]['id']
            result['model'] = available[0]['name']
        else:
            result.update(ready=False, message=f'No ready local {kind} model/runtime was found. Install the components described in docs/STUDIO.md; no download will start automatically.')
    else:
        # Prefer a coding model for code answers; multi-step tasks benefit from the
        # general instruction model's tool-following ability on this installation.
        candidates = sorted(models, key=lambda m: ((('coder' in m['name'].lower()) != (kind == 'code')), -m.get('bytes', 0), m['name']))
        if candidates:
            result['model'] = candidates[0]['name']
        else:
            result.update(ready=False, message='Add a compatible GGUF model to models/ to answer locally.')
    if kind == 'project' and not body.get('project_path'):
        result.update(ready=False, needs_project=True, message='Choose the project folder in Project access below, then send this request again.')
    return result
