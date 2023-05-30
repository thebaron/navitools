#! /usr/bin/python3

import os
import re
import sqlite3
import sys

DEBUG = False

# path to the navdrome sqlite3 database
DATABASE_PATH="/var/lib/navidrome/data/navidrome.db"


def findit(db, artist, album, title):
    """
        This function attempts to look up a song in the navidrome database by
        artist, album and title.  It tries a few different combinations of
        artist and title to try to find a match.  If it finds a match, it
        returns the path to the file.  If it does not find a match, it returns
        a list of potential matches.
    """

    cu = db.cursor()

    artist = artist.lower()
    album = album.lower()
    title = title.lower()
    artist_no_the = re.sub(r"^(the|el|la|los|las|le|les|os|as|o|a) ", "", artist)
    title_no_parens = re.sub(r"\s\(.*\)", "", title)

    # Try title, album and artist match first.
    rows = cu.execute("SELECT id, path FROM media_file WHERE title = ? COLLATE NOCASE AND album = ? COLLATE NOCASE AND artist = ? COLLATE NOCASE", (title, album, artist))
    r = rows.fetchone()
    if r:
        return r[1]
    if DEBUG:
        print(f"# tried title={title} album={album} artist={artist}")

    # Try title and artist, next
    rows = cu.execute("SELECT id, path FROM media_file WHERE title = ? COLLATE NOCASE AND artist = ? COLLATE NOCASE", (title, artist))
    r = rows.fetchone()
    if r:
        return r[1]
    if DEBUG:
        print(f"# tried title={title} artist={artist}")

    # If the no-article artist differs (e.g. The Police vs Police) - try that
    if artist != artist_no_the:
        rows = cu.execute("SELECT id, path FROM media_file WHERE title = ? COLLATE NOCASE AND artist = ? COLLATE NOCASE", (title, artist_no_the))
        r = rows.fetchone()
        if r:
            return r[1]
        if DEBUG:
            print(f"# tried title={title} artist={artist_no_the}")

    # Some titles have (feat. xyzpdq) or (50th Anniversary) - so try it without those
    if title != title_no_parens:
        rows = cu.execute("SELECT id, path FROM media_file WHERE title = ? COLLATE NOCASE AND artist = ? COLLATE NOCASE", (title_no_parens, artist))
        r = rows.fetchone()
        if r:
            return r[1]
        if DEBUG:
            print(f"# tried title={title_no_parens} artist={artist}")

    # Does the no article and no paren match exactly?
    rows = cu.execute("SELECT id, path FROM media_file WHERE title = ? COLLATE NOCASE AND artist = ? COLLATE NOCASE", (title_no_parens, artist_no_the))
    r = rows.fetchone()
    if r:
        return r[1]
    if DEBUG:
        print(f"# tried title={title_no_parens} artist={artist_no_the}")

    # Try swapping and and ampersand
    if title_no_parens.count(" and ") != 0:
        title_ampersand = title_no_parens.replace(" and ", " & ")
    elif title_no_parens.count("&") != 0:
        title_ampersand = title_no_parens.replace("&", "and")
    else:
        title_ampersand = title_no_parens

    if artist_no_the.count(" and ") != 0:
        artist_ampersand = artist_no_the.replace(" and ", " & ")
    elif artist_no_the.count("&") != 0:
        artist_ampersand = artist_no_the.replace("&", "and")
    else:
        artist_ampersand = artist_no_the

    rows = cu.execute("SELECT id, path FROM media_file WHERE title = ? COLLATE NOCASE AND artist = ? COLLATE NOCASE",
                        (title_ampersand, artist_ampersand, ))
    r = rows.fetchone()
    if r:
        return r[1]
    if DEBUG:
        print(f"# tried title={title_ampersand or title} or title={title_no_parens} and artist={artist_ampersand or artist} or artist={artist_no_the}")


    # Try just a raw title match and give them as potential matches
    rows = cu.execute("SELECT id, path, title, artist, album FROM media_file WHERE title = ? COLLATE NOCASE", (title, ))
    ret = [f"# potential matches: \n# {r[2]} - {r[3]} - {r[4]}\n# {r[1]}" for r in rows.fetchall()]

    return ret


###   ### ### ###   ### ### ###   ### ### ###   ### ### ###   ### ### ###   ###

db = sqlite3.connect(DATABASE_PATH)


if len(sys.argv) == 1:
    print(f"Usage: {sys.argv[0]} <source file> <target file> <playlist name>")
    sys.exit(1)

# Try to open file or assume /dev/stdin if it isn't provided
try:
    path = sys.argv[1]
except IndexError:
    path = "/dev/stdin"

if not os.path.exists(path):
    print(f"ERROR: source file {path} does not exist")
    sys.exit(1)

# Use the target if specified, or interpolate it from the source
try:
    target_pl = sys.argv[2]
except IndexError:
    target_pl = str.replace(sys.argv[1], ".txt", "")

# Make sure it ends in m3u
if not target_pl.endswith(".m3u"):
    target_pl += ".m3u"

# Get the name as argv[3] or use the filename without the extension
try:
    playlist_name = sys.argv[3]
except IndexError:
    if path == "/dev/stdin":
        playlist_name = "Imported Playlist"
    else:
        playlist_name = re.sub(r"^\./", "", re.sub(r"\.txt$", "", path))

# Write our file
with open(target_pl, "w+") as w:

    # Use write() as a shortcut to print to the file
    write = lambda *args: print(*args, file=w)

    print(f"Converting {playlist_name} playlist to m3u: {target_pl}")

    write("#EXTM3U")
    write(f"#PLAYLIST:{playlist_name}")

    # Read the playlist text file, split it into fields, and then look up the
    with open(path, "r") as f:
        for line in f.readlines():
            line = line.strip("\n") + "\t\t\t\t"
            if line.count("\t") < 6:
                continue

            (name, time, artist, album, genre, _, _) = line.split("\t")[0:7]
            try:
                (mins, sec) = time.split(":")
                runtime = int(mins) * 60 + int(sec)
            except ValueError:
                (hours, mins, sec) = time.split(":")
                runtime = int(hours) * 3600 * int(mins) * 60 + int(sec)

            write(f"#EXTINF:{runtime},{artist} - {name}")

            # If it is found, use it, otherwise indicate that it is not found
            filename = findit(db, artist, album, name) or f"#notfound: {artist}/{album}/{name}.mp3"
            if type(filename) == str:
                write(filename)
            elif type(filename) == list:
                for line in filename:
                    write(line)

db.close()