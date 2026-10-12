"""Explicit track selection and predictable channel/codec policy."""
import re


def selection_numbers(value):
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError('Tonspuren: Nummern wie 1, 3 oder 2-4 eingeben.')
    numbers = set()
    for entry in value.split(','):
        match = re.fullmatch(r'\s*(\d+)(?:\s*-\s*(\d+))?\s*', entry)
        if not match:
            raise ValueError('Tonspuren: Nummern wie 1, 3 oder 2-4 eingeben.')
        first, last = int(match[1]), int(match[2] or match[1])
        if not 1 <= first <= last <= 1000:
            raise ValueError('Tonspuren: Aufsteigende Nummern von 1 bis 1000 verwenden.')
        numbers.update(range(first, last+1))
    return sorted(numbers)


def sources(info):
    return [s for s in info['streams'] if s.get('codec_type') == 'audio']


def selected(info, options):
    tracks = sources(info)
    if options.audio_tracks == 'none':
        return []
    if options.audio_tracks == 'all':
        return tracks
    numbers = selection_numbers(options.audio_selection)
    if any(n > len(tracks) for n in numbers):
        raise ValueError(f'Tonspuren: Gewählte Spur fehlt; die Quelle enthält {len(tracks)} Audiospur(en).')
    return [tracks[n-1] for n in numbers]


def channels(track, options):
    return 2 if options.audio_channels == 'stereo' else track.get('channels')


def codec(track, options):
    if options.target == 'bd3d':
        return 'pcm_bluray'
    if options.audio_format == 'aac' or options.audio_channels == 'stereo':
        return 'aac'
    return 'flac' if track.get('codec_name') == 'pcm_bluray' else track.get('codec_name')


def validate(info, options):
    tracks = selected(info, options)
    if options.container == 'mp4':
        unsupported = {codec(s, options) for s in tracks} - {'aac', 'mp3', 'ac3', 'eac3', 'alac'}
        if unsupported:
            raise ValueError('Ton passt nicht zum MP4-Ausgabeformat ('+', '.join(sorted(unsupported))+
                             '). Unter Tonoptionen AAC wählen oder MKV verwenden.')
    if any(not isinstance(s.get('channels'), int) or not 1 <= s['channels'] <= 8 for s in tracks):
        raise ValueError('Ton: Verlässliche Kanalzahl von 1 bis 8 erforderlich.')
    return tracks


def summary(info, options, translate=None):
    t = translate or (lambda text:text)
    tracks = selected(info, options)
    if not tracks:
        return t('Ton: Ohne Ton' if sources(info) else 'Ton: Quelle enthält keinen Ton')
    descriptions = []
    all_tracks = sources(info)
    for track in tracks:
        number = all_tracks.index(track)+1
        tags = track.get('tags', {})
        identity = ' · '.join(str(tags[k]) for k in ('language', 'title') if tags.get(k))
        descriptions.append(t('Spur {0}: {1} → {2} · {3} Kanäle').format(
            number,track.get('codec_name','?').upper(),codec(track,options).upper(),channels(track,options))
            +(f' · {identity}' if identity else ''))
    return t('Ton: ')+'; '.join(descriptions)


def arguments(info, options, input_number):
    tracks = selected(info, options)
    result = []
    for track in tracks:
        result += ['-map', f"{input_number}:{track['index']}"]
    for number, track in enumerate(tracks):
        output_codec = codec(track, options)
        encode = (options.audio_format == 'aac' or options.audio_channels == 'stereo'
                  or track.get('codec_name') == 'pcm_bluray')
        result += [f'-c:a:{number}', output_codec if encode else 'copy']
        if output_codec == 'aac' and encode:
            bitrate = {1: 160, 2: 320, 3: 384, 4: 448, 5: 512, 6: 640, 7: 704, 8: 768}[channels(track, options)]
            result += [f'-b:a:{number}', str(bitrate)+'k']
            if options.audio_channels == 'stereo':
                result += [f'-ac:a:{number}', '2']
        elif output_codec == 'flac' and track.get('codec_name') == 'pcm_bluray':
            result += [f'-sample_fmt:a:{number}', 's32', f'-bits_per_raw_sample:a:{number}', '24']
        for tag in ('language', 'title'):
            value = track.get('tags', {}).get(tag)
            if isinstance(value, str):
                result += [f'-metadata:s:a:{number}', tag+'='+value]
    return result
