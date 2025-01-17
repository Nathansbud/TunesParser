import argparse
import itertools
import re

from datetime import datetime
from enum import Enum
from subprocess import Popen, PIPE
from typing import List, Union

from simple_term_menu import TerminalMenu

ESC = "\033"
DEFAULT = "\033[0m"
class Colors(Enum):
    BLACK = "0"
    RED = "1"
    GREEN = "2"
    YELLOW = "3"
    BLUE = "4"
    MAGENTA = "5"
    CYAN = "6"
    WHITE = "7"

def rgb(text: str, rgb_triple: tuple) -> str:
    return f"\033[38;2;{rgb_triple[0]};{rgb_triple[1]};{rgb_triple[2]}m{text}{DEFAULT}"

def cc(text: str, color_code: int) -> str:
    return f"\033[38;5;{color_code}m{text}{DEFAULT}"

def color(text, foreground=None, background=None):
    return f"\033[{('3' + foreground.value + ';') if foreground else ''}{('4' + background.value + ';') if background else ''}1m{text}{DEFAULT}"

def col(text, c, background):
    if not background: return color(text, c)
    else: return color(text, None, c)

def black(text, bg=False): return col(text, Colors.BLACK, bg)
def red(text, bg=False): return col(text, Colors.RED, bg)
def green(text, bg=False): return col(text, Colors.GREEN, bg)
def yellow(text, bg=False): return col(text, Colors.YELLOW, bg)
def blue(text, bg=False): return col(text, Colors.BLUE, bg)
def magenta(text, bg=False): return col(text, Colors.MAGENTA, bg)
def cyan(text, bg=False): return col(text, Colors.CYAN, bg)
def white(text, bg=False): return col(text, Colors.WHITE, bg)
def bold(text): return color(text)
def rainbow(text, bg=False): 
    return "".join([
        f"{col(l, c if not bg else None, c if bg else None)}" 
        for l, c in zip(text, itertools.cycle(list(Colors)[1:-1]))
    ])

        
