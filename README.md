# Breakfast στον Κόσμο — personal RSS feed

This repository turns the public **ERT Echo / KOSMOS** archive for
**Breakfast στον Κόσμο — Προκόπης Δούκας** into a normal podcast RSS feed.

It does **not** copy or re-host the audio. Podcast clients receive the MP3
directly from ERT's servers.

## One-time setup

1. Create a new **public** GitHub repository, for example `kosmos-breakfast-rss`.
2. Upload all files from this folder, preserving `.github/workflows/update-feed.yml`.
3. In the repository, open **Settings → Pages**.
4. Under **Build and deployment → Source**, select **GitHub Actions**.
5. Open **Actions → Update and publish RSS → Run workflow**.
6. After the workflow finishes, GitHub Pages will be available at:

   `https://YOUR-GITHUB-USERNAME.github.io/kosmos-breakfast-rss/`

   Your podcast feed will be:

   `https://YOUR-GITHUB-USERNAME.github.io/kosmos-breakfast-rss/feed.xml`

## Subscribe

Use the feed URL in a podcast player that supports adding a podcast by URL.

### Apple Podcasts
On Mac: **File → Add a Show by URL…**

On iPhone/iPad, Apple Podcasts' handling of arbitrary/private RSS feeds can vary
by OS version. If "Add a Show by URL" is unavailable, use a client such as
Overcast or Pocket Casts that accepts custom RSS URLs.

## Updates

GitHub Actions rebuilds the feed every weekday at 08:15 UTC. This is roughly
late morning in Greece and safely after the 08:00–10:00 broadcast.

You can also update it manually at any time:
**Actions → Update and publish RSS → Run workflow**.

## How it works

`generate.py`:

1. reads the public ERT archive for the show;
2. finds episode pages;
3. opens their AMP versions;
4. extracts the public `.mp3` URL;
5. generates `docs/feed.xml`;
6. GitHub Pages publishes it.

By default it scans 3 archive pages and keeps up to 40 episodes. You can change
these through the `MAX_ARCHIVE_PAGES` and `MAX_EPISODES` environment variables.

## Important

This is an unofficial personal convenience feed. ERT can change its webpage
structure at any time; if that happens the scraper may need a small update.
Audio remains hosted and served by ERT.
