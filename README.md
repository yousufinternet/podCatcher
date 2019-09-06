# podCatcher
Cute little script to parse podcasts rss feeds and download them for offline use.

needs `aria2` to download podcasts, you can get it from [here](https://aria2.github.io/)

Usage: 
```
usage: PodCatcher [-h] [--list | --download | --update-cache]
[--all | --latest] [--regex REGEX] [--after AFTER]
[--before BEFORE] [--exact-episode EXACT_EPISODE]
[--after-episode AFTER_EPISODE]
[--before-episode BEFORE_EPISODE] [--config CONFIG]
[podcast_names [podcast_names ...]]

List and download podcasts

positional arguments:
podcast_names         Put here names of podcasts -as defined in your config
file- to apply actions to them

optional arguments:
-h, --help            show this help message and exit
--list
--download
--update-cache
--all
--latest
--regex REGEX         filter episodes using a regex
--after AFTER         Episodes after a certain date only format:d-m-Y
--before BEFORE       Episodes before a certain date only format:d-m-Y
--exact-episode EXACT_EPISODE
episode number you would like to download
--after-episode AFTER_EPISODE
only download episodes carrying a number larger than
the provided
--before-episode BEFORE_EPISODE
only download episodes carrying a number smaller than
the provided
--config CONFIG       path to config file, by default config are read from
~/.config/podcatcher/urls
```