def call_applescript(script):
    p = Popen(['osascript'], stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    stdout, stderr = p.communicate(script)
    return {"output": stdout, "error": stderr, "code": p.returncode}

def get_share_link(track, apple=False):
    # this depends on the shortcut used here https://www.icloud.com/shortcuts/54fcecba0c614f97ab2d664b6ea21450,
    # which uses the iTunes Search API to get back an Apple Music track; not guaranteed to continue working on 
    # future macOS versions (and will not work for Windows)
    
    # copy the passed in track URI to a URL
    process = Popen(['pbcopy'], env={'LANG': 'en_US.UTF-8'}, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    _, procerr = process.communicate(bytes(track.encode('UTF-8')))

    if apple:
        p = Popen(['shortcuts', 'run', 'spotify-to-apple-music-link'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        return {"link": stdout, "error": stderr,"code": p.returncode}

    return {"link": track, "error": procerr, "code": process.returncode}

def get_vocal_paths():
    get_tracks = """
    tell application "iTunes"
        set vocalPaths to (get location of (every track in library playlist 1 whose (comment is "Vocal")))
        repeat with i from 1 to (count vocalPaths)
            set item i of vocalPaths to (POSIX path of item i of vocalPaths)
        end repeat
        set vocalPOSIX to vocalPaths
    end tell
    """
    return [f"/{s.lstrip('/')}".strip() for s in call_applescript(get_tracks)['output'].split(", /")]

def get_current_track():
    split_on =  "--------"
    get_current = f"""
		if application "Spotify" is running then
			tell application "Spotify"
                set theTrack to current track
                copy (name of theTrack as text) & "{split_on}" & (artist of theTrack as text) & "{split_on}" & (album of theTrack as text) to stdout
			end tell            
		end if
    """    
    
    current_track = call_applescript(get_current).get('output').strip().split(split_on)
    return {"title": current_track[0], "artist": current_track[1], "album": current_track[2]} if len(current_track) == 3 else None

def send_message_to_user(contact, msg):
    send_to_user = f"""
        tell application "Messages"
	        set targetService to 1st account whose service type = iMessage
	        set targetCell to participant "{contact}" of targetService
	        send "{msg}" to targetCell
        end tell
    """

    return call_applescript(send_to_user)

def remove_after(inp, endings=None, regex_endings=None):
    if regex_endings:
        for r in regex_endings: 
            inp = re.split(r, inp)[0]

    if endings:
        for ending in endings:
            if ending in inp: inp = inp.split(ending)[0].strip()

    return inp

def remove_remaster(inp):
    return remove_after(
        inp, 
        endings=[
            ' (Expanded', 
            ' (Deluxe', 
            ' (Original Mono', 
            ' (Remastered', 
            ' (Bonus', 
            ' (Legacy Edition', 
            ' (Super Deluxe Edition',
            ' (Special Edition',
            ' ['
        ], 
        regex_endings=[
            r'\s\(\d{4} Remaster',
            r'Remastered\s\d{4}',
            r'\(\d+(.*?) Anniversary(.*?)Edition'
        ]
    )

def dropdown(options: dict):
    # options contains k-v pairs
    o_keys = list(options.keys())
    select = TerminalMenu(o_keys)
    selected = select.show()
    if selected is not None: 
        return o_keys[selected], selected
    
    return None, None

def album_format(alb: dict, use_color=True):
    alb_o = alb.get('album', alb)
    
    if not isinstance(alb_o, str):
        alb_name = alb_o.get('name')
        alb_artist = ', '.join(artist.get('name') for artist in alb_o.get('artists', []))
    else:
        alb_name = alb.get('album')
        alb_artist = alb.get('artist')

    if use_color:
        return f"{color(alb_name, Colors.CYAN)} by {color(alb_artist, Colors.YELLOW)}"
    else:
        return f"{alb_name} by {alb_artist}"

def track_format(track: dict, use_color=True, album=False): 
    track_name = track.get('name')
    track_artist = ', '.join([artist.get('name') for artist in track.get('artists', [])]) if not track.get('artist') else track.get('artist')
    alb_name = track.get('album', {}).get('name') if type(track.get('album')) != str else track.get('album')

    if use_color:
        if not album or not alb_name:
            return f"{color(track_name, Colors.GREEN)} by {color(track_artist, Colors.YELLOW)}" 
        elif alb_name:
            return f"{color(track_name, Colors.GREEN)} by {color(track_artist, Colors.YELLOW)} ({cyan(alb_name)})" 
    else:
        if not album or not alb_name:
            return f"{track_name} by {track_artist}"
        elif alb_name:
            return f"{track_name} by {track_artist} ({alb_name})"

def extract_id(raw: str):
    raw = raw.strip()
    
    if raw.startswith('http'):
        idx = raw.split("/")[-1].split("?")[0]
    else:
        idx = raw if ':' not in raw else raw[raw.rindex(':')+1:]

    return (idx, True) if 'album' in raw else (idx, False)

class SongException(Exception): pass
class SongParser(argparse.ArgumentParser):
    def error(self, msg):
        raise SongException("Invalid track specifier!")

def timestamp(ms): 
    secs, mils = divmod(ms, 1000)
    mins, secs = divmod(secs, 60)
    return (f'{int(mins)}:{int(secs):02d}')

def time_progress(curr, total, paren=False):
    return ('(' * paren) + f"{bold(timestamp(curr))} / {bold(timestamp(total))}" + (')' * paren)

def iso_or_datetime(iso_or_datetime: Union[str, datetime]):
    if isinstance(iso_or_datetime, str): 
        return datetime.fromisoformat(iso_or_datetime)
    elif isinstance(iso_or_datetime, datetime):
        return iso_or_datetime
    
    return None

def flatten(nested):
    return [item for sublist in nested for item in sublist]